#!/usr/bin/python

import MySQLdb

from collections import defaultdict
from google.cloud import bigquery
from google.cloud import monitoring_v3


__DB = MySQLdb.connect(
    host="localhost", user="nobody", passwd="nobody", db="sensors")

__GCP_PROJECT = "spueblas-smart-home"
__GCP_LOCATION = "us-east1"
__GCP_METRIC_NAMESPACE = ""
__TEMPERATURE_METRIC = "custom.googleapis.com/temperature_c"
__HUMIDITY_METRIC = "custom.googleapis.com/humidity_perc"
__PRESSURE_METRIC = "custom.googleapis.com/pressure_hpa"

__BQ_DATASET = "weather_data"
__TEMPERATURE_TABLE = "%s.%s.temperature_c" % (__GCP_PROJECT, __BQ_DATASET)
__HUMIDITY_TABLE = "%s.%s.humidity_perc" % (__GCP_PROJECT, __BQ_DATASET)
__PRESSURE_TABLE = "%s.%s.pressure_hpa" % (__GCP_PROJECT, __BQ_DATASET)


def __GetMetricTimeseries(device_type, device_id, metric_type, date, value):
    series = monitoring_v3.types.TimeSeries()

    series.metric.type = metric_type
    series.resource.type = "generic_node"
    series.resource.labels["project_id"] = __GCP_PROJECT
    series.resource.labels["location"] = __GCP_LOCATION
    series.resource.labels["node_id"] = "%s_%s" % (device_type, device_id)
    series.resource.labels["namespace"] = __GCP_METRIC_NAMESPACE

    point = series.points.add()
    point.value.double_value = value
    point.interval.end_time.seconds = date
    point.interval.end_time.nanos = 0

    return series
    

def __GetBQRow(timestamp, device_type, device_id, value_column, value):
    return {"timestamp": timestamp, "device_type": device_type,
            "device_id": device_id, value_column: value}


def __PushMetricsToStackDriverAndBQ(device_type, device_id, date,
                                    temperature_c=None, humidity_perc=None,
                                    pressure_hpa=None):
    series = []
    bq_rows = defaultdict(lambda: [])
    if temperature_c is not None:
        series.append(
            __GetMetricTimeseries(device_type, device_id, __TEMPERATURE_METRIC,
                                  date, temperature_c))
        bq_rows[__TEMPERATURE_TABLE].append(__GetBQRow(
                date, device_type, device_id, "temperature_c", temperature_c))
    if humidity_perc is not None:
        series.append(
            __GetMetricTimeseries(device_type, device_id, __HUMIDITY_METRIC,
                                  date, humidity_perc))
        bq_rows[__HUMIDITY_TABLE].append(__GetBQRow(
                date, device_type, device_id, "humidity_perc", humidity_perc))
    if pressure_hpa is not None:
        series.append(
            __GetMetricTimeseries(device_type, device_id, __PRESSURE_METRIC,
                                  date, pressure_hpa))
        bq_rows[__PRESSURE_TABLE].append(__GetBQRow(
                date, device_type, device_id, "pressure_hpa", pressure_hpa))

    if series:
        sd_client = \
            monitoring_v3.MetricServiceClient.from_service_account_json(
            "../service_account.json")
        sd_client.create_time_series(sd_client.project_path(__GCP_PROJECT),
                                     series)

    if bq_rows:
        bq_client = \
            bigquery.Client.from_service_account_json(
            "../service_account.json")
        for table_name, rows in bq_rows.iteritems():
            table = bq_client.get_table(table_name)
            bq_client.insert_rows(table, rows)
    

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

    __PushMetricsToStackDriverAndBQ("DHT22", device_id, date, temperature_c,
                                    humidity_perc, None)


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


def InsertBMPE280Reading(device_id, date, temperature_c=None,
                         humidity_perc=None, pressure_hpa=None):
    # From http://www.sqlite.org/lang_datefunc.html.
    assert 0 <= date <= 10675199167

    sql = """INSERT INTO bmpe280readings VALUES (%s, %s, %s, %s, %s);"""
    __Insert(sql, (device_id, date, temperature_c, humidity_perc,
                   pressure_hpa))

    __PushMetricsToStackDriverAndBQ("BMPE280", device_id, date, temperature_c,
                                    humidity_perc, pressure_hpa)



def GetBMPE280Readings(device_id, min_date=None, max_date=None):
    # From http://www.sqlite.org/lang_datefunc.html.
    if min_date is None: min_date = 0
    if max_date is None: max_date = 10675199167

    sql = """\
SELECT
    ts_secs,
    temperature_c,
    humidity_perc,
    pressure_hpa
FROM
    bmpe280readings
WHERE device_id = %s AND ts_secs BETWEEN %s AND %s
ORDER BY ts_secs;"""

    return __FetchAll(sql, (device_id, min_date, max_date))


def GetLatestBMPE280Readings():
    sql = """\
SELECT
    T2.device_id, T2.ts_secs, T2.temperature_c, T2.humidity_perc,
    T2.pressure_hpa
FROM
    (SELECT   device_id, MAX(ts_secs) AS max_ts_secs
     FROM     bmpe280readings
     WHERE    device_id > 0
     GROUP BY device_id) AS T1
LEFT JOIN
    bmpe280readings AS T2
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
