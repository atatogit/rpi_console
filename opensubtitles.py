#!/usr/bin/python

import Queue
from StringIO import StringIO
import atexit
from base64 import b64decode, b64encode
import gzip
import json
import os
import struct
import threading
from time import sleep, time
import xmlrpclib

from subtitles_score import ScoreSubtitleMatch


_OPENSUBS_URL = "https://api.opensubtitles.org:443/xml-rpc"

_SESSION_EXPIRY_SECS = 60 * 15  # 14 minutes.

_OK_STATUS = "200 OK"

_NO_SESSION_STATUS = "406 No session"

_UNAUTHORIZED_STATUS = "401 Unauthorized"

_RELOGIN_STATUSES = (_NO_SESSION_STATUS, _UNAUTHORIZED_STATUS)

_MAX_NUM_RETRIES = 5

_SLEEP_BETWEEN_RETRIES_SECS = 1

# Expected to be like
# {
#   "username": "<username>",
#   "password": "<password>"
# }
_CREDS_FILE = '/usr/local/bin/rpi_console/opensubtitles_config.json'


def HashFile(name): 
    longlongformat = '<q'  # little-endian long long
    bytesize = struct.calcsize(longlongformat) 
    f = open(name, "rb") 
    filesize = os.path.getsize(name) 
    hash = filesize 
    assert filesize >= 65536 * 2
    for x in range(65536/bytesize): 
        buffer = f.read(bytesize) 
        (l_value,)= struct.unpack(longlongformat, buffer)  
        hash += l_value 
        hash = hash & 0xFFFFFFFFFFFFFFFF # to remain as 64bit number  
    f.seek(max(0,filesize-65536),0) 
    for x in range(65536/bytesize): 
        buffer = f.read(bytesize) 
        (l_value,)= struct.unpack(longlongformat, buffer)  
        hash += l_value 
        hash = hash & 0xFFFFFFFFFFFFFFFF 
                
    f.close() 
    returnedhash =  "%016x" % hash 
    return returnedhash 


def _EncodeIDAndFilename(sub_id, filename):
    return "%s.%s" % (b64encode(sub_id), b64encode(filename))


def _DecodeIDAndFilename(encoded):
    encoded_sub_id, encoded_filename = encoded.split(".")
    return b64decode(encoded_sub_id), b64decode(encoded_filename)


class OpenSubtitlesException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class OpenSubtitlesChannel(object):
    def __init__(self):
        self._server = xmlrpclib.ServerProxy(_OPENSUBS_URL)

    def __enter__(self):
        return self._server

    def __exit__(self, type, value, traceback):
        self._server.close()
        

class OpenSubtitlesSession(object):
    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._token = None

    def _login(self, channel):
        if self._token:
            raise OpenSubtitlesException(
                "Attempting to login without having closed")

        last_login_time = time()
        resp = channel.LogIn(
            self._username, self._password, "en", "TemporaryUserAgent")
        if resp["status"] != _OK_STATUS:
            raise OpenSubtitlesException(
                "Failed logging into OpenSubtitles: %s" % resp["status"])
        self._token = resp["token"]
        self._login_expiry_time = last_login_time + _SESSION_EXPIRY_SECS
        
    def _call(self, channel, method, args):
        if not self._token:
            self._login(channel)
        elif time() > self._login_expiry_time:
            status = channel.NoOperation(self._token)["status"]
            if status != _OK_STATUS:
                if status not in _RELOGIN_STATUSES:
                    raise OpenSubtitlesException(
                        "Failed NoOperation: %s" % status)
                self._try_close_and_login(channel)

        attempt = 0
        while True:
            attempt += 1
            method_time = time()
            resp = method(self._token, *args)
            status = resp["status"]
            if status == _OK_STATUS:
                self._login_expiry_time = method_time + _SESSION_EXPIRY_SECS
                break
            if attempt >= _MAX_NUM_RETRIES:
                break
            sleep(_SLEEP_BETWEEN_RETRIES_SECS)
            if status in _RELOGIN_STATUSES:
                self._try_close_and_login(channel)

        return resp
                    
    def _try_close_and_login(self, channel):
        try:
            self.close(channel)
        except OpenSubtitlesException as e:
            # Ignoring the failed attempt to close.
            pass
        self._login(channel)

    def close(self, channel=None):
        if not self._token:
            return
        if channel is not None:
            self._close_with_channel(channel)
        else:
            with OpenSubtitlesChannel() as channel:
                self._close_with_channel(channel)

    def _close_with_channel(self, channel):
        resp = channel.LogOut(self._token)
        self._token = None
        if resp["status"] != _OK_STATUS:
            raise OpenSubtitlesException(
                "Failed closing OpenSubtitles session: %s" % resp["status"])

    def search(self, queries, max_num_subs):
        with OpenSubtitlesChannel() as channel:
            resp = self._call(channel,
                              channel.SearchSubtitles,
                              [queries,  {"limit": max_num_subs}])
        # print resp
        if resp["status"] != _OK_STATUS:
            raise OpenSubtitlesException(
                "Failed searching OpenSubtitles: %s" % resp["status"])
        subs = []
        matches = resp.get("data")
        if not matches:
            return subs
        for match in matches:
            release_name = match.get("MovieReleaseName")
            subtitle_url = match.get("SubtitlesLink")
            id_subtitle_file = match.get("IDSubtitleFile")
            subtitle_filename = match.get("SubFileName")
            if (not release_name or not subtitle_url or
                not id_subtitle_file or not subtitle_filename):
                print >>sys.stdout, "Result missing needed data:", match
                continue
            subs.append((release_name.encode("utf-8"),
                         id_subtitle_file.encode("utf-8"), 
                         subtitle_filename.encode("utf-8"),
                         subtitle_url.encode("utf-8")))
        return subs

    def download(self, id_subtitle_file):
        with OpenSubtitlesChannel() as channel:
            resp = self._call(channel, channel.DownloadSubtitles,
                              [[id_subtitle_file]])
        if resp["status"] != _OK_STATUS:
            raise OpenSubtitlesException(
                "Failed downloading from OpenSubtitles: %s" % resp["status"])
        downloads = resp.get("data")
        if not downloads:
            raise OpenSubtitlesException("No subtitles returned")
        if len(downloads) != 1:
            print >>sys.stdout, "More than one subtitles returned"
        data = downloads[0].get("data")
        if not data:
            raise OpenSubtitlesException("Missing subtitles data")
        try:
            gz_data = b64decode(data)
        except Exception as e:
            raise OpenSubtitlesException(
                "Error decoding subtitles: %s" % repr(e))
        try:
            return gzip.GzipFile(fileobj=StringIO(gz_data)).read()
        except Exception as e:
            raise OpenSubtitlesException(
                "Error gunziping subtitles: %s" % repr(e))
        

def _SearchSubtitlesForHash(movie_size, movie_hash, max_num_subs):
    open_subtitles_query = [{"moviehash": movie_hash, "moviebytesize": movie_size,
                             "sublanguageid": "eng"}]
    return _session.search(open_subtitles_query, max_num_subs)


def _SearchSubtitlesForQuery(query, max_num_subs, queue):
    open_subtitles_query = [{"query": query, "sublanguageid": "eng"}]
    try:
        queue.put(_session.search(open_subtitles_query, max_num_subs))
    except Exception as e:
        queue.put(e)


def SearchSubtitlesForRelease(release, movie_file, movie_size=None,
                              movie_hash=None, max_num_subs=10):
    all_results = []
    if movie_size and movie_hash:
        all_results.append(
            _SearchSubtitlesForHash(movie_size, movie_hash, max_num_subs))
    if not all_results:
        queue = Queue.Queue()
        for query in (release, movie_file):
            t = threading.Thread(target=_SearchSubtitlesForQuery,
                                 args=(query, max_num_subs, queue))
            t.daemon = True
            t.start()
        thread_results = (queue.get(), queue.get())
        all_results.extend(thread_results)
    scored_matches = []
    for result in all_results:
        if isinstance(result, Exception):
            raise result
        scored_matches.extend((min(ScoreSubtitleMatch(release, sub[0]),
                                   ScoreSubtitleMatch(movie_file, sub[0])),
                               sub) for sub in result)
    scored_matches.sort()
    sub_ids_seen = set()
    subs = []
    for score, (name, sub_id, sub_filename, url) in scored_matches:
        if len(subs) >= max_num_subs: break
        if sub_id in sub_ids_seen: continue
        encoded_sub_id_and_filename = _EncodeIDAndFilename(
            sub_id, sub_filename)
        subs.append((name, encoded_sub_id_and_filename, url, score))
        sub_ids_seen.add(sub_id)
    return subs


def DownloadSubtitle(encoded_sub_id_and_filename):
    sub_id, sub_filename = _DecodeIDAndFilename(
        encoded_sub_id_and_filename)
    return (sub_filename, _session.download(sub_id))


def _ReadConfigFromFile():
    with open(_CREDS_FILE) as f:
        data = json.load(f)
        return data["username"], data["password"]


_session = OpenSubtitlesSession(*_ReadConfigFromFile())


@atexit.register
def _CloseSessions():
    _session.close()


if __name__ == "__main__":
    print SearchSubtitlesForRelease(
        "Billions.S01E01.HDTV.XviD-FUM[ettv]",
        "Billions.S01E01.HDTV.XviD-FUM[ettv]")
    #print SearchSubtitlesForRelease(
    #    "The.Americans.2013.S06E05.HDTV.x264-SVA",
    #    "The.Americans.2013.S06E05.HDTV.x264-SVA[rarbg]")
    #print SearchSubtitlesForRelease(
    #    "www.Torrenting.com - American.Gods.S01E08.HDTV.x264-FLEET",
    #    "www.Torrenting.com - American.Gods.S01E08.HDTV.x264-FLEET")
    #print SearchSubtitlesForRelease(
    #    "the.handmaids.tale.s01e10.xvid-afg",
    #    "the.handmaids.tale.s01e10.xvid-afg")
    
    # print len(DownloadSubtitle("1955037593"))

    #print HashFile(r"/mnt/wdtv/downloads/The.Americans.2013.S06E05.HDTV.x264-SVA[rarbg]/The.Americans.2013.S06E05.HDTV.x264-SVA.mkv")
