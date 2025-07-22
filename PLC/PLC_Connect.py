import time
import threading
import logging
from datetime import datetime
from opcua import Client, ua

# --- Configuration Section ---
PLC_URL = "opc.tcp://10.10.14.113:4840"
NODE_IDS = {
    "Motor_off": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Motor_off",
    "output0": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.output0",
    "mm": "ns=4;s=|var|AX-308EA0MA1P.Application.GVL.mm",
    "Relay1": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay1"
}
LOG_FILE = "plc_terminal_automation.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)


# --- Core PLC Controller ---
class PLCController:
    def __init__(self, url, node_ids):
        self.url = url
        self.node_ids = node_ids
        self.client = None
        self.connected = False
        self.status = {}
        self.emergency_active = False

    def connect(self):
        self.client = Client(self.url)
        try:
            self.client.connect()
            self.connected = True
            logging.info("Connected to PLC")
            return True
        except Exception as e:
            print(f"Connect error: {e}")
            logging.error(f"Connect error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        try:
            if self.client and self.connected:
                self.client.disconnect()
                logging.info("Disconnected from PLC")
        except Exception as e:
            logging.error(f"Disconnect error: {e}")
        self.connected = False

    def read(self, key):
        if not self.connected: return None
        try:
            node = self.client.get_node(self.node_ids[key])
            val = node.get_value()
            self.status[key] = val
            return val
        except Exception as e:
            logging.error(f"Read error ({key}): {e}")
            return None

    def write(self, key, value):
        if not self.connected: return False
        try:
            node = self.client.get_node(self.node_ids[key])
            dtype = node.get_data_type_as_variant_type()
            node.set_value(ua.Variant(value, dtype))
            self.status[key] = value
            logging.info(f"Write {key}: {value}")
            return True
        except Exception as e:
            logging.error(f"Write error ({key}): {e}")
            return False

    # High-level controls
    def start_motor(self):
        return self.write('Motor_off', False)

    def stop_motor(self):
        return self.write('Motor_off', True)

    def set_mm(self, v):
        return self.write('mm', v)

    def output_on(self):
        return self.write('output0', True)

    def output_off(self):
        return self.write('output0', False)

    def relay_on(self):
        return self.write('Relay1', True)

    def relay_off(self):
        return self.write('Relay1', False)

    def get_all(self):
        return {k: self.read(k) for k in self.node_ids}

    def emergency_stop(self):
        self.emergency_active = True
        self.stop_motor()
        self.output_off()
        self.relay_off()
        logging.warning("EMERGENCY STOP ACTIVATED")

    def emergency_reset(self):
        self.emergency_active = False
        logging.info("Emergency stop reset.")


# --- Automation Sequence System ---
class AutomationEngine:
    def __init__(self, plc):
        self.plc = plc
        self.running = False
        self.should_stop = False
        self.thread = None
        self.stats = {"runs": 0, "last_success": None, "errors": 0}

    # Example: Each step is a tuple (action, kwargs, wait_time)
    # e.g., steps = [("set_mm", {"v": 20.0}, 1), ("start_motor", {}, 5), ...]
    def run_sequence(self, steps, repeat=1, auto_stop=True):
        self.running = True
        self.should_stop = False
        cycle = 0
        try:
            while (repeat == 0 or cycle < repeat) and not self.should_stop and not self.plc.emergency_active:
                logging.info(f"Sequence start cycle {cycle + 1}")
                for (action, p, wait_s) in steps:
                    if self.should_stop or self.plc.emergency_active:
                        break
                    # Safety: Check for emergency stop in every step
                    if hasattr(self.plc, action):
                        fn = getattr(self.plc, action)
                        if p:
                            fn(**p)
                        else:
                            fn()
                        time.sleep(wait_s)
                        logging.info(f"Step: {action}, Params: {p}, Wait: {wait_s}s")
                cycle += 1
            self.stats["runs"] += 1
            self.stats["last_success"] = datetime.now().isoformat()
            if auto_stop: self.plc.stop_motor()
            logging.info("Sequence completed")
        except Exception as e:
            print(f"Automation error: {e}")
            logging.error(f"Automation error: {e}")
            self.stats["errors"] += 1
        self.running = False

    def start_sequence_async(self, steps, repeat=1, auto_stop=True):
        if self.running:
            print("Automation already running.")
            return
        # Start sequence in a background thread
        self.thread = threading.Thread(
            target=self.run_sequence, args=(steps, repeat, auto_stop)
        )
        self.thread.start()

    def stop(self):
        self.should_stop = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        self.running = False
        logging.info("Automation stopped by user/request.")


# --- Status Monitoring ---
class Monitor(threading.Thread):
    def __init__(self, plc, interval=2):
        super().__init__(daemon=True)
        self.plc = plc
        self.interval = interval
        self.running = True

    def run(self):
        while self.running:
            st = self.plc.get_all()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Status:", st)
            logging.info(f"Monitor status: {st}")
            time.sleep(self.interval)

    def stop(self):
        self.running = False


# --- Terminal Menu ---
def main_menu(plc, automation, monitor):
    sequences = {
        "cycle_auto": [  # Example professional sequence — edit to your process
            ("set_mm", {"v": 50.0}, 1),
            ("output_on", {}, 1),
            ("relay_on", {}, 1),
            ("start_motor", {}, 5),
            ("output_off", {}, 1),
            ("relay_off", {}, 1),
            ("stop_motor", {}, 1),
        ],
        "batch_process": [
            ("set_mm", {"v": 100.0}, 1),
            ("start_motor", {}, 3),
            ("set_mm", {"v": 110.0}, 1),
            ("start_motor", {}, 2),
            ("stop_motor", {}, 1),
        ]
    }

    while True:
        print("""
=== PLC AUTOMATION TERMINAL ===
1. Start motor    2. Stop motor
3. Activate out0  4. Deactivate out0
5. Activate relay 6. Deactivate relay
7. Set mm value   8. Print all status
9. Emergency STOP 10. Emergency RESET
11. Run seq: cycle_auto   12. Run seq: batch_process
13. Start monitoring      14. Stop monitoring
15. Stop automation       16. Automation stats
17. Exit
""")
        ch = input("Enter option: ").strip()
        try:
            if ch == "1":
                plc.start_motor()
            elif ch == "2":
                plc.stop_motor()
            elif ch == "3":
                plc.output_on()
            elif ch == "4":
                plc.output_off()
            elif ch == "5":
                plc.relay_on()
            elif ch == "6":
                plc.relay_off()
            elif ch == "7":
                mv = float(input("Enter mm value: "))
                plc.set_mm(mv)
            elif ch == "8":
                print(plc.get_all())
            elif ch == "9":
                plc.emergency_stop()
                automation.stop()
            elif ch == "10":
                plc.emergency_reset()
            elif ch == "11":
                repeat = int(input("Repeat? (0 = infinite): ") or "1")
                automation.start_sequence_async(sequences["cycle_auto"], repeat)
            elif ch == "12":
                automation.start_sequence_async(sequences["batch_process"])
            elif ch == "13":
                if not monitor.is_alive():
                    monitor.running = True
                    monitor.start()
                else:
                    print("Monitor already running.")
            elif ch == "14":
                monitor.stop()
            elif ch == "15":
                automation.stop()
            elif ch == "16":
                print(automation.stats)
            elif ch == "17":
                print("Exiting. Goodbye.")
                automation.stop()
                plc.disconnect()
                monitor.stop()
                break
        except Exception as e:
            print(f"Error: {e}")


# --- Main App ---
if __name__ == "__main__":
    plc = PLCController(PLC_URL, NODE_IDS)
    print("Connecting to PLC...")
    if not plc.connect():
        print("PLC connect failed. Exiting.")
        exit(1)
    automation = AutomationEngine(plc)
    monitor = Monitor(plc, interval=2)
    try:
        main_menu(plc, automation, monitor)
    finally:
        plc.disconnect()
        monitor.stop()
        print("Disconnected from PLC.")
