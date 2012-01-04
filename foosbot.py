from ConfigParser import SafeConfigParser
import copy
import datetime
import logging
import Queue
import random
import sqlite3
import threading

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout


class FoosBot(ClientXMPP):

    def __init__(self, jid, password):
        ClientXMPP.__init__(self, jid, password)

        self.add_event_handler("session_start", self.session_start)
        self.add_event_handler("message", self.message)

        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0199') # XMPP Ping
        
        self.game_requested = False
        self.game_requested_time = None
        self.active_players = []
        self.state_machines = {}

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
        body = str(msg["body"]).strip().lower()
        
        game_creator = self.state_machines.get(sender)
        if not game_creator: 
            self.state_machines[sender] = GameCreator(sender)
            game_creator = self.state_machines.get(sender)
        reply = game_creator.handle_message(sender, body)
        
        msg.reply(reply).send()        
        #msg.reply("Thanks for sending me a message %(from)s\n%(body)s" % msg).send()

class GameCreator(object):
    
    def __init__(self, player):
        self.player_status = "new"
        
    def handle_message(self, sender, message):
        if self.player_status == "new":
            reply = ("Hi, I'm FoosBot. I don't believe we've met. "
            "I organize games of foosball and keep track of stats. "
            "Would you like to register and be notified when someone "
            "requests a game?")
            self.player_status = "registration"
        elif self.player_status == "registration":
            if message == "yes":
                reply = ("Great! I just need to know your name. What should "
                "I call you?")
                self.player_status = "waiting for name"
            elif message == "no": 
                reply = "That's okay. Maybe some other time."
                self.player_status = "new"
            else: 
                reply = ("I'm sorry, I don't understand. Please respond "
                "with 'yes' or 'no'.")
        elif self.player_status == "waiting for name":
            t = (message, sender)
            queue.put(("insert into player (name, jabber_id) values (?, ?)", t))
            reply = ("Thanks %s. You've been successfully added to my database "
            "Please type 'help' to see a list of commands.") % message
            self.player_status = "active"
        elif self.player_status == "active":
            # Commands an active player can perform
            if message == "help":
                reply = ("I understand the following commands:\n"
                "help - Displays this menu\n"
                "play - Requests a game of foosball allowing you to set a time delay and wager\n"
                "quickplay - Requests a game of foosball instantly with no wager\n"
                "retire - Remove yourself from the active roster and disable notifications (your stats are not lost)\n"
                "unretire - Get back in the game!\n")
            elif message == "play":
                reply = "I'm sorry, but this feature hasn't been programmed yet."
            elif message == "quickplay":
                reply = "I'm sorry, but this feature hasn't been programmed yet."
            elif message == "retire":
                t = (player,)
                queue.put(("update player set is_active=0 where jabber_id='?'", t))
                self.player_status = "retired"
                reply = ("You have been removed from the active roster and "
                "will no longer receive notifications when games are "
                "requested. Pull a Brett Favre and unretire at any time by "
                "sending me the message 'unretire'")
                
        return reply 


def db_thread(queue):
    conn = sqlite3.connect('./data_working.db')

    def db_query(query, args):
        cur = conn.cursor()
        cur.execute(query, args)
        print "DEBUG AFTER: query = %s args = %s" % (query, args)
        conn.commit()

    while True:
        query, args = queue.get()
        print "DEBUG BEFORE: query = %s args = %s" % (query, args)
        db_query(query, args)


def generate_teams(players):
    # TODO Add algorithm to create best matchup
    players = copy.copy(players)
    random.shuffle(players)
    return players
    
    
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-8s %(message)s')

    # Load the config file
    cfgparser = SafeConfigParser()
    cfgparser.read('foosbot.cfg')
    
    queue = Queue.Queue()
    threading.Thread(target=db_thread, args=(queue,)).start()                          

    jid = cfgparser.get('Connection', 'jid')
    password = cfgparser.get('Connection', 'password')
    
    xmpp = FoosBot(jid, password)
    xmpp.connect(('talk.google.com', 5222))
    xmpp.process(block=True)