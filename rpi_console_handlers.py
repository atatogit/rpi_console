#!/usr/bin/python

import cgi
import subprocess
import sys
import time
import urllib
import urlparse

import torrent

HTML_HEADER = """\
<html><head><title>Raspi Console</title>
<link rel='stylesheet' href='style.css' />
<link rel='icon' href='favicon.ico?v=2' type='image/x-icon' />
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
    return values[0]

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
            temp, cgi.escape(GetFreeMem()), cgi.escape(GetDf()), 
            cgi.escape(GetUsers())))
    html.extend(["</ul>", HTML_TAIL])
    return 200, "\n".join(html)

def TorrentHandler(parsed_path):
    html = [HTML_HEADER, HTML_TOC, "<h1>rTorrent Download List</h1>"]
    params = urlparse.parse_qs(parsed_path.query)
    link = ExtractParamValue(params, "link")
    success = ExtractParamValue(params, "success")
    try:
        if link is not None:
            torrent.PushLink(link)
            time.sleep(WAIT_TORRENT_PUSH_SECS)
            return 200, """<html><head>\
<meta http-equiv="refresh" content="0;url=rtorrent?success=1" /></head></html>"""
        elif success == "1":
            html.append("""\
Successfully pushed requested link. Note that there are no guarantees that
rTorrent picked up the link, so you must check that everything is fine.<br>""")
        html.append(torrent.GetDownloadListHtml())

    except Exception as e:
        html.append("""\
Oops. There has been an error. Please check below for the nature of the problem:
<br><PRE>%s</PRE><br>""" % cgi.escape(str(e)))

    return 200, "\n".join(html)


if __name__ == "__main__":
    print SysConsoleHandler("/")
    print SysActionMenuHandler("/sysactmenu")
