#!/bin/sh
# launcher.sh
# navigate to script directory, then execute python script

cd "$(dirname "$0")"
python perfcounters-to-influx.py
