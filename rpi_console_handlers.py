#!/usr/local/bin/python2.7

import datetime
import os
import subprocess
import sys
import time
import urllib
import urlparse

from html_utils import HtmlEscape
import router_logs
import subtitles
import torrent
import torrent_logs
import sensors_logs
import utils

HTML_HEADER_BEGIN = """\
<html><head><title>Raspi Console</title>
<link rel='stylesheet' href='style.css' />
<link rel='icon' href='favicon.ico?v=2' type='image/x-icon' />
<meta charset="UTF-8">"""

HTML_HEADER_END = "</head><body>"

HTML_HEADER = HTML_HEADER_BEGIN + HTML_HEADER_END

HTML_TAIL = "</body></html>"

HTML_TOC =  """\
<div class="toc">
Go to:
<a accesskey="c" href="/">Console</a>,
<a accesskey="t" href="/rtorrent">rTorrent List</a>,
<a accesskey="r" href="/router">Router</a>,
<a accesskey="a" href="/sysactmenu">Actions</a>,
<a accesskey="s" href="/viewsensors">Sensors</a>
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
            "<div class='rtorrent_history_link'><a "
            "href='/rtorrentlogs?list=1'>Go to history</a></div>"]
    params = urlparse.parse_qs(parsed_path.query)
    link = ExtractParamValue(params, "link")
    torrent_hash = ExtractParamValue(params, "h")
    delete_torrent = ExtractParamValue(params, "delete")
    try:
        if link is not None:
            torrent.PushLink(link)
            time.sleep(WAIT_TORRENT_PUSH_SECS)
            return 200, """<html><head>\
<meta http-equiv="refresh" content="0;url=rtorrent" /></head></html>"""
        if torrent_hash is not None and delete_torrent == "1":
            torrent.DeleteTorrent(torrent_hash)
            time.sleep(WAIT_TORRENT_DELETE_SECS)
            return 200, """<html><head>\
<meta http-equiv="refresh" content="0;url=rtorrent" /></head></html>"""

        html.append("""\
<div>
<form action="/rtorrent" method="get">
<input type="text" name="link" value="">
<input type="submit" value="Add torrent">
</form>
</div>""")
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
        movie_size = ExtractParamValue(params, "movie_size")
        opensubtitles_hash = ExtractParamValue(params, "opensubtitles_hash")
        if movie_size and opensubtitles_hash:
            torrent_logs.UpdateTorrentSizeAndOpenSubtitlesHash(
                torrent_hash, movie_size, opensubtitles_hash)
        return 200, "Torrent finish event logged."
    return 400, "Unsuported event type"


def SearchSubsHandler(
    params, torrent_hash, name, html, max_num_subs_or_none=None):
    release = subtitles.TorrentNameToRelease(name)
    html.append("<div><b>Release:</b> %s</div>" % HtmlEscape(release))
    movie_files = subtitles.GetMovieFiles(
        torrent.GetTorrentFiles(torrent_hash), release)
    if not movie_files:
        html.extend(["Failed to identify movie candidates.", HTML_TAIL])
        return
    # Using movie file most similar to the release.
    movie_file = movie_files[0]
    html.append("<div><b>Movie file:</b> %s" % HtmlEscape(movie_file))
    movie_file_no_ext = os.path.basename(movie_file)[:-4]
    movie_size,  opensubtitles_hash = \
        torrent_logs.GetTorrentSizeAndOpenSubtitlesHash(torrent_hash)
    sub_list = subtitles.SearchSubtitlesForRelease(
        release, movie_file_no_ext, movie_size=movie_size,
        opensubtitles_hash=opensubtitles_hash,
        max_num_subs=max_num_subs_or_none)
    if not sub_list:
        html.extend(["<br>No subtitles found...", HTML_TAIL])
        return
    html.append("<div><b>Subtitles:</b></div>")
    html.append("<div><form action='/subs' method='get'>")
    for i, s in enumerate(sub_list):
        esc_name, esc_url, esc_full_url, score = (
            HtmlEscape(s[0]), HtmlEscape(s[1]), HtmlEscape(s[2]), s[3])
        html.append("""\
<input type='radio' name='suburl' value='%s' %s>%s (%d)
<a href='%s' target='_blank'>Go to sub page</a><br>""" % (
                esc_url, "checked" if i == 0 else "",
                esc_name, score,
                esc_full_url))
    html.append("""\
<input type='submit' value='Download selected subtitle'>
<input type='hidden' name='h' value='%s'>
<input type='hidden' name='moviefile' value='%s'>""" % (
            HtmlEscape(torrent_hash), HtmlEscape(movie_file)))
    html.append("</form></div>")
    max_num_subs = params.get("max_num_subs", [-1])
    if not max_num_subs or max_num_subs[0] < 1000:
        new_params = params.copy()
        new_params["max_num_subs"] = [1000]
        more_subs_url = "?%s" % urllib.urlencode(new_params, doseq=True)
        html.append(
            "<div><a href='%s'>Try to retrieve more subtitles</a></div>" %
            more_subs_url)


def DownloadSubHandler(torrent_hash, sub_url, movie_file, html):
    if len(movie_file) < 5 or movie_file[-4] != '.':
        html.append("Bad movie file (not a movie?): " % HtmlEscape(movie_file))
        return
    movie_file = os.path.join(DOWNLOADS_DIR, movie_file)
    base_dir = os.path.dirname(movie_file)
    movie_file_noext = movie_file[:-4]
    sub_fname, sub_data = subtitles.DownloadSubtitle(sub_url)
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
            SearchSubsHandler(params, torrent_hash, name, html, max_num_subs)
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


def __GetRouterDevicesTable():
    html = []
    html.append('<table class="router_devices_table"><tr>')
    columns = ["Name", "Hostname", "MAC", "IP", "Last Activity"]
    for c in columns: html.append("<th>%s</th>" % c)
    html.append("</tr>")
    data = router_logs.GetDevicesList()
    for d in data:
        name = HtmlEscape(d[0]) if d[0] else \
            "<span style='color:red'>NEW DEVICE</span>"
        hostname = HtmlEscape(d[1] or "Unknown")
        mac = HtmlEscape(d[2])
        ip = HtmlEscape(d[3] or "Unknown")
        last_date = HtmlEscape(__TimestampToHuman(d[4])) if d[2] else "Unknown"
        html.append("<tr>")
        for c in (name, hostname, mac, ip, last_date):
            html.append("<td>%s</td>" % c)
        html.append("</tr>")
    html.append("</table>")
    if not data: html.append("No devices found.")
    return "\n".join(html)


def RouterLogsHandler(parsed_path):
    html = [HTML_HEADER, HTML_TOC, "<h1>Router Devices</h1>"]
    try:
        html.append(__GetRouterDevicesTable())

    except Exception as e:
        html.append(__ExceptionToHtml(e))

    html.append(HTML_TAIL)
    return 200, "\n".join(html)
    

def SensorsHandler(parsed_path):
    params = urlparse.parse_qs(parsed_path.query)
    sensor_type = ExtractParamValue(params, "type")
    if sensor_type is None:
        return 400, "'type' must be provided"
    if sensor_type.lower() != "dht22":
        return 501, "Unsuported sensor type (only dht22 is supported)"
    try:
        sensor_id = int(ExtractParamValue(params, "id"))
        if sensor_id <= 0:
            return 400, "id must be larger than zero"
    except:
        return 400, "'id' must be an integer larger than zero"
    try:
        ts_secs = int(ExtractParamValue(params, "ts"))
        if ts_secs < 0:
            return 400, "'ts' must not be negative"
    except:
        return 400, "'ts' must be a valid timestamp"
    try:
        temp_c = float(ExtractParamValue(params, "temp_c"))
    except:
        return 400, "'temp_c' must be a valid temperature"
    try:
        humidity_perc = float(ExtractParamValue(params, "hum_perc"))
    except:
        return 400, "'hum_perc' must be a valid percentual humidity"
    try:
        sensors_logs.InsertDHT22Reading(
            sensor_id, ts_secs, temperature_c=temp_c, humidity_perc=humidity_perc)
    except Exception as e:
        html.append(__ExceptionToHtml(e))

    return 200, "OK"


def __GetLatestSensorsReadingsTable():
    html = []
    html.append("<h2>DHT22 Sensors</h2>")
    html.append('<table class="latest_sensors_table"><tr>')
    columns = ["ID", "Last Masurement", "Temp (C)", "Humidity (%)", "History"]
    for c in columns: html.append("<th>%s</th>" % c)
    html.append("</tr>")
    data = sensors_logs.GetLatestDHT22Readings()
    for d in data:
        device_id = str(d[0])
        last_date = HtmlEscape(__TimestampToHuman(d[1]))
        temp = str(d[2])
        hum = str(d[3])        
        html.append("<tr>")
        for c in (device_id, last_date, temp, hum):
            html.append("<td>%s</td>" % c)
        html.append('<td><a href="/viewsensors?mode=table&type=dht22&'
                    'id=%s">Table</a> / ' % device_id)
        html.append('<a href="/viewsensors?mode=graph&type=dht22&'
                    'id=%s">Graph</a></td>' % device_id)
        html.append("</tr>")
    html.append("</table>")
    if not data: html.append("No DHT22 devices found.")
    return "\n".join(html)


def __GetSensorsReadingsTable(sensor_id, ts_start, ts_end):
    html = []
    html.append('<table class="latest_sensors_table"><tr>')
    columns = ["Time", "Temp (C)", "Humidity (%)"]
    for c in columns: html.append("<th>%s</th>" % c)
    html.append("</tr>")
    data = sensors_logs.GetDHT22Readings(sensor_id, ts_start, ts_end)
    for d in reversed(data):
        date = HtmlEscape(__TimestampToHuman(d[0]))
        temp = str(d[1])
        hum = str(d[2])        
        html.append("<tr>")
        for c in (date, temp, hum):
            html.append("<td>%s</td>" % c)
        html.append("</tr>")
    html.append("</table>")
    if not data: html.append("No measurement found.")
    return "\n".join(html)


def __GetSensorsReadingsGraphData(sensor_id, ts_start, ts_end):
    js_temp = ["['Time', 'Temperature (C)']"]
    js_hum = ["['Time', 'Humidity (%)']"]
    data = sensors_logs.GetDHT22Readings(sensor_id, ts_start, ts_end)
    for d in data:
        ts = 1000 * d[0]
        js_temp.append("[new Date(%d), %f]" % (ts, d[1]))
        js_hum.append("[new Date(%d), %f]" % (ts, d[2]))
    return ",".join(js_temp), ",".join(js_hum)


def ViewSensorsHandler(parsed_path):
    params = urlparse.parse_qs(parsed_path.query)
    sensor_type = ExtractParamValue(params, "type")
    if sensor_type is None:
        html = [HTML_HEADER, HTML_TOC, "<h1>View Sensors</h1>"]
        html.append(__GetLatestSensorsReadingsTable())
        html.append(HTML_TAIL)
        return 200, "\n".join(html)
    
    if sensor_type.lower() != "dht22":
        return 501, "Unsuported sensor type (only dht22 is supported)"
    try:
        sensor_id = int(ExtractParamValue(params, "id"))
        if sensor_id <= 0:
            return 400, "id must be larger than zero"
    except:
        return 400, "'id' must be an integer larger than zero"
    ts_end = ExtractParamValue(params, "ts_end")
    if ts_end is None:
        ts_end = int(time.time())
    else:
        try:
            ts_end = int(ts_end)
            if ts_end < 0:
                return 400, "'ts_end' must not be negative"
        except:
            return 400, "'ts_end' must be a valid timestamp"
    ts_start = ExtractParamValue(params, "ts_start")
    if ts_start is None:
        ts_start = ts_end - 3600 * 24
    else:
        try:
            ts_start = int(ts_start)
            if ts_start < 0:
                return 400, "'ts_start' must not be negative"
            if ts_start > ts_end:
                return 400, "'ts_start' must precede 'ts_end'"
        except:
            return 400, "'ts_start' must be a valid timestamp"

    mode = ExtractParamValue(params, "mode")
    if mode is None or mode.lower() != "graph":
        html = [HTML_HEADER, HTML_TOC, "<h1>View Sensors</h1>"]
        html.append("<h2>DHT22 Sensor: %d </h2>" % sensor_id)
        html.append(__GetSensorsReadingsTable(sensor_id, ts_start, ts_end))
        html.append(HTML_TAIL)
        return 200, "\n".join(html)

    
    temp_data_js, hum_data_js = __GetSensorsReadingsGraphData(sensor_id, ts_start, ts_end)
    html = [HTML_HEADER_BEGIN, """\
<script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
<script type="text/javascript">
  google.charts.load('current', {packages: ['corechart']});
  google.charts.setOnLoadCallback(drawChart);
  function drawChart() {
    var temp_data = google.visualization.arrayToDataTable([%s]);
    var temp_options = {
      title: 'Temperature',
      curveType: 'function',
      legend: { position: 'bottom' }
    };
    var temp_chart = new google.visualization.LineChart(document.getElementById('temp_chart'));
    temp_chart.draw(temp_data, temp_options);
    var hum_data = google.visualization.arrayToDataTable([%s]);
    var hum_options = {
      title: 'Humidity',
      curveType: 'function',
      legend: { position: 'bottom' }
    };
    var hum_chart = new google.visualization.LineChart(document.getElementById('hum_chart'));
    hum_chart.draw(hum_data, hum_options);
  }
</script>""" % (temp_data_js, hum_data_js)]
    html.extend([HTML_HEADER_END, HTML_TOC, "<h1>View Sensors</h1>"])
    html.append("<h2>DHT22 Sensor: %d </h2>" % sensor_id)
    html.append('<div id="temp_chart" class="widechart"></div>')
    html.append('<div id="hum_chart" class="widechart"></div>')
    html.append(HTML_TAIL)
    return 200, "\n".join(html)


if __name__ == "__main__":
    #print SysConsoleHandler(urlparse.urlparse("/"))
    #print SysActionMenuHandler(urlparse.urlparse("/sysactmenu"))
    #print SensorsHandler(
    #    urlparse.urlparse("/sensors?type=dht22&id=1&ts=100&temp_c=25.3&hum_perc=40.1"))
    #print ViewSensorsHandler(urlparse.urlparse("/"))
    print ViewSensorsHandler(urlparse.urlparse("/viewsensors?type=dht22&id=100&mode=graph"))
