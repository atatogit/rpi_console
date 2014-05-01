#!/usr/bin/python

import sqlite3

__DB = sqlite3.connect("/home/seba/rtorrent_session/rpi_logs.db")
__DB.execute("pragma foreign_keys = on;")

####### Initialize the tables:

__DB.execute("""\
CREATE TABLE IF NOT EXISTS torrents (
  hash TEXT PRIMARY KEY NOT NULL,
  name TEXT
);""")

__DB.execute("""\
CREATE TABLE IF NOT EXISTS torrent_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_type INTEGER,
  torrent_hash TEXT,
  date TEXT,
  FOREIGN KEY(torrent_hash) REFERENCES torrents(hash),
  FOREIGN KEY(event_type) REFERENCES event_types(id)
);""")

__DB.execute("""\
CREATE TABLE IF NOT EXISTS event_types (
  id INTEGER PRIMARY KEY,
  name TEXT
);""")

if __DB.execute("SELECT COUNT(*) from event_types").fetchone()[0] == 0:
    types = enumerate([
            "start_download", "finish_download", "subtitles_downloaded"])
    __DB.executemany("INSERT INTO event_types(id, name) VALUES (?, ?)", types)
    __DB.commit()

if __name__ == "__main__":
    pass
