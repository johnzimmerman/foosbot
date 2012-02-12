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
        
        self.match_requested = False
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
        # Game creator variables
        self.player_status = None
        self.player_id = None

        # Check for existing user on object creation and set appropriate status
        t = (player, )
        result = db_query("select id, is_active from player where jabber_id = ?", t, "read")
 
        if len(result) >= 1:
            if result[0][1] == 1:
                self.player_status = "active"
            else:
                self.player_status = "retired"
            self.player_id = result[0][0]
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
                reply = ("Thanks %s. You've been successfully added to my database. "
                         "Please type 'help' to see a list of commands.") % message
                t = (sender, )
                result = db_query("select id from player where jabber_id = ?", t, "read")
                self.player_id = result[0][0]
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
            
            elif message == "quickplay" and bot.match_requested == False:
                bot.match_requested = True
                bot.match_players.append({'id' : self.player_id, 'jabber_id' : sender })
                t = (1, )
                result = db_query("select jabber_id, name from player where is_active = ?", t, "read")
                for row in result:
                    bot.active_players[row[0]] = row[1]
                for player in bot.active_players:
                    #if player != sender: !!! REMOVE THIS COMMENT LATER !!!
                        bot.send_message(mto = player,
                                         mbody=("%s has challeneged you to a "
                                                "game of table football!") % bot.active_players[sender],
                                         mtype='chat')
                reply = "I'm sorry, but this feature hasn't been programmed yet."
            
            elif message == 'y' and bot.match_requested == True:
                #Do not allow a registered user to be added more than once
                if sender in bot.match_players:
                    #The following message won't be sent. FIX LATER
                   reply = "You are already playing in the next match."
                   return
                Check for 4 players 
                if len(bot.match_players) < 4:
                    bot.match_players.append({'id' : self.player_id, 'jabber_id' : sender })
                if len(bot.match_players) == 4:
                    # Generate teams
                    match_data = create_match(bot.match_players)
                    for teammate in match_data['teams']:
                        bot.send_message(mto=teammate,
                                          mbody=("Match %s has been created "
                                          "with the following teams:\n" 
                                          "White team: %s and %s\nVS\n"
                                          "Red team: %s and %s\n"
                                          "Good luck.") % 
                                          ([match_data['match_id']],
                                          bot.active_players[match_data['teams'][0]],
                                          bot.active_players[match_data['teams'][1]],
                                          bot.active_players[match_data['teams'][2]],
                                          bot.active_players[match_data['teams'][3]],),
                                          mtype='chat')
                    # Clear active players array and set game_requeste to false
                    del bot.active_players[:]
                    bot.match_requested = False

                reply = "generic reply"
            
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
        con = sqlite3.connect('./data.db')
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

def create_match(players):
    # TODO Add algorithm to create best matchup
    # Generate teams
    players = copy.copy(players)
    random.shuffle(players)

    p1 = players[0]['id'] 
    p2 = players[1]['id']
    p3 = players[2]['id']
    p4 = players[3]['id']
    match_query_data = []

    for t in [(p1, p2, p1, p2), (p3, p4, p3, p4)]:
        # Check if team exists in the DB
        result = db_query("select id from team where (player1_id = ? OR player2_id = ?) AND (player1_id = ? OR player2_id = ?)", t, "read")    
        # Get team ID if yes
        if len(result) >= 1:
            match_query_data.append(result[0][0])
        # Create team ID and then get newly created ID
        else:
            t2 = t[0:2]
            db_query("insert into team (player1_id, player2_id) values (?, ?)", t2, "write")
            result = db_query("select id from team where (player1_id = ? OR player2_id = ?) AND (player1_id = ? OR player2_id = ?)", t, "read")
            match_query_data.append(result[0][0])

    # Create a match
    match_time = datetime.datetime.now()
    match_query_data.append(match_time)

    # Convert match_query_data into a tuple to be used in query
    match_query_data = tuple(match_query_data)
    result = db_query("insert into match (team1_id, team2_id, match_datetime) values (?, ?, ?)", match_query_data, "write")

    t = (match_time,)
    match_id = db_query("select id from match where match_datetime = ?", t, "read")[0][0]
    print "-------------- DEBUG --------------"
    print players
    print "-------------- DEBUG --------------"
    
    match_data = {
        'match_id' : match_id,
        'teams' : [players[0]['jabber_id'], players[1]['jabber_id'],
                   players[2]['jabber_id'], players[3]['jabber_id']]
    }
    
    return match_data
    
    
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-8s %(message)s')

    # Load the config file
    cfgparser = SafeConfigParser()
    cfgparser.read('settings.cfg')
    
    # Set connection settings
    jid = cfgparser.get('Connection', 'jid')
    password = cfgparser.get('Connection', 'password')

    # Launch bot
    bot = FoosBot(jid, password)
    bot.connect(('talk.google.com', 5222))
    bot.process(block=True)