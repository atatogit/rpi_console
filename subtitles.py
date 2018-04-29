#!/usr/local/bin/python2.7

import re

from levenshtein import Levenshtein2


__VID_EXTENSIONS = set((".avi", ".mpg", ".mp4", ".mkv"))

__VID_EXTENSIONS_RE = re.compile("(%s)$" % "|".join(
        map(lambda s: s.replace(".", r"\."), __VID_EXTENSIONS)), re.IGNORECASE)


def TorrentNameToRelease(name):
    return re.sub(__VID_EXTENSIONS_RE, "", name)


def GetMovieFiles(torrent_files, release):
    movie_files = []
    for fname in torrent_files:
        if re.search(__VID_EXTENSIONS_RE, fname):
            distance = Levenshtein2(fname, release) 
            movie_files.append((distance, fname))
    if not movie_files: return movie_files
    movie_files.sort()
    return [x[1] for x in movie_files]

