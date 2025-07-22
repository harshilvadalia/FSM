import time
import logging
import threading
import sys
from datetime import datetime
from opcua import Client, ua

# --- PLC CONFIGURATION ---
PLC_URL = "opc.tcp://10.10.14.113:4840"
NODE_IDS = {
    "Motor_off": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Motor_off",
    "output0": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.output0",
    "mm": "ns=4;s=|var|AX-308EA0MA1P.Application.GVL.mm",
    "Relay1": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay1"
}

# --- LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class PLCController:
    def __init__(self, plc_url, node_ids):
        self.plc_url = plc_url
        self.node_ids = node_ids
        self.client = None
        self.connected = False

    def connect(self):
        for attempt in range(3):
            try:
                self.client = Client(self.plc_url)
                self.client.set_timeout(10)
                self.client.connect()
                self.connected = True
                logging.info("Connected to OPC UA server")
                return True
            except Exception as e:
                logging.error(f"Connection attempt {attempt+1} failed: {e}")
                time.sleep(2)
        self.connected = False
        return False

    def disconnect(self):
        if self.client and self.connected:
            self.client.disconnect()
            self.connected = False
            logging.info("Disconnected.")

    def read_variable(self, node_key):
        if not self.connected:
            print("Not connected to PLC.")
            return None
        try:
            node = self.client.get_node(self.node_ids[node_key])
            val = node.get_value()
            logging.info(f"Read {node_key}: {val}")
            return val
        except Exception as e:
            logging.error(f"Error reading {node_key}: {e}")
            return None

    def write_variable(self, node_key, value):
        if not self.connected:
            print("Not connected to PLC.")
            return False
        try:
            node = self.client.get_node(self.node_ids[node_key])
            dtype = node.get_data_type_as_variant_type()
            node.set_value(ua.Variant(value, dtype))
            logging.info(f"Wrote {value} to {node_key}")
            return True
        except Exception as e:
            logging.error(f"Error writing {node_key}: {e}")
            return False

    # High-level control methods
    def start_motor(self):
        return self.write_variable('Motor_off', False)
    def stop_motor(self):
        return self.write_variable('Motor_off', True)
    def activate_output0(self):
        return self.write_variable('output0', True)
    def deactivate_output0(self):
        return self.write_variable('output0', False)
    def activate_relay1(self):
        return self.write_variable('Relay1', True)
    def deactivate_relay1(self):
        return self.write_variable('Relay1', False)
    def set_mm_value(self, val):
        return self.write_variable('mm', val)
    def read_all_status(self):
        return {k: self.read_variable(k) for k in self.node_ids.keys()}

def run_terminal_menu(plc):
    def menu():
        print("\n--- PLC Terminal Controller ---")
        print("1. Start Motor")
        print("2. Stop Motor")
        print("3. Activate Output0")
        print("4. Deactivate Output0")
        print("5. Activate Relay1")
        print("6. Deactivate Relay1")
        print("7. Set MM Value")
        print("8. Read All Status")
        print("9. Exit")
    while True:
        menu()
        choice = input("Select option: ").strip()
        if choice == "1":
            plc.start_motor()
        elif choice == "2":
            plc.stop_motor()
        elif choice == "3":
            plc.activate_output0()
        elif choice == "4":
            plc.deactivate_output0()
        elif choice == "5":
            plc.activate_relay1()
        elif choice == "6":
            plc.deactivate_relay1()
        elif choice == "7":
            try:
                val = float(input("MM value: "))
                plc.set_mm_value(val)
            except ValueError:
                print("Invalid value.")
        elif choice == "8":
            vals = plc.read_all_status()
            for k, v in vals.items():
                print(f"{k}: {v}")
        elif choice == "9":
            print("Exit.")
            break
        else:
            print("Invalid. Try again.")

def main():
    plc = PLCController(PLC_URL, NODE_IDS)
    print("Connecting to PLC...")
    if not plc.connect():
        print("Could not connect to PLC. Exiting.")
        sys.exit(1)
    try:
        run_terminal_menu(plc)
    finally:
        plc.disconnect()

if __name__ == "__main__":
    main()
