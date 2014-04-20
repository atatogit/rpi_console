#!/usr/bin/python

from StringIO import StringIO
import gzip
import os
import re
import urllib
import urllib2
import zipfile

from levenshtein import Levenshtein2

__VID_EXTENSIONS = set((".avi", ".mpg", ".mp4", ".mkv"))

__VID_EXTENSIONS_RE = re.compile("(%s)$" % "|".join(
        map(lambda s: s.replace(".", r"\."), __VID_EXTENSIONS)), re.IGNORECASE)

__SUB_EXTENSIONS = set((".sub", ".srt"))

__SUB_EXTENSIONS_RE = re.compile("(%s)$" % "|".join(
        map(lambda s: s.replace(".", r"\."), __SUB_EXTENSIONS)), re.IGNORECASE)

__SUB_LIST_ENTRY_RE = re.compile(
    'href="(/subtitles/[^/]*/english/[^"]*)"' +
    '[^<]*<div[^<]*<span[^<]*</span[^<]*<span[^>]*>([^<]*)</span')

__SUB_DOWNLOAD_LINK_RE = re.compile('href="(/subtitle/download?[^"]*)"')

__MAX_NUM_SUBS = 5

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

def __GetSearchReleaseUrl(release):
    return "http://subscene.com/subtitles/release?q=%s" % urllib.quote(release)

def SearchSubtitlesForRelease(query):
    data = urllib.urlopen(__GetSearchReleaseUrl(query)).read()
    matches = re.findall(__SUB_LIST_ENTRY_RE, data)
    if not matches: return []
    stripped_matches = [(m[1].strip(), m[0].strip()) for m in matches]
    scored_matches = [(Levenshtein2(query, m[0]), m) for m in stripped_matches]
    scored_matches.sort()
    urls_seen = set()
    subs = []
    for score, (name, url) in scored_matches:
        if len(subs) >= __MAX_NUM_SUBS: break
        if url in urls_seen: continue
        subs.append((name, url))
        urls_seen.add(url)
    return subs

def __GetSubtitleUrl(sub_url):
    return "http://subscene.com/%s" % sub_url.lstrip("/")

def DownloadSubtitle(sub_url):
    data = urllib.urlopen(__GetSubtitleUrl(sub_url)).read()
    matches = re.findall(__SUB_DOWNLOAD_LINK_RE, data)
    if len(matches) != 1:
        raise RuntimeError("Failed parsing subtitle html page.")
    sub_data_url = matches[0]

    request = urllib2.Request(__GetSubtitleUrl(sub_data_url))
    request.add_header('Accept-encoding', 'gzip')
    response = urllib2.urlopen(request)
    if response.info().get('Content-Encoding') == 'gzip':
        buf = StringIO(response.read())
        f = gzip.GzipFile(fileobj=buf)
        data = f.read()
    else:
        data = response.read()

    fname = response.info().get('Content-Disposition').split('filename=')[1]
    if re.search(__SUB_EXTENSIONS_RE, fname): return (fname, data)

    if not fname.lower().endswith('.zip'):
        raise NotImplementedError("Unsupported file: %s" % fname)
    
    buf = StringIO(data)
    zipf = zipfile.ZipFile(buf)
    fname = None
    # Picking the first subtitle found (if any).
    for fname in zipf.namelist():
        if re.search(__SUB_EXTENSIONS_RE, fname): break
    if not fname:
        raise RuntimeError("Could not find any subtitle in zip file.")
    data = zipf.read(fname)
    return (os.path.basename(fname), data)
    
    

if __name__ == "__main__":
    # print SearchSubtitlesForRelease("Silicon.Valley.S01E01.HDTV.x264-2HD")
    # DownloadSubtitle("/subtitles/silicon-valley-first-season/english/894763")
    pass