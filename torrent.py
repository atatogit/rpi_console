#!/usr/local/bin/python2.7

import os
from rtorrent_xmlrpc import SCGIServerProxy
import xmlrpclib

from html_utils import HtmlEscape
import torrent_logs
import utils

__STATES = ("CLOSED", "STARTED")

__rtorrent = SCGIServerProxy('scgi:///home/seba/rtorrent_session/socket')

__download_dir = "/mnt/big/rtorrent_downloads"

def PushLink(link):
    __rtorrent.load_start_verbose(link)

def DeleteTorrent(torrent_hash):
    __rtorrent.d.erase(torrent_hash)
    
def GetDownloadListHtml():
    data = __rtorrent.d.multicall(
        "", 
        "d.get_hash=", "d.get_name=", "d.get_state=", "d.get_size_bytes=",
        "d.get_bytes_done=", "d.get_down_rate=", "d.get_up_rate=")
    html = ['<table class="rtorrent_download_table"><tr>']
    columns = ["Name", "State", "Size", "Done", "Down (Kb/sec)", "Up (Kb/sec)",
               "Subtitles"]
    for c in columns: html.append("<th>%s</th>" % c)
    html.append("</tr>")
    for d in data:
        torrent_hash = HtmlEscape(d[0])
        name = HtmlEscape(d[1])
        state = __STATES[d[2]]
        size = HtmlEscape(utils.BytesToHuman(d[3]))
        done = HtmlEscape("%d%%" % ((100 * d[4]) / d[3] if d[3] else 0))
        down_rate = "%d" % (d[5] / 1024)
        up_rate = "%d" % (d[6] / 1024)
        subtitles = "Done" if torrent_logs.HasSubtitles(d[0]) else "Missing"
        html.append("<tr><td>")
        html.append("""\
<span style="float:left">%s</span>
<form action="/rtorrent" method="get" 
      onsubmit="return confirm('Are you sure you want to delete\\n%s?')">
<input type="submit" style="float:right" value="Delete">
<input type="hidden" name="h" value="%s">
<input type="hidden" name="delete" value="1">
</form>
<div style="clear:both">
<a class="rtorrent_table_link" href="subs?h=%s">Subs</a></div></td>
""" % (name, name, torrent_hash, torrent_hash))
        for c in (state, size, done, down_rate, up_rate, subtitles):
            html.append("<td>%s</td>" % c)
        html.append("</tr>")
    html.append("</table>")
    if not data: html.append("No torrents found.")
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
    #PushLink("http://re.zoink.it/2684774066")
    #print GetTorrentFiles("611BF69A7825FBDD0F5129D8CE976443E75EE530")
    pass
