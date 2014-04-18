#!/usr/bin/python

import cgi
import os
from rtorrent_xmlrpc import SCGIServerProxy
import xmlrpclib

__STATES = ("CLOSED", "STARTED")

__rtorrent = SCGIServerProxy('scgi:///home/seba/rtorrent_session/socket')

__download_dir = "/mnt/big/rtorrent_downloads"

def __BytesToHuman(num):
    for x in ['bytes','KB','MB','GB']:
        if num < 1024.0 and num > -1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')
    
def PushLink(link):
    __rtorrent.load_start_verbose(link)
    
def GetDownloadListHtml():
    data = __rtorrent.d.multicall(
        "", 
        "d.get_hash=", "d.get_name=", "d.get_state=", "d.get_size_bytes=",
        "d.get_bytes_done=", "d.get_down_rate=", "d.get_up_rate=")
    html = ['<table class="rtorrent_download_table"><tr>']
    columns = ["Name", "State", "Size", "Done", "Down (Kb/sec)", "Up (Kb/sec)"]
    for c in columns: html.append("<th>%s</th>" % c)
    html.append("</tr>")
    for d in data:
        torrent_hash = cgi.escape(d[0])
        name = cgi.escape(d[1])
        state = __STATES[d[2]]
        size = cgi.escape(__BytesToHuman(d[3]))
        done = cgi.escape("%d%%" % ((100 * d[4]) / d[3] if d[3] else 0))
        down_rate = "%d" % (d[5] / 1024)
        up_rate = "%d" % (d[6] / 1024)
        html.append("<tr>")
        html.append("""\
<td><div>%s</div> <a class="rtorrent_table_link" href="subs?h=%s">Subs</a></td>
""" % (name, torrent_hash))
        for c in (state, size, done, down_rate, up_rate):
            html.append("<td>%s</td>" % c)
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)

def __BuildExecuteMethodOrNone(method):
    def ExecuteMethodOrNone(*args, **kargs):
        try:
            return method(*args, **kargs)
        except xmlrpclib.Fault as err:
            if err.faultCode == -501: return None
            raise        
    return ExecuteMethodOrNone

GetTorrentName = __BuildExecuteMethodOrNone(__rtorrent.d.get_name)
GetTorrentSizeFiles = __BuildExecuteMethodOrNone(__rtorrent.d.get_size_files)
__GetFilesData = __BuildExecuteMethodOrNone(__rtorrent.f.multicall)

def GetTorrentFiles(torrent_hash):
    is_multi_file = __rtorrent.d.is_multi_file(torrent_hash)
    pre_path = __rtorrent.d.get_name(torrent_hash) if is_multi_file else ""
    data = __GetFilesData(torrent_hash, "", "f.get_path=")
    if data is None: return None
    return [os.path.join(pre_path, f[0]) for f in data]
    

if __name__ == "__main__":
    print GetTorrentFiles("611BF69A7825FBDD0F5129D8CE976443E75EE530")
    pass
