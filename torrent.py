#!/usr/bin/python

import cgi
from rtorrent_xmlrpc import SCGIServerProxy

__STATES = ("CLOSED", "STARTED")

__rtorrent = SCGIServerProxy('scgi:///home/seba/rtorrent_session/socket')

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
        "d.get_name=", "d.get_state=", "d.get_size_bytes=", "d.get_bytes_done=", 
        "d.get_down_rate=", "d.get_up_rate=")
    html = ['<table class="rtorrent_download_table"><tr>']
    columns = ["Name", "State", "Size", "Done", "Down (Kb/sec)", "Up (Kb/sec)"]
    for c in columns: html.append("<th>%s</th>" % c)
    html.append("</tr>")
    for d in data:
        name = cgi.escape(d[0])
        state = __STATES[d[1]]
        size = cgi.escape(__BytesToHuman(d[2]))
        done = cgi.escape("%d%%" % ((100 * d[3]) / d[2] if d[2] else 0))
        down_rate = "%d" % (d[4] / 1024)
        up_rate = "%d" % (d[5] / 1024)
        html.append("<tr>")
        for c in (name, state, size, done, down_rate, up_rate):
            html.append("<td>%s</td>" % c)
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)

if __name__ == "__main__":
    pass
