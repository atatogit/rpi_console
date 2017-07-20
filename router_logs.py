#!/usr/local/bin/python2.7

import MySQLdb

__DB = MySQLdb.connect(
    host="localhost", user="nobody", passwd="nobody", db="router")

def __FetchAll(sql, params):
    __DB.ping(True)
    c = __DB.cursor()
    c.execute("""set session transaction isolation level READ COMMITTED;""")
    c.fetchall()
    c.execute(sql, params)
    results = c.fetchall()
    c.close()
    return results
    
def GetDevicesList(min_date=None, max_date=None):
    # From http://www.sqlite.org/lang_datefunc.html.
    if min_date is None: min_date = 0
    if max_date is None: max_date = 10675199167

    sql = """\
SELECT
    knowndevices.name,
    devices.last_hostname, 
    devices.mac, 
    INET_NTOA(devices.last_ip), 
    devices.last_activity
FROM
    devices
    LEFT JOIN knowndevices ON devices.mac = knowndevices.mac
WHERE devices.last_activity BETWEEN %s AND %s
ORDER BY devices.last_activity DESC, knowndevices.name ASC;"""

    return __FetchAll(sql, (min_date, max_date))

if __name__ == "__main__":
    print GetDevicesList()
