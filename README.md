# victroninflux
Python script that reads VE.Direct protocol text from a victron MPPT charger and writes those date to an influx database

Reads serial input from a victron MPPT chargers serial interface ("VE.Direct" protocol),
and sends those data to a local influx database.

Is written for MPPT charger devices, only.
However, if you intend to read data from other devices,
refer to victrons VE.Direct protocol white paper
and integrate the missing (if any) record key/values.
You can request the PDF using your email-address here:
https://www.victronenergy.com/support-and-downloads/whitepapers