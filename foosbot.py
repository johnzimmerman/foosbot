from ConfigParser import SafeConfigParser
import copy
import datetime
import logging
import random
import re
import sqlite3
from os.path import abspath, join, dirname
from string import Template as StringTemplate

from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqError, IqTimeout


THIS_DIR = dirname(abspath(__file__))




class Template(object):
    def __init__(self, name, *args, **kwargs):
        self.tmpl = self.get_template(name)
        self.text = self.tmpl.safe_substitute(*args, **kwargs)
    
    def get_template(self, name):
        with open(join(THIS_DIR, "templates", name+".tmpl"), "r") as h:
            tmpl = StringTemplate(h.read())
        return tmpl
    
    def __str__(self):
        return self.text



class FoosBot(object):
    def __init__(self, jid, password):
        # we set this as an attribute instead of sublcassing because many
        # of ClientXMPP's attributes are named something we might accidentally
        # overrite (breaking ClientXMPP).  it's happened to me quite a bit
        self.xmpp = ClientXMPP(jid, password)
    
        self.xmpp.add_event_handler("session_start", self._session_start_handler)
        self.xmpp.add_event_handler("message", self._message_handler)

        self.xmpp.register_plugin('xep_0030') # Service Discovery
        self.xmpp.register_plugin('xep_0199') # XMPP Ping
        
        self.match_requested = False
        self.active_players = {}
        self.match_players = []
        self.state_machines = {}


    def start(self):
        self.xmpp.connect(('talk.google.com', 5222))
        self.xmpp.process(block=True)

    def _session_start_handler(self, event):
        self.xmpp.send_presence()

        # Most get_*/set_* methods from plugins use Iq stanzas, which
        # can generate IqError and IqTimeout exceptions
        try:
            self.xmpp.get_roster()
        except IqError as err:
            logging.error('There was an error getting the roster')
            logging.error(err.iq['error']['condition'])
            self.xmpp.disconnect()
        except IqTimeout:
            logging.error('Server is taking too long to respond')
            self.xmpp.disconnect()


    def _message_handler(self, msg):
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
        if reply: self.send(sender, reply)   


    def send(self, to, message):
        if not isinstance(to, (tuple, list)): to = [to]
        message = str(message) # evaluates Template, if it exists
        for player in to:
            self.xmpp.send_message(player, message)



class GameCreator(object):
    
    def __init__(self, player):
        self.entry_mode = "normal"

        # Player variables
        self.player_status = None
        self.player_id = None
        
        # Scoring variables
        self.score_progress = None
        self.match_num = 0
        self.num_games = 0
        self.current_game = 1
        self.game_data = []

        # Check for existing user on object creation and set appropriate status
        t = (player, )
        result = db_query("select id, is_active from player where jabber_id = ?", t, "r")
 
        if len(result) >= 1:
            if result[0][1] == 1:
                self.player_status = "active"
            else:
                self.player_status = "retired"
            self.player_id = result[0][0]
        else:
            self.player_status = "new"

        
    def handle_message(self, sender, message):
        reply = "I'm sorry, but this feature hasn't been programmed yet."
        
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
            message = message.capitalize()
            t = (message, sender)
            result = db_query("insert into player (name, jabber_id) values (?, ?)", t, "w")
            if result == 'success':
                reply = ("Thanks %s. You've been successfully added to my database. "
                         "Please type 'help' to see a list of commands.") % message
                t = (sender, )
                result = db_query("select id from player where jabber_id = ?", t, "r")
                self.player_id = result[0][0]
            else:
                reply = "I'm sorry, something bad has happened. Please contact the bot administrator."
            self.player_status = "active"
        
        # Commands an active player can perform
        elif self.player_status == "active":
            if self.entry_mode == "normal":
                if message == "help":
                    reply = Template("help")
                
                elif message == "play":
                    pass
                
                elif message == "quickplay" and bot.match_requested == False:
                    bot.match_requested = True
                    bot.match_players.append({'id' : self.player_id, 'jabber_id' : sender })
                    
                    t = (1, )
                    result = db_query("select jabber_id, name from player where is_active = ?", t, "r")

                    for row in result:
                        bot.active_players[row[0]] = row[1]

                    message = ("%s has challeneged you to a match of table "
                               "football! Would you like to play? Reply with "
                               "(y)es to play.") % bot.active_players[sender]
                    bot.send(bot.active_players.keys(), message)

                    reply = 'Match requested. I will notify the others.'
                
                elif (message == 'y' or message == 'yes') and bot.match_requested == True:
                    # Do not allow a registered user to be added more than once
                    if sender in bot.match_players:
                        #The following message won't be sent. FIX LATER
                       reply = "You are already playing in the next match."

                    # Check for 4 players 
                    if len(bot.match_players) < 4:
                        bot.match_players.append({'id' : self.player_id, 'jabber_id' : sender })
                        # notify game initiator as players join
                        bot.send(bot.match_players[0]['jabber_id'],
                                 '%s has joined the match.' % bot.active_players[sender])
                    if len(bot.match_players) == 4:
                        # Generate teams
                        match_data = create_match(bot.match_players)
                        
                        # convenience shortcuts
                        teams = match_data['teams']
                        ap = bot.active_players
                        
                        tparams = {
                            "id": match_data['match_id'],
                            "white1": ap[teams[0]], "white2": ap[teams[1]],
                            "red1": ap[teams[2]], "red2": ap[teams[3]],
                        }
                        bot.send(teams, Template("match", **tparams))
                        
                        # Clear match/active players array and 
                        # reset match_requested
                        del bot.match_players[:]
                        bot.active_players.clear()
                        bot.match_requested = False

                    reply = None
                
                elif message == "score":
                    self.entry_mode = "scoring"
                    reply = ("You are now in scoring mode. You can exit this mode "
                             "at any time by typing 'exit'. Please enter the "
                             "match number that you would like to score.")
                    self.score_progress = 'match number'

                elif message == "retire":
                    t = (player,)
                    db_query("update player set is_active = 0 where jabber_id='?'", t, "w")
                    self.player_status = "retired"
                    reply = Template("retire")
                else:
                    reply = ("I'm sorry, I dont understand. Please type 'help' "
                             "for a list of commands.")

            # Scoring mode
            elif self.entry_mode == 'scoring':
                if message == 'exit':
                    self.entry_mode = 'normal'
                    reply = "You are no longer in scoring mode."
                elif self.score_progress == 'match number':
                    if check_if_int(message):
                        # check if match num exists
                        t = (message, )
                        result = db_query("select id from match where id = ?", t, "r")
                        if len(result) == 1:
                            self.match_num = int(result[0][0])
                            # check if match has been scored
                            t = (self.match_num, )
                            result = db_query("select id from game where match_id = ?", t, "r")
                            if len(result) >= 1:
                                reply = ('That match has already been scored. '
                                         'Please enter another or type exit.')
                            else:
                                reply = "How many games did you play?"
                                self.score_progress = 'number of games'
                        else:
                            reply = ("That match number does not exist. "
                                     "Please try again.")        
                    else:
                        reply = 'Please enter a number.'

                elif self.score_progress == 'number of games':
                    if check_if_int(message):
                        self.num_games = int(message)
                        t = (self.match_num, )
                        result = db_query("select p1.name, p2.name from team join match on match.team1_id=team.id "
                                          "join player as p1 on p1.id = player1_id join player as p2 on " 
                                          "p2.id = player2_id where match.id = ?;", t, "r")
                        team1_names = {'white1': result[0][0], 'white2' : result[0][1]}
                        reply = Template("scoring_instructions", **team1_names)
                        self.score_progress = 'enter scores'
                    else :
                        reply = 'Please enter a number.'

                elif self.score_progress == 'enter scores':
                    if self.current_game <= len(range(self.num_games)):
                        message = message.replace(' ', '')
                        if re.search('^(\d{1}|\d{2})-(\d{1}|\d{2})$', message):
                            sc1, sc2 = message.split('-')
                            if sc1 != sc2:
                                self.game_data.append((self.match_num, sc1, sc2))
                                if self.current_game == len(range(self.num_games)):
                                    # enter scores in DB
                                    db_query("insert into game (match_id, team1_score, team2_score) "
                                             "values (?, ?, ?)", self.game_data, "wm")

                                    reply = ('Thank you, match #%d has been '
                                             'successfully scored. Now leaving '
                                             'scoring mode.' % self.match_num)

                                    # Populate team wins/losses
                                    set_team_stats(self.match_num)

                                    # flush variables
                                    self.match_num = 0
                                    self.num_games = 0
                                    self.current_game = 1
                                    del self.game_data[:]
                                    self.score_progress = None
                                    self.entry_mode = 'normal'

                                else:
                                    self.current_game += 1
                                    reply = 'Please enter the score of game #%d' % self.current_game
                            else:
                                reply = 'Please enter a valid score.'
                        else:
                            reply = 'Please enter a valid score.'
            
        return reply


def db_query(query, args, query_type):
    try:
        con = sqlite3.connect('./data.db')
        cur = con.cursor() 
        if query_type == 'w':
            cur.execute(query, args)
            con.commit()
            return "success"
        elif query_type == 'wm':
            cur.executemany(query, args)
            con.commit()
            return "success"
        else:
            cur.execute(query, args)
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
        result = db_query("select id from team where (player1_id = ? OR player1_id = ?) AND (player2_id = ? OR player2_id = ?)", t, "r")
        # Get team ID if yes
        if len(result) >= 1:
            match_query_data.append(result[0][0])
        # Create team ID and then get newly created ID
        else:
            t2 = t[0:2]
            db_query("insert into team (player1_id, player2_id) values (?, ?)", t2, "w")
            result = db_query("select id from team where (player1_id = ? OR player1_id = ?) AND (player2_id = ? OR player2_id = ?)", t, "r")
            match_query_data.append(result[0][0])

    # Create a match
    match_time = datetime.datetime.now()
    match_query_data.append(match_time)

    # Convert match_query_data into a tuple to be used in query
    match_query_data = tuple(match_query_data)
    result = db_query("insert into match (team1_id, team2_id, match_datetime) values (?, ?, ?)", match_query_data, "w")

    t = (match_time,)
    match_id = db_query("select id from match where match_datetime = ?", t, "r")[0][0]
    
    match_data = {
        'match_id' : match_id,
        'teams' : [players[0]['jabber_id'], players[1]['jabber_id'],
                   players[2]['jabber_id'], players[3]['jabber_id']]
    }
    
    return match_data
 
def check_if_int(message):
    try:
        int(message)
        return True
        
    except Exception: 
        return False


def set_team_stats(match_id):
    t1_wins = 0
    t2_wins = 0
    t = (match_id, )
    result = db_query("select team1_score, team2_score from game where match_id = ?", t, "r")

    if len(result) >= 1:
        for game in result:
            if game[0] > game[1]: 
                t1_wins += 1
            else: 
                t2_wins += 1

        if t1_wins > t2_wins:
            db_query("update team set wins = wins + 1 where id in (select team1_id from match where id = ?);", t, "w")
            db_query("update team set losses = losses + 1 where id in (select team2_id from match where id = ?);", t, "w")
        else:
            db_query("update team set wins = wins + 1 where id in (select team2_id from match where id = ?);", t, "w")
            db_query("update team set losses = losses + 1 where id in (select team1_id from match where id = ?);", t, "w")
    
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
    bot.start()
