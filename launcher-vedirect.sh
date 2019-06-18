#!/bin/sh
# launcher.sh
# navigate to script directory, then execute python script

cd "$(dirname "$0")"
sudo python serialvictron-to-influx.py