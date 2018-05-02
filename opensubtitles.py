#!/usr/local/bin/python2.7

import Queue
from StringIO import StringIO
import atexit
from base64 import b64decode, b64encode
import gzip
import json
import threading
import xmlrpclib

from subtitles_score import ScoreSubtitleMatch


_OPENSUBS_URL = "https://api.opensubtitles.org:443/xml-rpc"

_OK_STATUS = "200 OK"

# Expected to be like
# {
#   "username": "<username>",
#   "password": "<password>"
# }
_CREDS_FILE = 'opensubtitles_config.json'


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


class PooledOpenSubtitlesSession(object):
    def __init__(self, pool):
        self._pool = pool

    def __enter__(self):
        self._session = self._pool.Get();
        return self._session

    def __exit__(self, exception_type, exception_value, traceback):
        self._pool.Return(self._session)


class OpenSubtitlesSessionPool(object):
    def __init__(self, username, password, num_sessions=2):
        self._username = username
        self._password = password
        self._num_sessions = num_sessions
        self._num_created_sessions = 0
        self._sessions = []
        self._sessions_available = threading.Condition()

    def Get(self):
        self._sessions_available.acquire()
        while not self._sessions:
            if self._num_created_sessions < self._num_sessions:
                self._sessions.append(
                    OpenSubtitlesSession(self._username, self._password))
                self._num_created_sessions += 1
                break
            else:
                self._sessions_available.wait()
        session = self._sessions.pop()
        self._sessions_available.release()
        return session

    def Return(self, session):
        self._sessions_available.acquire()
        self._sessions.append(session)
        self._sessions_available.notify()
        self._sessions_available.release()

    def Close(self):
        self._sessions_available.acquire()
        while len(self._sessions) != self._num_sessions:
            self._sessions_available.wait()
        for session in self._sessions:
            try:
                session.close()
            except:
                pass
        del self._sessions[:]
        self._num_created_sessions = 0
        self._sessions_available.release()
        

class OpenSubtitlesSession(object):
    def __init__(self, username, password):
        self._server = xmlrpclib.ServerProxy(_OPENSUBS_URL)
        resp = self._server.LogIn(username, password, "en",
                                  "TemporaryUserAgent")
        if resp["status"] != _OK_STATUS:
            raise OpenSubtitlesException(
                "Failed logging into OpenSubtitles: %s" % resp["status"])
        self._token = resp["token"]

    def close(self):
        resp = self._server.LogOut(self._token)
        if resp["status"] != _OK_STATUS:
            raise OpenSubtitlesException(
                "Failed closing OpenSubtitles session: %s" % resp["status"])

    def search(self, query, max_num_subs):
        resp = self._server.SearchSubtitles(
            self._token,
            [{"query": query, "sublanguageid": "eng"}],
            {"limit": max_num_subs})
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
        resp = self._server.DownloadSubtitles(self._token,
                                              [id_subtitle_file])
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
        

def _SearchSubtitlesForQuery(query, max_num_subs, queue):
    try:
        with PooledOpenSubtitlesSession(_session_pool) as session:
            queue.put(session.search(query, max_num_subs))
    except Exception as e:
        queue.put(e)


def SearchSubtitlesForRelease(release, movie_file, max_num_subs=10):
    queue = Queue.Queue()
    for query in (release, movie_file):
        t = threading.Thread(target=_SearchSubtitlesForQuery,
                             args=(query, max_num_subs, queue))
        t.daemon = True
        t.start()
    thread_results = (queue.get(), queue.get())
    scored_matches = []
    for result in thread_results:
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
    with PooledOpenSubtitlesSession(_session_pool) as session:
        return (sub_filename, session.download(sub_id))


def _ReadConfigFromFile():
    with open(_CREDS_FILE) as f:
        data = json.load(f)
        return data["username"], data["password"]


_session_pool = OpenSubtitlesSessionPool(*_ReadConfigFromFile())


@atexit.register
def _CloseSessions():
    global _session_pool
    _session_pool.Close()


if __name__ == "__main__":
    #print SearchSubtitlesForRelease(
    #    "Billions.S01E01.HDTV.XviD-FUM[ettv]",
    #    "Billions.S01E01.HDTV.XviD-FUM[ettv]")
    #print SearchSubtitlesForRelease(
    #    "The.Americans.2013.S06E05.HDTV.x264-SVA",
    #    "The.Americans.2013.S06E05.HDTV.x264-SVA[rarbg]")
    print SearchSubtitlesForRelease(
        "www.Torrenting.com - American.Gods.S01E08.HDTV.x264-FLEET",
        "www.Torrenting.com - American.Gods.S01E08.HDTV.x264-FLEET")
    # print len(DownloadSubtitle("1955037593"))
