#!/usr/local/bin/python2.7

import os
import subprocess
import sys
import unicodedata
import urllib

import opensubtitles
import subtitles
import torrent


def __GetRpiConsoleLogUrl(event_type, h, name=None, movie_size=None,
                          opensubtitles_hash=None):
    params = "type=%s&h=%s" % (event_type, h)
    if type(name) == unicode:
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore')
    if name:
        params += "&name=%s" % urllib.quote(name)
    if movie_size:
        params += "&movie_size=%d" % movie_size
    if opensubtitles_hash:
        params += "&opensubtitles_hash=%s" % str(opensubtitles_hash)
    return "http://raspi:8080/rtorrentlogs?%s" % params


if __name__ == "__main__":
    event = sys.argv[1]
    torrent_hash = sys.argv[2]
    if event == "inserted_new":
        name = sys.argv[3]
        url = __GetRpiConsoleLogUrl("insert", torrent_hash, name)
        print urllib.urlopen(url).read()
    elif event == "finished":
        torrent_hash = sys.argv[2]
        base_path = sys.argv[3]
        name = torrent.GetTorrentName(torrent_hash)
        assert name
        release = subtitles.TorrentNameToRelease(name)
        assert release
        movie_files = subtitles.GetMovieFiles(
            torrent.GetTorrentFiles(torrent_hash), release)
        if movie_files:
            movie_file = movie_files[0]  # Picking the first one...
            movie_file_fullpath = os.path.join(base_path, movie_file)
            movie_size = os.path.getsize(movie_file_fullpath)
            opensubtitles_hash = opensubtitles.HashFile(movie_file_fullpath)
        else:
            movie_size, opensubtitles_hash = None, None
        url = __GetRpiConsoleLogUrl("finished", torrent_hash, name,
                                    movie_size, opensubtitles_hash)
        print urllib.urlopen(url).read()
        # Now do the move.
        src_dir =  sys.argv[4]
        target_dir = sys.argv[5]
        subprocess.call(["mergetodir.py", src_dir, target_dir])
    else:
        sys.exit(1)
