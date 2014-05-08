#!/usr/bin/python

import datetime
import os
import subprocess
import sys
import time
import urlparse

from html_utils import HtmlEscape
import subscene
import torrent
import torrent_logs
import utils

HTML_HEADER = """\
<html><head><title>Raspi Console</title>
<link rel='stylesheet' href='style.css' />
<link rel='icon' href='favicon.ico?v=2' type='image/x-icon' />
<meta charset="UTF-8">
</head><body>"""

HTML_TAIL = "</body></html>"

HTML_TOC =  """\
<div class="toc">
Go to: <a href="/">Console</a>, <a href="/rtorrent">rTorrent List</a>,
<a href="/sysactmenu">Actions</a>
</div>"""

HTML_ACTIONS_TITLE = "<h1>Raspi System Action</h1>"

ACTION_TOLERANCE_SECS = 60

WAIT_TORRENT_PUSH_SECS = 1.0

WAIT_TORRENT_DELETE_SECS = 0.5

DOWNLOADS_DIR = "/mnt/wdtv/downloads/"

def GetOutputCmd(name="unknown", *args):
    def f():
        try:
            return subprocess.check_output(args)
        except:
            print >>sys.stdout, "Error getting %s" % name
            return "Error"
    return f

def ActionCmd(name="unknown", *args):
    def f():
        try:
            is_ok = (subprocess.call(args) == 0)
        except:
            is_ok = False
        if not is_ok: print >>sys.stdout, "Error executing %s" % name
        return is_ok
    return f
        
GetDf = GetOutputCmd("df", "/bin/df", "-h")
GetFreeMem = GetOutputCmd("free", "/usr/bin/free", "-h")
GetFreeMem = GetOutputCmd("free", "/usr/bin/free", "-h")
GetUsers = GetOutputCmd("w", "/usr/bin/w")
ActionShutdown = ActionCmd(
    "shutdown", "/usr/local/bin/sudo_shutdown", "-h", "now")
ActionRestart = ActionCmd(
    "shutdown", "/usr/local/bin/sudo_shutdown", "-r", "now")

def GetTemp():
    try:
        temp = open("/sys/class/thermal/thermal_zone0/temp").read().strip()
        return float(temp) / 1000.0
    except:
        print >>sys.stdout, "Error reading temperature"
        return None

def ExecuteShutdown():
    if ActionShutdown(): return "Raspi should be shutting down now!"
    return "Error shutting down raspi."

def ExecuteRestart():
    if ActionRestart(): return "Raspi should be restarting now!"
    return "Error restarting raspi."

def ExtractParamValue(params, name):
    values = params.get(name, [])
    if not values: return None
    try:
        value = str(values[0].decode('ascii'))
    except:
        value = values[0].decode('utf-8')
    return value

def ExecuteSystemActionAndGetHtml(params):
    try:
        ts = int(ExtractParamValue(params, "ts"))
    except:
        ts = 0
    ts_now = int(time.time())
    if ts <= 0 or ts > ts_now: return "Invalid time parameter."
    if ts_now - ts > ACTION_TOLERANCE_SECS: return "Expired request."
    action = ExtractParamValue(params, 'action')
    if action is None:
        return "No action specified. Nothing to do."
    if action == "restart":
        return ExecuteRestart()
    elif action == "shutdown":
        return ExecuteShutdown()
    else:
        return "Unknown action!"
    
def SysActionHandler(parsed_path):
    html = [HTML_HEADER, HTML_TOC, HTML_ACTIONS_TITLE, 
            ExecuteSystemActionAndGetHtml(urlparse.parse_qs(parsed_path.query)),
            HTML_TAIL]
    return 200, "\n".join(html)
    
def SysActionMenuHandler(parsed_path):
    html = [HTML_HEADER, HTML_TOC, HTML_ACTIONS_TITLE, """\
<form action='/sysact' method='get' 
    onsubmit='return confirm("Are you sure you want to perform that action?")'>
<input type='radio' name='action' value='restart'>Restart<br>
<input type='radio' name='action' value='shutdown'>Shutdown<br>
<input type='submit' value='Submit'>
<input type='hidden' name='ts' value='%d'>
</form>
You have at most %d seconds since you load the page to make your selection. If
necessary, please reload the page.""" % (int(time.time()), 
                                         ACTION_TOLERANCE_SECS),
            HTML_TAIL]
    return 200, "\n".join(html)

def SysConsoleHandler(parsed_path):
    html = [HTML_HEADER, HTML_TOC, "<h1>Raspi Console</h1><ul>"]
    temp = GetTemp()
    temp = "%.2f" % temp if temp is not None else "Error"
    html.append("""\
<li><b>Core temperature:</b> %s &#176;C</li>
<li><b>Memory info:</b><PRE>%s</PRE></li>
<li><b>Free space in mounts:</b><PRE>%s</PRE></li>
<li><b>Uptime + Users:</b><PRE>%s</PRE></li>""" % (
            temp, HtmlEscape(GetFreeMem()), HtmlEscape(GetDf()), 
            HtmlEscape(GetUsers())))
    html.extend(["</ul>", HTML_TAIL])
    return 200, "\n".join(html)

def __ExceptionToHtml(e):
    return """<br><br>\
Oops. There has been an error. Please check below for the nature of the problem:
<br><PRE>%s</PRE><br>""" % HtmlEscape(str(e))
    
def TorrentHandler(parsed_path):
    html = [HTML_HEADER, HTML_TOC, "<h1>rTorrent Download List</h1>",
            "<a href='/rtorrentlogs?list=1'>Go to history</a>"]
    params = urlparse.parse_qs(parsed_path.query)
    link = ExtractParamValue(params, "link")
    success = ExtractParamValue(params, "success")
    torrent_hash = ExtractParamValue(params, "h")
    delete_torrent = ExtractParamValue(params, "delete")
    try:
        if link is not None:
            torrent.PushLink(link)
            time.sleep(WAIT_TORRENT_PUSH_SECS)
            return 200, """<html><head>\
<meta http-equiv="refresh" content="0;url=rtorrent?success=1" /></head></html>"""
        if torrent_hash is not None and delete_torrent == "1":
            torrent.DeleteTorrent(torrent_hash)
            time.sleep(WAIT_TORRENT_DELETE_SECS)
            return 200, """<html><head>\
<meta http-equiv="refresh" content="0;url=rtorrent" /></head></html>"""
        if success == "1":
            # Consider presenting some confirmation message.
            pass

        html.append(torrent.GetDownloadListHtml())

    except Exception as e:
        html.append(__ExceptionToHtml(e))

    html.append(HTML_TAIL)
    return 200, "\n".join(html)

def __TimestampToHuman(ts):
  return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def GetTorrentLogsList(torrent_hash, name_query):
    html = [HTML_HEADER, HTML_TOC, "<h1>rTorrent Download History</h1>"]
    html.append("""\
<form action="/rtorrentlogs" method="get">
Name: <input type="text" name="name_query" value="%s">
<input type="image" src="magnifier.png" style="vertical-align:middle"
       width="24px" height="24px"> 
<input type="hidden" name="list" value="1">
""" % (HtmlEscape(name_query) if name_query else ""))
    html.append('<table class="rtorrent_download_table"><tr>')
    columns = ["Name", "Download", "Download Time", "Subtitles"]
    for c in columns: html.append("<th>%s</th>" % c)
    html.append("</tr>")
    data = torrent_logs.GetTorrentsLogTable(name_query=name_query)
    for d in data:
        torrent_hash = HtmlEscape(d[0])
        name = HtmlEscape(d[1] or 'Unknown')
        download_start = HtmlEscape(__TimestampToHuman(d[2])) if d[2] else "None"
        duration = utils.SecsToHuman(d[3]) if d[3] is not None else "Incomplete"
        subtitles_date = HtmlEscape(__TimestampToHuman(d[4])) if d[4] else "None"
        html.append("<tr>")
        for c in (name, download_start, duration, subtitles_date):
            html.append("<td>%s</td>" % c)
        html.append("</tr>")
    html.append("</table>")
    if not data: html.append("No torrents found.")

    html.append(HTML_TAIL)
    return 200, "\n".join(html)

def TorrentLogsHandler(parsed_path):
    params = urlparse.parse_qs(parsed_path.query)
    torrent_hash = ExtractParamValue(params, "h")
    list_param = ExtractParamValue(params, "list")
    if list_param == '1':
        name_query = ExtractParamValue(params, "name_query")
        return GetTorrentLogsList(torrent_hash, name_query)

    event_type = ExtractParamValue(params, "type")
    if event_type is None or torrent_hash is None:
        return 400, "Missing event type or torrent hash"
    
    if event_type == "insert":
        name = ExtractParamValue(params, "name")
        if name is None or name == torrent_hash + ".meta":
            return 200, "No name, just ignored"
        torrent_logs.AddTorrent(torrent_hash, name)
        torrent_logs.AddTorrentEvent(
            torrent_logs.EventType.download_start, torrent_hash)
        return 200, "Torrent added"
    elif event_type == "finished":
        torrent_logs.AddTorrentEvent(
            torrent_logs.EventType.download_finish, torrent_hash)
        return 200, "Torrent finish event logged."
    return 400, "Unsuported event type"

def SearchSubsHandler(torrent_hash, name, html, max_num_subs_or_none=None):
    release = subscene.TorrentNameToRelease(name)
    html.append("<div><b>Release:</b> %s</div>" % HtmlEscape(release))
    movie_files = subscene.GetMovieFiles(
        torrent.GetTorrentFiles(torrent_hash), release)
    if not movie_files:
        html.extend(["Failed to identify movie candidates.", HTML_TAIL])
        return
    # Using movie file most similar to the release.
    movie_file = movie_files[0]
    html.append("<div><b>Movie file:</b> %s" % HtmlEscape(movie_file))
    movie_file_no_ext = os.path.basename(movie_file)[:-4]
    sub_list = subscene.SearchSubtitlesForRelease(
        release, movie_file_no_ext, max_num_subs_or_none)
    if not sub_list:
        html.extend(["<br>No subtitles found...", HTML_TAIL])
        return
    html.append("<div><b>Subtitles:</b></div>")
    html.append("<div><form action='/subs' method='get'>")
    for i, s in enumerate(sub_list):
        esc_url = HtmlEscape(s[1])
        esc_name = HtmlEscape(s[0])
        esc_full_url = HtmlEscape(subscene.GetSubtitleUrl(s[1]))
        html.append("""\
<input type='radio' name='suburl' value='%s' %s>%s
<a href='%s' target='_blank'>Go to sub page</a><br>""" % (
                esc_url, "checked" if i == 0 else "", esc_name, esc_full_url))
                     
    html.append("""\
<input type='submit' value='Download selected subtitle'>
<input type='hidden' name='h' value='%s'>
<input type='hidden' name='moviefile' value='%s'>""" % (
            HtmlEscape(torrent_hash), HtmlEscape(movie_file)))
    html.append("</form></div>")

def DownloadSubHandler(torrent_hash, sub_url, movie_file, html):
    if len(movie_file) < 5 or movie_file[-4] != '.':
        html.append("Bad movie file (not a movie?): " % HtmlEscape(movie_file))
        return
    movie_file = os.path.join(DOWNLOADS_DIR, movie_file)
    base_dir = os.path.dirname(movie_file)
    movie_file_noext = movie_file[:-4]
    sub_fname, sub_data = subscene.DownloadSubtitle(sub_url)
    if len(sub_fname) < 5 or sub_fname[-4] != '.':
        html.append("Bad subtitle file name: " % HtmlEscape(sub_fname))
        return    
    sub_file = "%s.%s" % (movie_file_noext, sub_fname[-3:])
    if base_dir and not os.path.exists(base_dir): os.makedirs(base_dir)
    f = open(sub_file, "w")
    f.write(sub_data)
    f.close()
    log_data = { "sub_url": sub_url }
    torrent_logs.AddTorrentEvent(
        torrent_logs.EventType.subtitles, torrent_hash, log_data)
    html.append("Successfully written %s." % HtmlEscape(sub_file))

def SubsHandler(parsed_path):
    html = [HTML_HEADER, HTML_TOC, "<h1>Subtitles Manager</h1>"]
    params = urlparse.parse_qs(parsed_path.query)
    torrent_hash = ExtractParamValue(params, "h")
    if not torrent_hash:
        html.extend(["No torrent hash specified in 'h' parameter.", HTML_TAIL])
        return 200, "\n".join(html)
    sub_url = ExtractParamValue(params, "suburl")

    try:
        name = torrent.GetTorrentName(torrent_hash)
        if not name:
            html.extend(["Specified torrent hash not found.", HTML_TAIL])
            return 200, "\n".join(html)
        html.append("<h2>%s</h2>" % HtmlEscape(name))

        if not sub_url:
            max_num_subs = ExtractParamValue(params, "max_num_subs")
            if max_num_subs is not None: max_num_subs = int(max_num_subs)
            SearchSubsHandler(torrent_hash, name, html, max_num_subs)
        else:
            movie_file = ExtractParamValue(params, "moviefile")
            if not movie_file:
                html.append("No movie file specified.")
            else:
                DownloadSubHandler(torrent_hash, sub_url, movie_file, html)

    except Exception as e:
        html.append(__ExceptionToHtml(e))

    html.append(HTML_TAIL)
    return 200, "\n".join(html)


if __name__ == "__main__":
    print SysConsoleHandler("/")
    print SysActionMenuHandler("/sysactmenu")
