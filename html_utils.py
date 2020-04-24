#!/usr/bin/python

import cgi

def HtmlEscape(s):
    escaped = cgi.escape(s)
    if type(escaped) == unicode:
        return escaped.encode('ascii', 'xmlcharrefreplace')
    return escaped

if __name__ == "__main__":
    pattern = "Example of html code: <b>This is a %s</b>"
    print "<b>%s</b>" % HtmlEscape(pattern % "test")
    
    some_utf8 = u"roulement \u00e0 billes"
    print "<b>%s</b>" % HtmlEscape(pattern % some_utf8)
