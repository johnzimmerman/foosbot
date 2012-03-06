CREATE TABLE game (
  id           integer PRIMARY KEY AUTOINCREMENT NOT NULL,
  match_id     integer NOT NULL,
  team1_score  integer,
  team2_score  integer,
  FOREIGN KEY (match_id)
    REFERENCES "match"(id)
);
CREATE TABLE "match" (
  id               integer PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE,
  match_datetime   datetime NOT NULL,
  team1_id         integer NOT NULL,
  team2_id         integer NOT NULL,
  is_bet           bool DEFAULT 0,
  bet              varchar
);
CREATE TABLE team (
  id          integer PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE,
  player1_id  integer NOT NULL,
  player2_id  integer NOT NULL,
  wins        integer DEFAULT 0,
  losses      integer DEFAULT 0,
  FOREIGN KEY (player1_id)
    REFERENCES player(id),
  FOREIGN KEY (player2_id)
    REFERENCES player(id)
);
CREATE TABLE player (
  id         integer PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE,
  name       varchar(20) NOT NULL,
  jabber_id  varchar(50) NOT NULL UNIQUE,
  wins       integer DEFAULT 0,
  losses     integer DEFAULT 0,
  is_active  bool DEFAULT 1
);