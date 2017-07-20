#!/usr/local/bin/python2.7

import json
import re
import sqlite3
import time

__DB = sqlite3.connect("/home/seba/rtorrent_session/rpi_logs.db")
__DB.execute("pragma foreign_keys = on;")
__DB.execute("pragma case_sensitive_like = off;")

class EventType(object): pass

def AddTorrent(torrent_hash, name):
    __DB.execute("INSERT OR REPLACE INTO torrents (hash, name) VALUES (?,?)",
                 (torrent_hash, name))
    __DB.commit()

def AddTorrentEvent(event_type, torrent_hash, extra=None):
    now = int(time.time())
    if extra is not None: extra = json.dumps(extra, ensure_ascii=False)
    __DB.execute("""INSERT INTO torrent_events (type, torrent_hash, date, extra) 
    VALUES (?,?,?,?)""", (event_type, torrent_hash, now, extra))
    __DB.commit()

def HasSubtitles(torrent_hash):
    return len(__DB.execute("""\
SELECT date FROM torrent_events 
WHERE torrent_hash == ? AND type == ? LIMIT 1""", (
                torrent_hash, EventType.subtitles)).fetchall()) > 0

def GetTorrentsLogTable(name_query=None, min_date=None, max_date=None,
                        max_num_entries=None):
    # From http://www.sqlite.org/lang_datefunc.html.
    if min_date is None: min_date = 0
    if max_date is None: max_date = 10675199167

    if max_num_entries is None: max_num_entries = 10000
    if name_query: name_query = "%%%s%%" % re.sub(r"[ .]", "_", name_query)
    
    sql = """\
SELECT
    torrents.hash, torrents.name,
    download_start.max_date,
    download_finish.max_date - download_start.max_date,
    subtitles.max_date
FROM
    torrents
    INNER JOIN (SELECT torrent_hash, MAX(date) AS max_date FROM torrent_events
        WHERE type == :type_start GROUP BY torrent_hash) AS download_start
        ON download_start.torrent_hash == torrents.hash
    LEFT JOIN (SELECT torrent_hash, MAX(date) AS max_date FROM torrent_events
        WHERE type == :type_finish GROUP BY torrent_hash) AS download_finish
        ON download_finish.torrent_hash == torrents.hash
    LEFT JOIN (SELECT torrent_hash, MAX(date) AS max_date FROM torrent_events
        WHERE type == :type_subtitles GROUP BY torrent_hash) AS subtitles
        ON subtitles.torrent_hash == torrents.hash
WHERE download_start.max_date BETWEEN :min_date AND :max_date %s
ORDER BY download_start.max_date DESC, torrents.name ASC LIMIT :limit;""" % (
        "AND torrents.name LIKE :name_query" if name_query else "")

    params = { "type_start": EventType.download_start,
               "type_finish": EventType.download_finish,
               "type_subtitles": EventType.subtitles,
               "min_date": min_date, "max_date": max_date,
               "name_query": name_query,
               "limit": max_num_entries }
    return __DB.execute(sql, params).fetchall()

####### Initialize the tables:

__DB.execute("""\
CREATE TABLE IF NOT EXISTS torrents (
  hash TEXT PRIMARY KEY NOT NULL,
  name TEXT
);""")

__DB.execute("""\
CREATE TABLE IF NOT EXISTS torrent_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type INTEGER,
  torrent_hash TEXT,
  date INTEGER,
  extra TEXT,
  FOREIGN KEY(type) REFERENCES event_types(id)
);""")

__DB.execute("""\
CREATE INDEX IF NOT EXISTS torrent_events_hash_index ON torrent_events (
  torrent_hash
);""")

__DB.execute("""\
CREATE TABLE IF NOT EXISTS event_types (
  id INTEGER PRIMARY KEY,
  name TEXT
);""")

if __DB.execute("SELECT COUNT(*) FROM event_types;").fetchone()[0] == 0:
    types = enumerate(["download_start", "download_finish", "subtitles"])
    __DB.executemany("INSERT INTO event_types (id, name) VALUES (?, ?);", types)
    __DB.commit()

for i, name in __DB.execute("SELECT id,name FROM event_types;").fetchall():
    setattr(EventType, name, i)

if __name__ == "__main__":
    if 0:
        AddTorrent("thisisahash", "lala1")
        AddTorrent("thisisahash", "lala2")
        AddTorrentEvent(EventType.download_start, "thisisahash")
        AddTorrentEvent(EventType.download_finish, "thisisahash")
    print GetTorrentsLogTable()
    print GetTorrentsLogTable(name_query="ar ow")
    print HasSubtitles("24778772CE261A966A65CF01FD2FBA3F2F147C09")
