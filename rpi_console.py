#!/usr/local/bin/python2.7

import SocketServer
import getopt
import os
import sys

from generic_http_handler import SimpleGenericHandler
from rpi_console_handlers import SysActionHandler
from rpi_console_handlers import SysActionMenuHandler
from rpi_console_handlers import SysConsoleHandler
from rpi_console_handlers import TorrentHandler
from rpi_console_handlers import TorrentLogsHandler
from rpi_console_handlers import SubsHandler
from rpi_console_handlers import RouterLogsHandler
from rpi_console_handlers import SensorsHandler
from rpi_console_handlers import ViewSensorsHandler

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
      "/rtorrentlogs": TorrentLogsHandler,
      "/subs": SubsHandler,
      "/router": RouterLogsHandler,
      "/sensors": SensorsHandler,
      "/viewsensors": ViewSensorsHandler })
  httpd = SocketServer.TCPServer(("", port), http_handler_class)

  os.chdir("resources")

  print "serving at port", port
  httpd.serve_forever()
