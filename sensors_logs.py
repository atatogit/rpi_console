#!/usr/bin/python

import MySQLdb

__DB = MySQLdb.connect(
    host="localhost", user="nobody", passwd="nobody", db="sensors")

def __FetchAll(sql, params):
    __DB.ping(True)
    c = __DB.cursor()
    c.execute("""set session transaction isolation level READ COMMITTED;""")
    c.fetchall()
    c.execute(sql, params)
    results = c.fetchall()
    c.close()
    return results

def __Insert(sql, params):
    __DB.ping(True)
    c = __DB.cursor()
    c.execute(sql, params)
    __DB.commit()
    c.close()


def InsertDHT22Reading(device_id, date, temperature_c=None, humidity_perc=None):
    # From http://www.sqlite.org/lang_datefunc.html.
    assert 0 <= date <= 10675199167

    sql = """INSERT INTO dht22readings VALUES (%s, %s, %s, %s);"""
    __Insert(sql, (device_id, date, temperature_c, humidity_perc))


def GetDHT22Readings(device_id, min_date=None, max_date=None):
    # From http://www.sqlite.org/lang_datefunc.html.
    if min_date is None: min_date = 0
    if max_date is None: max_date = 10675199167

    sql = """\
SELECT
    ts_secs,
    temperature_c,
    humidity_perc
FROM
    dht22readings
WHERE device_id = %s AND ts_secs BETWEEN %s AND %s
ORDER BY ts_secs;"""

    return __FetchAll(sql, (device_id, min_date, max_date))


def GetLatestDHT22Readings():
    sql = """\
SELECT
    T2.device_id, T2.ts_secs, T2.temperature_c, T2.humidity_perc
FROM
    (SELECT   device_id, MAX(ts_secs) AS max_ts_secs
     FROM     dht22readings
     WHERE    device_id > 0
     GROUP BY device_id) AS T1
LEFT JOIN
    dht22readings AS T2
ON T1.device_id = T2.device_id AND
   T1.max_ts_secs = T2.ts_secs;
"""
    return __FetchAll(sql, ())


if __name__ == "__main__":
    #InsertDHT22Reading(0, 1, None, None)
    #InsertDHT22Reading(0, 2, 24.5, None)
    #InsertDHT22Reading(0, 3, None, 40.2)
    #InsertDHT22Reading(0, 4, 25, 43)
    #print GetDHT22Readings(0)
    print GetLatestDHT22Readings()