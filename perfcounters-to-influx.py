# RK 20190617 V1.0.
# Reads a few system performance counters and sends those data to a local influx database.
import datetime
import serial
import time
import string
import unicodedata
import os
import signal
import sys
import traceback
import psutil
from influxdb import InfluxDBClient

# After a successful insert to the database, specified seconds is waited to avoid flooding the database with an unneccessary precision
intervalseconds = 5

# The name of the local influx database.
influxdatabasename = 'perfcounters'

# Evaluate debug argument
debug = False
for arg in sys.argv:
    if(arg == "-d"):
        debug = True

# Returns an empty influx dictionary object.
def getinflux():
    return {"measurement" : "piperf", "tags" : {}, "time" : "", "fields" : {}}

# Initialize influx database client.
client = InfluxDBClient(database=influxdatabasename)

# Initialize current record.
influx = getinflux()

# Ongoing main loop.
while True:
    try:
        # Evaluate values using psutil and build influx object
        influx["fields"]["CPU Load"] = psutil.cpu_percent(interval=0.3)
        netiocounters = psutil.net_io_counters(pernic=False)
        influx["fields"]["Bytes Sent"] = netiocounters.bytes_sent
        influx["fields"]["Bytes Received"] = netiocounters.bytes_recv
        influx["fields"]["RAM Usage"] = psutil.virtual_memory().percent
        influx["fields"]["CPU Temp"] = psutil.sensors_temperatures()['cpu-thermal'][0].current
        influx["fields"]["Disk Usage"] = psutil.disk_usage('/').percent
        influx["time"] = str(datetime.datetime.utcnow())
        
        if(debug == True):
            print("About to write influx object")
            print(influx)

        # Write to database
        client.write_points([influx,])
        print("Inserted record at " + influx["time"])
        
        # Wait for defined interval.
        time.sleep(intervalseconds)
    except:
        # Print exception info and wait for specified interval, if an error occured
        traceback.print_exc()
        time.sleep(intervalseconds)
