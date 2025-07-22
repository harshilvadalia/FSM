# README for PLC Terminal Automation Controller (BASIC CHECK version)

## Overview
This Python script provides a **simple, standalone terminal interface** to connect and control a single PLC over OPC UA from your Windows 11 laptop (or any PC). It allows you to manually operate key PLC functions and monitor its status through a straightforward menu system without any web or network complexity.

## Features
- Connects to your PLC's OPC UA server using configured Node IDs.
- Manual controls for:
  - Starting/stopping the motor.
  - Activating/deactivating outputs and relays.
  - Setting an analog/numeric variable (`mm`).
- Reads and displays all configured PLC variables.
- Simple terminal menu-driven interface.
- Safe connection management and error logging.
- Minimal dependencies and easy to run.

## Requirements
- Python 3.7+ installed on your PC.
- `opcua` Python library:
  ```
  pip install opcua
  ```

## Configuration
Edit the top of the script to specify your PLC endpoint and variable nodes:

```python
PLC_URL = "opc.tcp://10.10.14.113:4840"

NODE_IDS = {
    "Motor_off": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Motor_off",
    "output0": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.output0",
    "mm": "ns=4;s=|var|AX-308EA0MA1P.Application.GVL.mm",
    "Relay1": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay1"
}
```

Make sure to replace these with your actual PLC address and nodes.

## Running the Script
1. Open **Command Prompt** (Windows key → type `cmd` → Enter).
2. Navigate to the folder containing this script.
3. Run:

```
python plc_automation_controller.py
```

The program will connect to the PLC and show a menu:

```
1. Start Motor
2. Stop Motor
3. Activate Output0
4. Deactivate Output0
5. Activate Relay1
6. Deactivate Relay1
7. Set MM Value
8. Read All Status
9. Exit
```

Select options by entering numbers and pressing Enter.

## Usage Notes
- **Start/Stop Motor:** Turns the motor on or off by writing to the `Motor_off` variable.
- **Activate/Deactivate Outputs:** Control `output0` and `Relay1` variables.
- **Set MM Value:** Enter a decimal number to set the `mm` variable.
- **Read All Status:** Displays all PLC variable values defined in `NODE_IDS`.
- **Exit:** Disconnects and closes the program safely.

## Troubleshooting
- **Connection issues?**
  - Verify your PC and PLC are on the same LAN.
  - Confirm correct OPC UA server IP/port.
  - Check firewall settings may block OPC UA communication.
- **Invalid node errors?** Double-check your Node IDs and confirm with your PLC engineer.
- **Permission errors writing variables?** Ensure your OPC UA server allows writes from your client.

## Logging
This script logs info and connection errors on the console for real-time feedback.

## Extensibility
This simple script is designed for local testing and manual control. For automation sequences or safety features, consider the more advanced version with automation loops and emergency stop capabilities.

Developed as a straightforward tool for **industrial automation learning and initial PLC integration testing** on Windows 11 and OPC UA-compatible devices.

For detailed industrial automation or scaling up to multi-PLC systems, explore extending or migrating to advanced systems covering monitoring, safety, and batch production controls.