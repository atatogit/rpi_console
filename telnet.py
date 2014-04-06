#!/usr/bin/python

import telnetlib

# Fuck security.
__HOST = "192.168.1.1"
__USER = "admin\n"
__PASS = "Iseuqrom\n"


def ExecuteCommand(command):
    tn = telnetlib.Telnet(__HOST)
    tn.read_until("login: ")
    tn.write(__USER)
    tn.read_until("Password: ")
    tn.write(__PASS)
    tn.write("%s\n" % command)
    tn.write("exit\n")
    tn.read_very_eager()
    return tn.read_all()

if __name__ == "__main__":
    print "---"
    print ExecuteCommand("ls /tmp/")
    print "---"
