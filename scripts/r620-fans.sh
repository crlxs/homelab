#!/bin/bash

DATE=$(date +%Y-%m-%d-%H:%M:%S)

echo ""

echo "$DATE"

# Constants

IDRACIP=""
IDRACUSER=""
IDRACPASSWORD=""

IDLE_TEMPTHRESHOLD="45"
NORMAL_TEMPTHRESHOLD="70"
MAX_TEMPTHRESHOLD="80"

IDLE_FANSPEEDBASE16="0x05" # 5%
NORMAL_FANSPEEDBASE16="0x14" # 20%
MAX_FANSPEEDBASE16="0x46" # 70%

IDLE_FANSPEEDBASE10="5%" # 5%
NORMAL_FANSPEEDBASE10="20%" # 20%
MAX_FANSPEEDBASE10="70%" # 70%

# Logic

# enable manual fan control

ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x01 0x00

CPU1=$(ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD sdr type temperature | grep "0Eh" | awk -F'|' '{print $5}' | awk '{print $1}')
CPU2=$(ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD sdr type temperature | grep "0Fh" | awk -F'|' '{print $5}' | awk '{print $1}')

if [ "$CPU1" -gt "$CPU2" ]; then
	T=$CPU1
else
	T=$CPU2
fi

echo "CPU1: $CPU1°C | CPU2: $CPU2°C"
echo "Using $T°C as current control temperature."
echo ""

if [ "$T" -gt "$MAX_TEMPTHRESHOLD" ]; then
	echo "Temp is over the maximum allowed threshold of $MAX_TEMPTHRESHOLD°C"
	echo "Setting fan speed to maximum ($MAX_FANSPEEDBASE10)"
	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff $MAX_FANSPEEDBASE16
elif [ "$T" -gt "$NORMAL_TEMPTHRESHOLD" ]; then
	echo "Temp is over the normal allowed threshold of $NORMAL_TEMPTHRESHOLD°C"
	echo "Setting fan speed to normal ($NORMAL_FANSPEEDBASE10)"
	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff $NORMAL_FANSPEEDBASE16
elif [ "$T" -gt "$IDLE_TEMPTHRESHOLD" ]; then
	echo "Temp is over the idle allowed threshold of $IDLE_TEMPTHRESHOLD°C"
	echo "Setting fan speed to idle ($IDLE_FANSPEEDBASE10)"
	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff $IDLE_FANSPEEDBASE16
else
	echo "Temp is at or below the idle allowed threshold of $IDLE_TEMPTHRESHOLD°C"
	echo "Setting fan speed to 0%"
	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff 0x00
fi
