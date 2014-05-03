#!/usr/bin/python

import sys
import unicodedata
import urllib

def __GetRpiConsoleLogUrl(event_type, h, name=None):
    params = "type=%s&h=%s" % (event_type, h)
    if type(name) == unicode:
        name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore')
    if name: params = params + "&name=" + urllib.quote(name)
    return "http://raspi:8080/rtorrentlogs?" + params

if __name__ == "__main__":
    if sys.argv[1] == "inserted_new":
        url = __GetRpiConsoleLogUrl("insert", sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "finished":
        url = __GetRpiConsoleLogUrl("finished", sys.argv[2])
    else:
        sys.exit(1)

    print urllib.urlopen(url).read()

