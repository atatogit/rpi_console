#!/usr/bin/python

import SocketServer
import getopt
import os
import sys

from generic_http_handler import SimpleGenericHandler
from rpi_console_handlers import SysActionHandler
from rpi_console_handlers import SysActionMenuHandler
from rpi_console_handlers import SysConsoleHandler
from rpi_console_handlers import TorrentHandler
from rpi_console_handlers import TorrentListHandler

PORT = 8080

if __name__ == "__main__":
  myopts, args = getopt.getopt(sys.argv[1:], "p:")
  port = PORT
  for o, a in myopts:
    if o == "-p": port = int(a)

  SocketServer.TCPServer.allow_reuse_address = True
  http_handler_class = SimpleGenericHandler.NewSimpleGenericHandlerClass({
      "/": SysConsoleHandler, 
      "/sysactmenu": SysActionMenuHandler, 
      "/sysact": SysActionHandler,
      "/rtorrent": TorrentHandler,
      "/rtorrentlist": TorrentListHandler})
  httpd = SocketServer.TCPServer(("", port), http_handler_class)

  os.chdir("resources")

  print "serving at port", port
  httpd.serve_forever()
