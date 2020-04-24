#!/usr/bin/python

import telnetlib

# Fuck security.
__HOST = "192.168.1.1"
__USER = "admin\n"
__PASS = "PASSWORD\n"

__BEGIN = "#BEGINBEGINBEGIN"
__END = "#ENDENDEND"

def __ConnectAndLogIn():
    tn = telnetlib.Telnet(__HOST)
    tn.read_until("login: ")
    tn.write(__USER)
    tn.read_until("Password: ")
    tn.write(__PASS)
    tn.read_very_eager()
    return tn

def ExecuteCommand(command):
    tn = __ConnectAndLogIn()
    tn.write("%s\n" % __BEGIN)
    tn.write("%s\n" % command)
    tn.write("%s\n" % __END)
    tn.write("exit\n")
    return tn.read_all()

def GetRemoteTextFile(path):
    data = ExecuteCommand("cat %s" % path)
    begin = data.rindex(__BEGIN) + len(__BEGIN) + 2
    begin = data.index("\r\n", begin) + 2
    end = data.index(__END, begin) - 2
    end = data.rindex("\r\n", begin, end)
    return data[begin:end]

if __name__ == "__main__":
    print GetRemoteTextFile("/tmp/syslog.log")
