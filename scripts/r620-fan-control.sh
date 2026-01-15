#!/bin/bash

# === SYSTEMD SETUP INSTRUCTIONS ===
# 1. Create the service file: 
#    vim /etc/systemd/system/fancontrol.service
# ---------------------------------------------------------
# [Unit]
# Description=Dell R620 Smart Fan Control
#
# [Service]
# Type=simple
# ExecStart=/bin/bash /root/r620-fan-control.sh
# ---------------------------------------------------------
#
# 2. Create the timer file:
#    vim /etc/systemd/system/fancontrol.timer
# ---------------------------------------------------------
# [Unit]
# Description=Run Dell Fan Control every 5 seconds
#
# [Timer]
# OnBootSec=1min
# OnUnitActiveSec=10s
# AccuracySec=1ms
#
# [Install]
# WantedBy=timers.target
# ---------------------------------------------------------
#
# 3. Enable and Start:
#    systemctl daemon-reload
#    systemctl enable --now fancontrol.timer
#
# 4. Useful Commands:
#    systemctl list-timers             # Check if it is running
#    systemctl status fancontrol.timer # Check timer health
#    journalctl -u fancontrol.service  # See execution logs
# ==================================

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

LOGFILE="/var/log/r620_fan_control.log"
MAX_LOGSIZE=1048576 # 1MB in bytes
STATEFILE="/dev/shm/fan_last_state" # Stored in RAM

###############################################

# Log Rotation Logic
if [ -f "$LOGFILE" ]; then
	SIZE=$(stat -c%s "$LOGFILE")
	if [ "$SIZE" -gt "$MAX_LOGSIZE" ]; then
		echo "$(date +%Y-%m-%d-%H:%M:%S) - Log max size reached. Rotating." > "$LOGFILE"
	fi
fi


# Redirect all output and errors to the logfile
exec >> "$LOGFILE" 2>&1

DATE=$(date +%Y-%m-%d-%H:%M:%S)
echo "--- Run: $DATE ---"


# Fetch temperatures - use a timeout to ensure script doesn't hang if IDRAC is slow to respond
CPU1=$(timeout 10s ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD sdr type temperature | grep "0Eh" | awk -F'|' '{print $5}' | awk '{print $1}')
CPU2=$(timeout 10s ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD sdr type temperature | grep "0Fh" | awk -F'|' '{print $5}' | awk '{print $1}')


# Safety Check: Did we get valid numbers?
if [[ ! "$CPU1" =~ ^[0-9]+$ ]] || [[ ! "$CPU2" =~ ^[0-9]+$ ]]; then
	echo "ERROR: Could not read CPU temperatures. Returning control to iDRAC for safety!"
        # 0x01 0x01 enables dynamic/automatic fan control
        ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x01 0x01
        exit 1
fi


# Determine highest temp
if [ "$CPU1" -gt "$CPU2" ]; then
	T=$CPU1
else
	T=$CPU2
fi

echo "CPU1: $CPU1°C | CPU2: $CPU2°C"
echo "Using $T°C as current control temperature."
echo ""


# --- Determine Target Bracket ---
if [ "$T" -gt "$MAX_TEMPTHRESHOLD" ]; then
	NEW_STATE="MAX"
	SPEED_HEX=$MAX_FANSPEEDBASE16
elif [ "$T" -gt "$NORMAL_TEMPTHRESHOLD" ]; then
	NEW_STATE="NORMAL"
	SPEED_HEX=$NORMAL_FANSPEEDBASE16
elif [ "$T" -gt "$IDLE_TEMPTHRESHOLD" ]; then
	NEW_STATE="IDLE"
	SPEED_HEX=$IDLE_FANSPEEDBASE16
else
	NEW_STATE="LOW"
	SPEED_HEX="0x05" # Safety minimum
fi


# --- Check if state has changed ---
OLD_STATE=$(cat "$STATEFILE" 2>/dev/null)

if [ "$NEW_STATE" == "$OLD_STATE" ]; then
	# No change needed, exit quietly to save iDRAC resources
	echo "No state change, exiting."
	echo ""
	exit 0
else
	# State changed! Update iDRAC
	echo "$(date) State Change: $OLD_STATE -> $NEW_STATE (Temp: ${T}°C)"
	echo ""
	
	# 1. Enable Manual Mode
	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x01 0x00
	# 2. Set Speed
	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff $SPEED_HEX                                
	
	# 3. Save new state
	echo "$NEW_STATE" > "$STATEFILE"
fi


# Enable manual file control
#ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x01 0x00
#
#if [ "$T" -gt "$MAX_TEMPTHRESHOLD" ]; then
#	echo "Temp is over the maximum allowed threshold of $MAX_TEMPTHRESHOLD°C"
#	echo "Setting fan speed to maximum ($MAX_FANSPEEDBASE10)"
#	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff $MAX_FANSPEEDBASE16
#elif [ "$T" -gt "$NORMAL_TEMPTHRESHOLD" ]; then
#	echo "Temp is over the normal allowed threshold of $NORMAL_TEMPTHRESHOLD°C"
#	echo "Setting fan speed to normal ($NORMAL_FANSPEEDBASE10)"
#	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff $NORMAL_FANSPEEDBASE16
#elif [ "$T" -gt "$IDLE_TEMPTHRESHOLD" ]; then
#	echo "Temp is over the idle allowed threshold of $IDLE_TEMPTHRESHOLD°C"
#	echo "Setting fan speed to idle ($IDLE_FANSPEEDBASE10)"
#	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff $IDLE_FANSPEEDBASE16
#else
#	echo "Temp is at or below the idle allowed threshold of $IDLE_TEMPTHRESHOLD°C"
#	echo "Setting fan speed to 0%"
#	ipmitool -I lanplus -H $IDRACIP -U $IDRACUSER -P $IDRACPASSWORD raw 0x30 0x30 0x02 0xff 0x00
#fi
