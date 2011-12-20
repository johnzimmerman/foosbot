from ConfigParser import SafeConfigParser
import logging
import random

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout


# Load the config file
cfgparser = SafeConfigParser()
cfgparser.read('foosbot.cfg')

# Game configuration
game_requested = False
active_players = []

class FoosBot(ClientXMPP):

    def __init__(self, jid, password):
        ClientXMPP.__init__(self, jid, password)

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)

        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0199') # XMPP Ping

    def session_start(self, event):
        self.send_presence()

        # Most get_*/set_* methods from plugins use Iq stanzas, which
        # can generate IqError and IqTimeout exceptions
        try:
            self.get_roster()
        except IqError as err:
            logging.error('There was an error getting the roster')
            logging.error(err.iq['error']['condition'])
            self.disconnect()
        except IqTimeout:
            logging.error('Server is taking too long to respond')
            self.disconnect()

    def message(self, msg):
        if msg['type'] not in ('chat', 'normal'):
            # TODO
            # Add logging
            return
            
        sender = str(msg["from"]).split("/")[0]
        
        # Check if the person requesting the game is on the players list
        if not cfgparser.has_option('Players', sender):
            msg.reply('I\'m sorry, but I don\'t recognize you.').send()
            return
            
        player = cfgparser.get('Players', sender)
        body = str(msg["body"]).strip().lower()
        
        if body == 'play' and game_requested == False:
            # Set game state to requested
            game_requested = True
            # Add requesting player to active players list
            active_players.append(player)
            # Send message to other registered players
            registered_players = cfgparser.options('Players')
            for rp in registered_players:
                self.send_message(mto=rp,
                                  mbody='%s has challenged you to a game of f00sball!' % player,
                                  mtype='chat')
            #msg.reply('Oh Hai, %s' % player).send()
            
         
        #msg.reply("Thanks for sending me a message %(from)s\n%(body)s" % msg).send()
    

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-8s %(message)s')
                        
    jid = cfgparser.get('Connection', 'jid')
    password = cfgparser.get('Connection', 'password')
    
    xmpp = FoosBot(jid, password)
    xmpp.connect(('talk.google.com', 5222))
    xmpp.process(block=True)