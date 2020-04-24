#!/usr/bin/python

import SimpleHTTPServer
from urlparse import urlparse

class SimpleGenericHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
  @staticmethod
  def NewSimpleGenericHandlerClass(handlers):
    class SimpleGenericHandlerWithCustomHandlers(SimpleGenericHandler): pass
    SimpleGenericHandlerWithCustomHandlers.__handlers = handlers
    return SimpleGenericHandlerWithCustomHandlers
      
  def do_HEAD(self):
    return self.__DoHeadOrGet(False)

  def do_GET(self):
    return self.__DoHeadOrGet(True)

  def __DoHeadOrGet(self, return_content):
    parsed = urlparse(self.path)
    handler = self.__handlers.get(parsed.path)
    if handler is None:
      if return_content:
        return SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)
      else:
        return SimpleHTTPServer.SimpleHTTPRequestHandler.do_HEAD(self)
    code, html_data = handler(parsed)
    self.send_response(code)
    self.send_header("Content-type", "text/html")
    self.end_headers()
    if return_content: self.wfile.write(html_data)
