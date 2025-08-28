# Fully Autonomous PLC Control System - No Human Interaction
# Only Emergency Override Available

import time
import threading
import logging
import signal
import sys
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

# Autonomous Operation Parameters
AUTO_CONFIG = {
    "cycle_interval": 30,           # Seconds between production cycles
    "production_duration": 15,      # Seconds per production cycle
    "target_position": 85.0,        # Target LVDT position (mm)
    "position_tolerance": 3.0,       # Position accuracy tolerance
    "max_cycles_per_hour": 100,     # Safety limit
    "auto_restart_attempts": 5,      # Auto recovery attempts
    "shutdown_after_errors": 10     # Shutdown threshold
}

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('autonomous_plc.log'),
        logging.StreamHandler()
    ]
)

class AutonomousPLCSystem:
    def __init__(self):
        self.client = None
        self.connected = False
        self.system_running = True
        self.emergency_active = False
        
        # Operation tracking
        self.total_cycles = 0
        self.successful_cycles = 0
        self.error_count = 0
        self.consecutive_errors = 0
        self.start_time = datetime.now()
        
        # Threading
        self.main_thread = None
        self.monitoring_thread = None
        
        # System state
        self.current_status = {}
        self.last_cycle_time = 0
        
        # Setup emergency signal handler
        signal.signal(signal.SIGINT, self._emergency_signal_handler)
        signal.signal(signal.SIGTERM, self._emergency_signal_handler)
    
    def _emergency_signal_handler(self, signum, frame):
        """Handle emergency shutdown signals (Ctrl+C, etc.)"""
        logging.critical("🚨 EMERGENCY SIGNAL RECEIVED - INITIATING SHUTDOWN")
        self.emergency_shutdown()
        sys.exit(0)
    
    def connect_with_retry(self):
        """Connect to PLC with automatic retry"""
        max_attempts = 10
        retry_delay = 5
        
        for attempt in range(max_attempts):
            try:
                logging.info(f"🔌 Connection attempt {attempt + 1}/{max_attempts}")
                self.client = Client(PLC_URL)
                self.client.set_timeout(15)
                self.client.connect()
                self.connected = True
                
                # Verify connection with test read
                test_value = self.read_value("mm")
                if test_value is not None:
                    logging.info(f"✅ Connected successfully - LVDT: {test_value}mm")
                    return True
                else:
                    raise Exception("Test read failed")
                    
            except Exception as e:
                logging.error(f"❌ Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_attempts - 1:
                    logging.info(f"⏳ Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 30)  # Exponential backoff
        
        logging.critical("❌ All connection attempts failed - system cannot start")
        return False
    
    def read_value(self, node_key):
        """Read value with error handling"""
        if not self.connected:
            return None
        try:
            node = self.client.get_node(NODE_IDS[node_key])
            return node.get_value()
        except Exception as e:
            logging.error(f"Read error {node_key}: {e}")
            return None
    
    def write_value(self, node_key, value):
        """Write value with safety checks"""
        if not self.connected or self.emergency_active:
            return False
        try:
            node = self.client.get_node(NODE_IDS[node_key])
            node.set_value(value)
            logging.info(f"✅ {node_key} = {value}")
            return True
        except Exception as e:
            logging.error(f"Write error {node_key}: {e}")
            return False
    
    def check_emergency_conditions(self):
        """Check for emergency conditions"""
        # Hardware emergency stop
        if self.read_value('Motor_off'):
            if not self.emergency_active:
                logging.critical("🚨 HARDWARE EMERGENCY STOP DETECTED")
                self.emergency_active = True
            return True
        
        # LVDT out of range
        mm_value = self.read_value("mm")
        if mm_value and (mm_value < 0 or mm_value > 120):
            logging.critical(f"🚨 LVDT OUT OF SAFE RANGE: {mm_value}mm")
            self.emergency_active = True
            return True
        
        # Too many consecutive errors
        if self.consecutive_errors >= AUTO_CONFIG["shutdown_after_errors"]:
            logging.critical(f"🚨 TOO MANY ERRORS ({self.consecutive_errors}) - EMERGENCY SHUTDOWN")
            self.emergency_active = True
            return True
        
        return False
    
    def emergency_shutdown(self):
        """Execute immediate emergency shutdown"""
        logging.critical("🚨 EXECUTING EMERGENCY SHUTDOWN")
        self.emergency_active = True
        self.system_running = False
        
        # Force all outputs OFF
        emergency_commands = [
            ("Relay1", False),
            ("operational_bearing_on", False), 
            ("operational_staff_on", False)
        ]
        
        for node_key, value in emergency_commands:
            try:
                if self.connected:
                    node = self.client.get_node(NODE_IDS[node_key])
                    node.set_value(value)
                    logging.critical(f"Emergency OFF: {node_key}")
            except Exception as e:
                logging.critical(f"CRITICAL: Emergency shutdown failed for {node_key}: {e}")
    
    def autonomous_production_cycle(self):
        """Execute one autonomous production cycle"""
        cycle_start = time.time()
        self.total_cycles += 1
        
        logging.info(f"🔄 Autonomous Cycle #{self.total_cycles} Starting")
        
        try:
            # Phase 1: Safety verification
            if self.check_emergency_conditions():
                return False
            
            # Phase 2: System initialization
            logging.info("🔧 Initializing systems...")
            self.write_value("operational_staff_on", True)
            time.sleep(1)
            self.write_value("operational_bearing_on", True)
            time.sleep(2)
            
            # Phase 3: Start production
            logging.info("⚡ Starting production...")
            self.write_value("Relay1", True)
            
            # Phase 4: Monitor production progress
            production_start = time.time()
            target_reached = False
            
            while (time.time() - production_start) < AUTO_CONFIG["production_duration"]:
                # Continuous safety monitoring
                if self.check_emergency_conditions():
                    logging.error("❌ Emergency during production - aborting cycle")
                    break
                
                # Check production progress
                mm_value = self.read_value("mm")
                if mm_value and mm_value >= AUTO_CONFIG["target_position"]:
                    logging.info(f"✅ Target position reached: {mm_value}mm")
                    target_reached = True
                    break
                
                time.sleep(0.5)  # High frequency monitoring
            
            # Phase 5: Production shutdown
            logging.info("🛑 Stopping production...")
            self.write_value("Relay1", False)
            time.sleep(1)
            self.write_value("operational_bearing_on", False)
            time.sleep(1) 
            self.write_value("operational_staff_on", False)
            
            # Phase 6: Cycle completion
            cycle_duration = time.time() - cycle_start
            
            if target_reached:
                self.successful_cycles += 1
                self.consecutive_errors = 0
                logging.info(f"✅ Cycle #{self.total_cycles} SUCCESS ({cycle_duration:.1f}s)")
                return True
            else:
                self.consecutive_errors += 1
                logging.warning(f"⚠️ Cycle #{self.total_cycles} INCOMPLETE ({cycle_duration:.1f}s)")
                return False
                
        except Exception as e:
            self.error_count += 1
            self.consecutive_errors += 1
            logging.error(f"❌ Cycle #{self.total_cycles} ERROR: {e}")
            
            # Emergency shutdown on critical errors
            self.emergency_shutdown()
            return False
    
    def autonomous_main_loop(self):
        """Main autonomous operation loop - runs forever until emergency"""
        logging.info("🤖 AUTONOMOUS OPERATION STARTED - NO HUMAN INTERACTION REQUIRED")
        logging.info("🚨 Press Ctrl+C for EMERGENCY STOP ONLY")
        
        while self.system_running and not self.emergency_active:
            try:
                # Check if it's time for next cycle
                current_time = time.time()
                if current_time - self.last_cycle_time >= AUTO_CONFIG["cycle_interval"]:
                    
                    # Safety pre-check
                    if not self.check_emergency_conditions():
                        # Execute production cycle
                        self.autonomous_production_cycle()
                        self.last_cycle_time = current_time
                        
                        # Brief pause between cycles
                        time.sleep(2)
                    else:
                        # Emergency detected - wait for manual intervention
                        logging.critical("🚨 SYSTEM HALTED - EMERGENCY INTERVENTION REQUIRED")
                        self.wait_for_emergency_reset()
                else:
                    # Wait until next cycle time
                    time.sleep(1)
                
                # Periodic status logging (every 60 seconds)
                if int(current_time) % 60 == 0:
                    self.log_system_status()
                    
            except Exception as e:
                logging.critical(f"💥 CRITICAL SYSTEM ERROR: {e}")
                self.emergency_shutdown()
                break
        
        logging.critical("🛑 AUTONOMOUS OPERATION STOPPED")
    
    def wait_for_emergency_reset(self):
        """Wait for emergency condition to be cleared (human intervention)"""
        logging.critical("⏸️ WAITING FOR EMERGENCY RESET...")
        print("\n" + "="*60)
        print("🚨 EMERGENCY STOP ACTIVE - HUMAN INTERVENTION REQUIRED")
        print("="*60)
        print("System is HALTED and waiting for:")
        print("1. Clear hardware emergency stop")
        print("2. Fix any mechanical issues")
        print("3. Press ENTER to attempt restart")
        print("   OR Ctrl+C to shutdown permanently")
        print("="*60)
        
        try:
            input()  # Wait for human confirmation
            
            # Attempt to reset
            if not self.read_value('Motor_off'):
                self.emergency_active = False
                self.consecutive_errors = 0
                logging.info("✅ Emergency reset - resuming autonomous operation")
                print("✅ EMERGENCY CLEARED - Resuming autonomous operation...")
            else:
                logging.warning("⚠️ Hardware emergency still active")
                print("⚠️ Hardware emergency stop still active - cannot resume")
                
        except KeyboardInterrupt:
            logging.critical("🚨 PERMANENT SHUTDOWN REQUESTED")
            self.emergency_shutdown()
            sys.exit(0)
    
    def log_system_status(self):
        """Log periodic system status"""
        runtime = datetime.now() - self.start_time
        success_rate = (self.successful_cycles / max(self.total_cycles, 1)) * 100
        
        status = {
            "mm": self.read_value("mm"),
            "Motor_off": self.read_value("Motor_off"),
            "Relay1": self.read_value("Relay1"),
            "operational_bearing_on": self.read_value("operational_bearing_on")
        }
        
        logging.info(f"📊 STATUS - Runtime: {runtime}, Cycles: {self.total_cycles}, "
                    f"Success: {success_rate:.1f}%, Errors: {self.error_count}, "
                    f"Position: {status['mm']}mm, Emergency: {status['Motor_off']}")
    
    def start_monitoring(self):
        """Start background monitoring"""
        def monitor():
            while self.system_running:
                try:
                    self.current_status = {key: self.read_value(key) for key in NODE_IDS.keys()}
                    time.sleep(5)
                except:
                    pass
        
        self.monitoring_thread = threading.Thread(target=monitor, daemon=True)
        self.monitoring_thread.start()
    
    def run_autonomous_system(self):
        """Start the fully autonomous system"""
        logging.info("🚀 STARTING AUTONOMOUS PLC SYSTEM")
        
        # Connect to PLC
        if not self.connect_with_retry():
            logging.critical("❌ Cannot establish PLC connection - system cannot start")
            return False
        
        # Start background monitoring
        self.start_monitoring()
        
        # Initial safety check
        if self.check_emergency_conditions():
            logging.critical("❌ Emergency condition detected at startup")
            self.wait_for_emergency_reset()
        
        # Start main autonomous loop
        self.autonomous_main_loop()
        
        # Cleanup
        if self.client and self.connected:
            self.client.disconnect()
        
        # Final status report
        runtime = datetime.now() - self.start_time
        logging.info(f"📊 FINAL STATS - Runtime: {runtime}, Total Cycles: {self.total_cycles}, "
                    f"Successful: {self.successful_cycles}, Errors: {self.error_count}")
        
        return True

def main():
    """Main entry point"""
    print("🤖 FULLY AUTONOMOUS PLC CONTROL SYSTEM")
    print("🚨 NO HUMAN INTERACTION - EMERGENCY OVERRIDE ONLY")
    print("⚠️  Press Ctrl+C for EMERGENCY STOP")
    print("\nStarting autonomous operation...\n")
    
    system = AutonomousPLCSystem()
    system.run_autonomous_system()
    
    print("\n✅ System shutdown complete")

if __name__ == "__main__":
    main()