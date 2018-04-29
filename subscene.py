#!/usr/local/bin/python2.7

import Queue
from StringIO import StringIO
import gzip
import os
import re
import threading
import unicodedata
import urllib
import urllib2
import zipfile

from subtitles_score import ScoreSubtitleMatch


__SUB_EXTENSIONS = set((".sub", ".srt"))

__SUB_EXTENSIONS_RE = re.compile("(%s)$" % "|".join(
        map(lambda s: s.replace(".", r"\."), __SUB_EXTENSIONS)), re.IGNORECASE)

__SUB_LIST_ENTRY_RE = re.compile(
    'href="(/subtitles/[^/]*/english/[^"]*)"' +
    '[^<]*<span[^<]*</span[^<]*<span[^>]*>([^<]*)</span')

__SUB_DOWNLOAD_LINK_RE = re.compile(
    '<div class="download".*?href="(/subtitles/[^"]*)"', re.DOTALL)

__USER_AGENT = ('Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) '
                'Gecko/20071127 Firefox/2.0.0.11')

url_opener = urllib2.build_opener()
url_opener.addheaders = [('User-agent', __USER_AGENT)]

# Requires: "release" is ASCII.
def __GetSearchReleaseUrl(release):
    return "https://subscene.com/subtitles/release?q=%s" % urllib.quote(release)

# Searches "query" in subscene, parses out subtitles, and puts them scored into
# "queue".
# Requires: "query" is ASCII.
def __SearchSubtitlesForQuery(query, queue):
    try:
        print "Opening: ", __GetSearchReleaseUrl(query)
        data = url_opener.open(__GetSearchReleaseUrl(query)).read()
        print "done."
        matches = re.findall(__SUB_LIST_ENTRY_RE, data)
        if not matches: 
            queue.put([])
            return
        stripped_matches = [(m[1].strip(), m[0].strip()) for m in matches]
        scored_matches = [(ScoreSubtitleMatch(query, m[0]), m)
                          for m in stripped_matches]
        queue.put(scored_matches)
    except Exception as e:
        queue.put(e)
        return

def __GetSubtitleUrl(sub_url):
    return "https://subscene.com/%s" % sub_url.lstrip("/")

def SearchSubtitlesForRelease(release, movie_file, max_num_subs):
    queue = Queue.Queue()
    for query in (release, movie_file):
        if type(query) == unicode:
            query = unicodedata.normalize('NFKD', query).encode('ascii', 'ignore')
        # It seems multiple concurrent queries are rejected with error 409 :-(
        if True:
            __SearchSubtitlesForQuery(query, queue)
        else:
            t = threading.Thread(target=__SearchSubtitlesForQuery, args=(query, queue))
            t.daemon = True
            t.start()
    thread_results = (queue.get(), queue.get())
    scored_matches = []
    for result in thread_results:
        if isinstance(result, Exception): raise result
        scored_matches.extend(result)
    scored_matches.sort()
    urls_seen = set()
    subs = []
    for score, (name, url) in scored_matches:
        if len(subs) >= max_num_subs: break
        if url in urls_seen: continue
        subs.append((name, url, __GetSubtitleUrl(url), score))
        urls_seen.add(url)
    return subs

def DownloadSubtitle(sub_url):
    data = url_opener.open(GetSubtitleUrl(sub_url)).read()
    matches = re.findall(__SUB_DOWNLOAD_LINK_RE, data)
    if len(matches) != 1:
        raise RuntimeError("Failed parsing subtitle html page.")
    sub_data_url = matches[0]

    request = urllib2.Request(GetSubtitleUrl(sub_data_url))
    request.add_header('User-agent', __USER_AGENT)
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
    print SearchSubtitlesForRelease("Halt.and.Catch.Fire.S01E07.HDTV.x264-ASAP",
                                    "Halt.and.Catch.Fire.S01E07.HDTV.x264-ASAP")
    # DownloadSubtitle("/subtitles/silicon-valley-first-season/english/894763")
    pass
