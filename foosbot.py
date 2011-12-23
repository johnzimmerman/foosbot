from ConfigParser import SafeConfigParser
import copy
import logging
import random

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout

# Load the config file
cfgparser = SafeConfigParser()
cfgparser.read('foosbot.cfg')

def generate_teams(players):
    players = copy.copy(players)
    random.shuffle(players)
    return players

class FoosBot(ClientXMPP):

    def __init__(self, jid, password):
        ClientXMPP.__init__(self, jid, password)

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)

        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0199') # XMPP Ping
        
        self.game_requested = False
        self.registered_players = cfgparser.options('Players')
        self.active_players = []

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
            # TODO Add logging
            return
            
        sender = str(msg["from"]).split("/")[0]
        
        # Check if the person requesting the game is on the players list
        if not cfgparser.has_option('Players', sender):
            msg.reply('I\'m sorry, but I don\'t recognize you.').send()
            return
            
        player = cfgparser.get('Players', sender)
        body = str(msg["body"]).strip().lower()
        
        if body == 'play' and self.game_requested == False:
            # TODO Check to see if 4 registered players are online
            # TODO Create variable for game start time. Check each reply to make sure !> 5 min.
            # Set game state to requested
            self.game_requested = True
            # Add requesting player to active players list
            self.active_players.append(sender)
            # Send message to other registered players
            for rp in self.registered_players:
                if rp != sender:
                    self.send_message(mto=rp,
                                      mbody="""%s has challenged you to a game of table football! \
                                      Would you like to play? [y/n]""" % player,
                                      mtype='chat')
        elif body == 'play' and self.game_requested == True:
            msg.reply('Oh hai, %s. Someone is already looking for a game. \
                      Would you like to play? [y/n]' % player).send()
        elif body == 'y' and self.game_requested == True:
            # Check for 4 players
            if sender in self.active_players:
                msg.reply("Relax! I heard you the first time.").send()
            if len(self.active_players) < 4:
                # Add player to the list
                self.active_players.append(sender)
                msg.reply("You're in! Waiting for %d more players..." % (4 - len(self.active_players))).send()
                if len(self.active_players) == 4:
                    # Generate teams
                    teams = generate_teams(self.active_players)
                    # Notify players
                    for teammate in teams:
                        print '!!!!!! PAY ATTENTION !!!!!! %s' % teammate
                        self.send_message(mto=teammate,
                                          mbody="""
                                          Here are the teams I came up with:
                                          White team: %s and %s
                                          Red team: %s and %s
                                          Play on, playas!""" % (cfgparser.get('Players', teams[0]),
                                          cfgparser.get('Players', teams[1]),
                                          cfgparser.get('Players', teams[2]),
                                          cfgparser.get('Players', teams[3])),
                                          mtype='chat')
                    # Clear active players array and set game_requeste to false
                    del self.active_players[:]
                    self.game_requested = False
                    
        #msg.reply("Thanks for sending me a message %(from)s\n%(body)s" % msg).send()
    

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-8s %(message)s')
                        
    jid = cfgparser.get('Connection', 'jid')
    password = cfgparser.get('Connection', 'password')
    
    xmpp = FoosBot(jid, password)
    xmpp.connect(('talk.google.com', 5222))
    xmpp.process(block=True)