# README: Autonomous PLC Control System - START & EMERGENCY Only

## Overview
This Python script provides a **fully autonomous PLC control system** with only two commands:
- **START**: Begin autonomous operation
- **EMERGENCY**: Immediate stop of all operations

Once started, the system runs **completely autonomously** with no human interaction required unless an emergency occurs.

## Features
- ✅ **Autonomous Operation**: Runs production cycles automatically
- 🚨 **Emergency Stop**: Immediate halt via 'E' key or Ctrl+C
- 📊 **Real-time Monitoring**: LVDT sensor feedback and safety checks
- 🔄 **Continuous Cycles**: Repeats production cycles with configurable intervals
- 📝 **Comprehensive Logging**: All operations logged to file and console
- 🛡️ **Safety Interlocks**: Position limits and emergency detection

## Requirements
- Python 3.7+
- Windows 11 (uses msvcrt for key detection)
- OPC UA library: `pip install opcua`
- Network connection to PLC at 10.10.14.113:4840

## How It Works

### 1. Start Command
- Type `S` to start autonomous operation
- System connects to PLC and performs safety checks
- Begins continuous production cycles without human intervention

### 2. Production Cycle (Automated)
Each cycle follows this sequence:
1. **Safety Check**: Verify LVDT position and emergency signals
2. **System Init**: Enable operational staff and bearing systems
3. **Production**: Start motor and monitor progress
4. **Monitoring**: Track LVDT sensor until target position (85mm)
5. **Shutdown**: Stop motor and disable systems
6. **Wait**: 30-second interval before next cycle

### 3. Emergency Stop
Multiple ways to trigger emergency stop:
- Press `E` key during operation
- Press `Ctrl+C` 
- Hardware emergency stop signal detected
- LVDT position out of safe range (0-100mm)

## Usage Instructions

### Running the System
```bash
python start-emergency-plc.py
```

### Available Commands
- `S` - **START**: Begin autonomous operation
- `E` - **EMERGENCY**: Stop all operations immediately  
- `Q` - **QUIT**: Exit the program

### Operation Flow
1. Run the script
2. Type `S` and confirm with `Y`
3. System starts autonomous operation
4. Monitor status updates every 60 seconds
5. Use `E` key for emergency stop if needed

## Configuration

### Autonomous Parameters (editable at top of script)
```python
CONFIG = {
    "cycle_interval": 30,        # Seconds between cycles
    "production_time": 15,       # Production duration per cycle
    "target_position": 85.0,     # Target LVDT position (mm)
    "max_position": 100.0,       # Safety limit
    "min_position": 0.0          # Safety limit
}
```

### PLC Node Mappings
- **mm**: LVDT sensor data (read-only)
- **Motor_off**: Emergency stop signal (read-only) 
- **Relay1**: Motor control (read/write)
- **operational_bearing_on**: Bearing control (read/write)
- **operational_staff_on**: Staff safety system (read/write)
- **Relay2/3**: Hydraulic status (read-only)
- **output0**: Motor status feedback (read-only)

## Safety Features

### Automatic Safety Checks
- Hardware emergency stop detection
- LVDT position limit enforcement
- Hydraulic system conflict detection
- Connection monitoring with automatic retry

### Emergency Response
When emergency triggered:
1. Immediately disable motor (Relay1 = False)
2. Turn off operational bearing system
3. Disable staff safety system
4. Log emergency event with timestamp
5. Stop all automation threads

## Logging and Monitoring

### Console Output
- Real-time operation status
- Cycle completion notifications
- Emergency alerts
- Status updates every 60 seconds

### Log File: `autonomous_plc.log`
- Detailed operation history
- Error messages and debugging info
- Safety event logging
- Performance statistics

### Status Information
- Runtime duration
- Cycles completed
- Current LVDT position
- Motor status
- Emergency state

## Troubleshooting

### Connection Issues
- Verify PLC IP address: 10.10.14.113:4840
- Check network connectivity
- Ensure OPC UA server is running on PLC

### Emergency Stop Won't Reset
- Check hardware emergency stop button
- Verify LVDT position is within safe range (0-100mm)
- Review log file for specific error messages

### System Won't Start
- Hardware emergency stop may be active
- Check PLC connection
- Verify all node IDs are correct

## Example Operation

```
$ python start-emergency-plc.py

============================================================
    AUTONOMOUS PLC CONTROL SYSTEM
    NO HUMAN INTERACTION MODE
============================================================

Available commands:
  [S] START  - Begin autonomous operation
  [E] EMERGENCY - Stop all operations immediately

Enter command (S=Start, E=Emergency, Q=Quit): s

🚀 STARTING AUTONOMOUS SYSTEM...
⚠️  Once started, system runs without human interaction
🚨 Press 'E' key during operation for emergency stop

Confirm start autonomous operation? (Y/N): y

🔌 Connecting to PLC...
✅ Connected to PLC
🤖 Starting autonomous operation...
✅ System started - Running autonomously...

🚨 EMERGENCY: Press 'E' key anytime for emergency stop
📊 System will show status every 60 seconds
--------------------------------------------------
🔄 Starting Cycle #1
🔧 Starting systems...
⚡ Starting motor...
✅ Target reached: 87.2mm
🛑 Stopping production...
✅ Cycle #1 completed successfully
⏳ Waiting 30 seconds until next cycle...

📊 STATUS UPDATE:
   Runtime: 0:02:15
   Cycles completed: 1
   Current position: 45.3mm
   Motor running: False
   Emergency: False
--------------------------------------------------
```

## Important Notes

⚠️ **Safety First**: Always ensure proper safety measures before starting autonomous operation

⚠️ **Emergency Access**: Keep emergency stop accessible at all times

⚠️ **Monitoring**: While autonomous, system provides regular status updates

⚠️ **Manual Override**: Only emergency stop available during operation - no other manual controls

This system is designed for **lights-out automation** where minimal human intervention is required for normal production operations.