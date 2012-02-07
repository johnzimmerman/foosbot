from ConfigParser import SafeConfigParser
import copy
import datetime
import logging
import random
import sqlite3

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
        self.quick_game_requested = False
        self.active_players = {}
        self.match_players = []
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
        # Check for existing user on object creation and set appropriate status
        t = (player, )
        result = db_query("select is_active from player where jabber_id = ?", t, "read")
        if result[0][0] == 1:
            self.player_status = "active"
        elif result[0][0] == 0:
            self.player_status = "retired"
        else:
            self.player_status = "new"

        
    def handle_message(self, sender, message):
        # Player registration
        if self.player_status == "new":
            reply = ("Hi, I'm FoosBot. I don't believe we've met. "
                     "I organize games of foosball and keep track of stats. "
                     "Would you like to register and be notified when "
                     "someone requests a game?")
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
            result = db_query("insert into player (name, jabber_id) values (?, ?)", t, "write")
            if result == 'success':
                reply = ("Thanks %s. You've been successfully added to my database "
                         "Please type 'help' to see a list of commands.") % message
            else:
                reply = "I'm sorry, something bad has happened. Please contact the bot administrator."
            self.player_status = "active"
        
        # Commands an active player can perform
        elif self.player_status == "active":
            if message == "help":
                reply = ("I understand the following commands:\n"
                         "help - Displays this menu\n"
                         "play - Requests a game of foosball allowing you to set a time delay and wager\n"
                         "quickplay - Requests a game of foosball instantly with no wager\n"
                         "retire - Remove yourself from the active roster and disable notifications (your stats are not lost)\n"
                         "unretire - Get back in the game!\n")
            elif message == "play":
                reply = "I'm sorry, but this feature hasn't been programmed yet."
            elif message == "quickplay" and bot.quick_game_requested == False:
                t = (1, )
                result = db_query("select jabber_id, name from player where is_active = ?", t, "read")
                for row in result:
                    bot.active_players[row[0]] = row[1]
                bot.quick_game_requested == True
                for player in bot.active_players:
                    #if player != sender: !!! REMOVE THIS COMMENT LATER !!!
                        bot.send_message(mto = player,
                                         mbody=("%s has challeneged you to a "
                                                "game of table football!") % bot.active_players[sender],
                                         mtype='chat')
                reply = "I'm sorry, but this feature hasn't been programmed yet."
            elif message == "retire":
                t = (player,)
                db_query("update player set is_active = 0 where jabber_id='?'", t, "write")
                self.player_status = "retired"
                reply = ("You have been removed from the active roster and "
                         "will no longer receive notifications when games are "
                         "requested. Pull a Brett Favre and unretire at any time by "
                         "sending me the message 'unretire'")
            else:
                reply = ("I'm sorry, I dont understand. Please type 'help' "
                         "for a list of commands.")
                
        return reply 


def db_query(query, args, query_type):
    try:
        con = sqlite3.connect('./data_working.db')
        cur = con.cursor() 
        cur.execute(query, args)
        if query_type == 'write':
            con.commit()
            return "success"
        else:
            rows = cur.fetchall()
            if rows == None:
                return "failure"
            else:
                return rows
    except sqlite3.Error:
        if con:
            con.rollback()
            return "failure"
    finally:
        if con:
            con.close()

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
    
    # Set connection settings
    jid = cfgparser.get('Connection', 'jid')
    password = cfgparser.get('Connection', 'password')

    # Launch bot
    bot = FoosBot(jid, password)
    bot.connect(('talk.google.com', 5222))
    bot.process(block=True)