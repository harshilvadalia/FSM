# Autonomous PLC System - START and EMERGENCY Commands Only

import time
import threading
import logging
import signal
import sys
import msvcrt
from datetime import datetime
from opcua import Client, ua

# PLC Configuration
PLC_URL = "opc.tcp://10.10.14.113:4840"
NODE_IDS = {
    "mm": "ns=4;s=|var|AX-308EA0MA1P.Application.GVL.mm",                           # LVDT sensor
    "Motor_off": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Motor_off",         # Emergency stop
    "output0": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.output0",             # Motor status
    "Relay2": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay2",               # Hydraulic backward
    "Relay3": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay3",               # Hydraulic forward
    "Relay1": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay1",               # Motor control
    "operational_bearing_on": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.operational_bearing_on",
    "operational_staff_on": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.operational_staff_on"
}

# Autonomous Configuration
CONFIG = {
    "cycle_interval": 30,        # Seconds between cycles
    "production_time": 15,       # Production duration per cycle
    "target_position": 85.0,     # Target LVDT position (mm)
    "max_position": 100.0,       # Safety limit
    "min_position": 0.0          # Safety limit
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autonomous_plc.log'),
        logging.StreamHandler()
    ]
)

class AutonomousPLC:
    def __init__(self):
        self.client = None
        self.connected = False
        self.running = False
        self.emergency = False
        
        # Statistics
        self.cycles_completed = 0
        self.start_time = None
        
        # Threads
        self.main_thread = None
        self.input_thread = None
    
    def connect(self):
        """Connect to PLC"""
        try:
            self.client = Client(PLC_URL)
            self.client.connect()
            self.connected = True
            logging.info("✅ Connected to PLC")
            return True
        except Exception as e:
            logging.error(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from PLC"""
        if self.client and self.connected:
            self.client.disconnect()
            self.connected = False
            logging.info("✅ Disconnected from PLC")
    
    def read(self, key):
        """Read PLC value"""
        if not self.connected:
            return None
        try:
            node = self.client.get_node(NODE_IDS[key])
            return node.get_value()
        except Exception as e:
            logging.error(f"Read error {key}: {e}")
            return None
    
    def write(self, key, value):
        """Write PLC value"""
        if not self.connected or self.emergency:
            return False
        try:
            node = self.client.get_node(NODE_IDS[key])
            node.set_value(value)
            logging.info(f"✅ {key} = {value}")
            return True
        except Exception as e:
            logging.error(f"Write error {key}: {e}")
            return False
    
    def emergency_stop(self):
        """Execute emergency stop"""
        logging.critical("🚨 EMERGENCY STOP ACTIVATED!")
        self.emergency = True
        self.running = False
        
        # Turn off all outputs immediately
        try:
            if self.connected:
                self.client.get_node(NODE_IDS["Relay1"]).set_value(False)
                self.client.get_node(NODE_IDS["operational_bearing_on"]).set_value(False) 
                self.client.get_node(NODE_IDS["operational_staff_on"]).set_value(False)
                logging.critical("🚨 All outputs disabled")
        except Exception as e:
            logging.critical(f"CRITICAL: Emergency stop failed: {e}")
    
    def production_cycle(self):
        """Execute one production cycle"""
        cycle_num = self.cycles_completed + 1
        logging.info(f"🔄 Starting Cycle #{cycle_num}")
        
        try:
            # Check safety before starting
            mm_value = self.read("mm")
            motor_off = self.read("Motor_off")
            
            if motor_off:
                logging.error("❌ Hardware emergency active - cycle aborted")
                self.emergency_stop()
                return False
            
            if mm_value and (mm_value < CONFIG["min_position"] or mm_value > CONFIG["max_position"]):
                logging.error(f"❌ Position out of range: {mm_value}mm - cycle aborted")
                self.emergency_stop()
                return False
            
            # Start production sequence
            logging.info("🔧 Starting systems...")
            self.write("operational_staff_on", True)
            time.sleep(1)
            self.write("operational_bearing_on", True) 
            time.sleep(2)
            
            logging.info("⚡ Starting motor...")
            self.write("Relay1", True)
            
            # Monitor production
            start_time = time.time()
            target_reached = False
            
            while (time.time() - start_time) < CONFIG["production_time"] and self.running:
                # Safety check during operation
                if self.read("Motor_off"):
                    logging.error("❌ Hardware emergency during production!")
                    self.emergency_stop()
                    return False
                
                # Check progress
                mm_value = self.read("mm")
                if mm_value and mm_value >= CONFIG["target_position"]:
                    logging.info(f"✅ Target reached: {mm_value}mm")
                    target_reached = True
                    break
                
                time.sleep(0.5)
            
            # Stop production
            logging.info("🛑 Stopping production...")
            self.write("Relay1", False)
            time.sleep(1)
            self.write("operational_bearing_on", False)
            time.sleep(1)
            self.write("operational_staff_on", False)
            
            if target_reached:
                self.cycles_completed += 1
                logging.info(f"✅ Cycle #{cycle_num} completed successfully")
                return True
            else:
                logging.warning(f"⚠️ Cycle #{cycle_num} incomplete")
                return False
                
        except Exception as e:
            logging.error(f"❌ Cycle error: {e}")
            self.emergency_stop()
            return False
    
    def autonomous_operation(self):
        """Main autonomous operation loop"""
        logging.info("🤖 AUTONOMOUS OPERATION STARTED")
        self.start_time = datetime.now()
        
        while self.running and not self.emergency:
            try:
                # Execute production cycle
                self.production_cycle()
                
                if self.running and not self.emergency:
                    # Wait between cycles
                    logging.info(f"⏳ Waiting {CONFIG['cycle_interval']} seconds until next cycle...")
                    
                    for i in range(CONFIG["cycle_interval"]):
                        if not self.running or self.emergency:
                            break
                        time.sleep(1)
                
            except Exception as e:
                logging.critical(f"💥 Critical error in autonomous operation: {e}")
                self.emergency_stop()
                break
        
        logging.info("🛑 Autonomous operation stopped")
    
    def input_monitor(self):
        """Monitor for emergency key press"""
        print("\n🚨 EMERGENCY: Press 'E' key anytime for emergency stop")
        print("📊 System will show status every 60 seconds")
        print("-" * 50)
        
        while self.running and not self.emergency:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                if key == 'e':
                    print("\n🚨 EMERGENCY KEY PRESSED!")
                    self.emergency_stop()
                    break
            time.sleep(0.1)
    
    def status_monitor(self):
        """Show periodic status updates"""
        last_status_time = time.time()
        
        while self.running and not self.emergency:
            current_time = time.time()
            
            # Show status every 60 seconds
            if current_time - last_status_time >= 60:
                runtime = datetime.now() - self.start_time if self.start_time else "N/A"
                mm_value = self.read("mm")
                motor_on = self.read("Relay1")
                
                print(f"\n📊 STATUS UPDATE:")
                print(f"   Runtime: {runtime}")
                print(f"   Cycles completed: {self.cycles_completed}")
                print(f"   Current position: {mm_value}mm")
                print(f"   Motor running: {motor_on}")
                print(f"   Emergency: {self.emergency}")
                print("-" * 50)
                
                last_status_time = current_time
            
            time.sleep(5)
    
    def start_system(self):
        """Start the autonomous system"""
        print("🔌 Connecting to PLC...")
        if not self.connect():
            print("❌ Cannot connect to PLC. System cannot start.")
            return False
        
        print("✅ Connected to PLC")
        
        # Check initial safety
        if self.read("Motor_off"):
            print("⚠️ Hardware emergency stop is active. Please clear it first.")
            self.disconnect()
            return False
        
        print("🤖 Starting autonomous operation...")
        self.running = True
        
        # Start threads
        self.main_thread = threading.Thread(target=self.autonomous_operation, daemon=True)
        self.input_thread = threading.Thread(target=self.input_monitor, daemon=True)
        status_thread = threading.Thread(target=self.status_monitor, daemon=True)
        
        self.main_thread.start()
        self.input_thread.start()
        status_thread.start()
        
        print("✅ System started - Running autonomously...")
        
        # Wait for threads to complete
        try:
            while self.running and not self.emergency:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🚨 Ctrl+C pressed - Emergency stop!")
            self.emergency_stop()
        
        # Cleanup
        self.disconnect()
        
        # Final statistics
        runtime = datetime.now() - self.start_time if self.start_time else "N/A"
        print(f"\n📊 FINAL STATISTICS:")
        print(f"   Total runtime: {runtime}")
        print(f"   Cycles completed: {self.cycles_completed}")
        print(f"   Emergency stopped: {self.emergency}")
        
        return True

def main():
    """Main program with START and EMERGENCY commands only"""
    system = AutonomousPLC()
    
    print("="*60)
    print("    AUTONOMOUS PLC CONTROL SYSTEM")
    print("    NO HUMAN INTERACTION MODE")
    print("="*60)
    print()
    print("Available commands:")
    print("  [S] START  - Begin autonomous operation")  
    print("  [E] EMERGENCY - Stop all operations immediately")
    print()
    
    while True:
        command = input("Enter command (S=Start, E=Emergency, Q=Quit): ").strip().lower()
        
        if command == 's':
            print("\n🚀 STARTING AUTONOMOUS SYSTEM...")
            print("⚠️  Once started, system runs without human interaction")
            print("🚨 Press 'E' key during operation for emergency stop")
            
            confirm = input("\nConfirm start autonomous operation? (Y/N): ").strip().lower()
            if confirm == 'y':
                system.start_system()
                print("\n✅ Autonomous operation completed")
            else:
                print("❌ Start cancelled")
                
        elif command == 'e':
            print("🚨 EMERGENCY STOP command acknowledged")
            if system.running:
                system.emergency_stop()
                print("✅ Emergency stop executed")
            else:
                print("ℹ️ System is not running")
                
        elif command == 'q':
            print("👋 Exiting...")
            if system.running:
                system.emergency_stop()
            break
            
        else:
            print("❌ Invalid command. Use S, E, or Q")

if __name__ == "__main__":
    main()