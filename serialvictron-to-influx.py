# RK 20190606 V1.1.0
# Reads serial input from a victron mppt device (VE.Direct protocol),
# and sends those data to a local influx database.
# Is designed for MPPT chargers only.
# However, if you intend to read data from other devices,
# refer to victrons VE.Direct protocol white paper
# and integrate the missing (if any) record key/values.
import datetime
import serial
import time
import string
import unicodedata
import os
import signal
import sys
import traceback
from influxdb import InfluxDBClient

# After a successful insert to the database, specified seconds
# is waited to avoid flooding the database with an unnecessary precision
intervalseconds = 5

# The name of the local influx database.
influxdatabasename = 'victronlog'

# The address of the serial device.
serialdeviceaddress = '/dev/ttyUSB0'

# Evaluate debug argument
debug = False
for arg in sys.argv:
    if(arg == '-d'):
        debug = True


# Validates the integrity of a data block.
# The sum of all modulo-256 operations must equal to 0.
# The checksum value sent by victron device is used to always allow a sum to 0,
# so we do not actually need to evaluate the checksum value.
def checkblock(st):
    val = 0
    for c in st:
        num = ord(c)
        val = val + num
    return val % 256 == 0


# Returns an empty influx dictionary object.
def getinflux():
    return {'measurement': 'vedirect', 'tags': {}, 'time': '', 'fields': {}}

scriptstartutc = datetime.datetime.utcnow()
laststatuslog = datetime.datetime.utcnow()
checksumerrors = 0
exceptionerrors = 0
records = 0

# Initialize serial device with configuration used by VE.Direct devices.
ser = serial.Serial(serialdeviceaddress, 19200, 8, 'N', 1, timeout=1)
ser.flushInput()

# Initialize influx database client.
client = InfluxDBClient(database=influxdatabasename)

# Initialize current record.
influx = getinflux()
block = ''

# Ongoing main loop.
while True:
    if(laststatuslog < datetime.datetime.utcnow(),
            - datetime.timedelta(seconds=10)):
        laststatuslog = datetime.datetime.utcnow()
        elapsed = datetime.datetime.utcnow() - scriptstartutc
        print('Check sum errors: ' + str(checksumerrors))
        print(' | Exception errors: ' + str(exceptionerrors))
        print(' | Records inserted: ' + str(records))
        print('Script running since: ' + str(elapsed))
        # If any of the values should get close to the int32 border, reset values.
        if(max(checksumerrors, exceptionerrors, records) > 2000000000):
            checksumerrors = 0
            exceptionerrors = 0
            records = 0
            print('Counters reset')
    try:
        # Read a line from serial interface.
        # A data block (record) consists of multiple lines.
        serialinput = ser.readline().decode('ascii')

        # Data keys and values are separated by tabulator.
        values = serialinput.split('\t')

        # We expect 2 items (key and value).
        # If not sent, then do not try to parse but wait a few secs.
        if len(values) != 2:
            time.sleep(3)
        else:
            # Remove additional content after last sent byte for a block
            # Sometimes, VE devices sends these for no obvious reason
            if(values[0] == 'Checksum'):
                values[1] = values[1].split(':')[0]

            # We concatenate the input of the current block
            # to verify the integrity with sent checksum later on.
            block = block + serialinput
            key = values[0]

            # Used for renaming the key to a more user-friendly name.
            keyname = key

            # Remove control characters from value
            # (carriage return and new line are sent).
            value = str(values[1].strip())
            if key == 'V':
                # Divide by 1000 because millivolts are sent
                # to allow precision without using float.
                # Unnecessary to let the client calculate that.
                value = float(value)/1000
                keyname = 'Battery Voltage'
            elif key == 'VPV':
                keyname = 'Panel Voltage'
                value = float(value)/1000
            elif key == 'PPV':
                keyname = 'Panel Power'
                value = int(value)
            elif key == 'I':
                keyname = 'Battery Current'
                value = float(value)/1000
            elif key == 'IL':
                keyname = 'Load Current'
                value = float(value)/1000
            elif key == 'LOAD':
                keyname = 'Load State Code'
                # Evaluate load state.
                if value == 'ON':
                    value = 1
                else:
                    value = 0
            elif key == 'H19':
                keyname = 'Yield Total'
                # Unit is KWh, but scale is 0.01 for precision reasons.
                # Unnecessary to let the client calculate that.
                value = float(value)/100
            elif key == 'H20':
                keyname = 'Yield Today'
                value = float(value)/100
            elif key == 'H21':
                keyname = 'Maximum Power Today'
                value = int(value)
            elif key == 'H22':
                keyname = 'Yield Yesterday'
                value = float(value)/100
            elif key == 'H23':
                keyname = 'Maximum Power Yesterday'
                value = int(value)
            elif key == 'CS':
                keyname = 'Operation State Int'
                value = int(value)
            elif key == 'ERR':
                keyname = 'Error Int'
                value = int(value)
            elif key == 'FW':
                keyname = 'Firmware Version'
            elif key == 'PID':
                keyname = 'Product ID'
            elif key == 'SER#':
                keyname = 'Serial Number'
            elif key == 'HSDS':
                keyname = 'Day Sequence Number Int'
                value = int(value)
            elif key == 'MPPT':
                keyname = 'MPPT Int'
                value = int(value)

            # Checksum is the last line sent for a block.
            if key == 'Checksum':
                if(debug is True):
                    print('Block complete')
                    print(block)

                # Verify integrity.
                if checkblock(block):
                    # If the check was successful, set the time
                    # for the influx object and insert it in the database.
                    influx['time'] = str(datetime.datetime.utcnow())
                    client.write_points([influx, ])
                    records += 1
                    if(debug is True):
                        print('Inserted record at ' + influx['time'])

                    # Wait for defined interval.
                    time.sleep(intervalseconds)
                else:
                    # If the check was not successful, just print an error.
                    # Current block is reset afterwards.
                    checksumerrors += 1

                    if(debug is True):
                        print('Checksum error, record is ignored')
                # Reset current block/record.
                influx = getinflux()
                block = ''
            # If we do not get a 'checksum' line for whatever reason,
            # hard-reset the current record.
            # This is to avoid Memory Overflows,
            # and allows the script to recover itself.
            elif len(influx['fields']) > 50:
                print('Expected checksum line not sent, resetting.')
                influx = getinflux()
                block = ''
            else:
                # When the current line is not 'checksum',
                # and there is no overflow, set the field here.
                influx['fields'][keyname] = value
    except:
        # Print exception info and wait for specified interval,
        # if an error occurred
        exceptionerrors += 1
        traceback.print_exc()
        time.sleep(intervalseconds)
