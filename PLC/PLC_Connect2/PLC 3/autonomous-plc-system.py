#!/usr/bin/env python3
"""
Fully Autonomous PLC Control System - No Human Interaction Unless Emergency
Controls PLC via OPC UA with complete automation and safety systems
"""

import time
import threading
import logging
from datetime import datetime
from opcua import Client, ua
import sys

# PLC Configuration with your specific Node IDs
PLC_URL = "opc.tcp://10.10.14.113:4840"
NODE_IDS = {
    "Motor_off": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Motor_off",
    "Opration_Bering_On": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Opration_Bering_On",
    "Opration_Shaft_On": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Opration_Shaft_On",
    "output0": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.output0",
    "Relay1": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay1",
    "Relay2": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay2",
    "Relay3": "ns=4;s=|var|AX-308EA0MA1P.Application.PLC_PRG.Relay3",
    "mm": "ns=4;s=|var|AX-308EA0MA1P.Application.GVL.mm"
}

# Safety and operational parameters
SAFETY_LIMITS = {
    "min_position": 0.0,  # Minimum LVDT position (mm)
    "max_position": 100.0,  # Maximum LVDT position (mm)
    "target_position": 85.0,  # Target completion position (mm)
    "position_tolerance": 2.0,  # Position accuracy tolerance
    "cycle_timeout": 30.0,  # Maximum time for one cycle (seconds)
    "cycle_interval": 30.0,  # Time between cycles (seconds)
    "production_time": 15.0  # Maximum production time per cycle
}

# Configure logging
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
        self.autonomous_running = False
        self.emergency_active = False
        self.monitoring_active = False

        # Threading
        self.autonomous_thread = None
        self.monitoring_thread = None
        self.emergency_thread = None

        # System state
        self.current_status = {}
        self.cycle_count = 0
        self.error_count = 0
        self.consecutive_errors = 0
        self.start_time = datetime.now()

        # Safety flags
        self.position_out_of_range = False
        self.last_successful_cycle = None

    def connect(self):
        """Connect to PLC with retry logic"""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                logging.info(f"Connection attempt {attempt + 1}/{max_retries}")
                self.client = Client(PLC_URL)
                self.client.set_timeout(10)
                self.client.connect()
                self.connected = True
                logging.info("✅ Connected to PLC successfully")

                # Initial safety check
                self._initial_safety_check()
                return True

            except Exception as e:
                logging.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

        logging.error("❌ All connection attempts failed")
        return False

    def disconnect(self):
        """Safely disconnect from PLC"""
        self.stop_autonomous_operation()
        self.stop_monitoring()

        if self.client and self.connected:
            try:
                # Ensure all outputs are safe before disconnect
                self._safe_shutdown_sequence()
                self.client.disconnect()
                self.connected = False
                logging.info("✅ Disconnected from PLC")
            except Exception as e:
                logging.error(f"Disconnect error: {e}")

    def read_value(self, node_key):
        """Read value from PLC with error handling"""
        if not self.connected:
            return None

        try:
            node = self.client.get_node(NODE_IDS[node_key])
            value = node.get_value()
            return value
        except Exception as e:
            logging.error(f"Read error for {node_key}: {e}")
            self.error_count += 1
            self.consecutive_errors += 1
            return None

    def write_value(self, node_key, value):
        """Write value to PLC with safety checks"""
        if not self.connected:
            return False

        # Emergency override check
        if self.emergency_active and node_key in ["Relay1", "Opration_Bering_On", "Opration_Shaft_On"]:
            logging.warning(f"Emergency active - write blocked for {node_key}")
            return False

        try:
            node = self.client.get_node(NODE_IDS[node_key])
            dtype = node.get_data_type_as_variant_type()
            variant = ua.Variant(value, dtype)
            node.set_value(variant)

            logging.info(f"✅ Write: {node_key} = {value}")
            self.consecutive_errors = 0  # Reset error counter on success
            return True

        except Exception as e:
            logging.error(f"Write error for {node_key}: {e}")
            self.error_count += 1
            self.consecutive_errors += 1

            # Trigger emergency on too many consecutive errors
            if self.consecutive_errors >= 10:
                logging.critical("Too many consecutive errors - triggering emergency stop")
                self.emergency_stop()

            return False

    def read_all_status(self):
        """Read all PLC variables and update status"""
        status = {}
        for key in NODE_IDS.keys():
            status[key] = self.read_value(key)

        self.current_status = status
        return status

    def _initial_safety_check(self):
        """Perform initial safety verification"""
        logging.info("🔍 Performing initial safety check...")

        status = self.read_all_status()

        # Check emergency stop status
        if status.get('Motor_off', False):
            self.emergency_active = True
            logging.warning("⚠️ Emergency stop detected during startup")

        # Check LVDT position
        mm_value = status.get('mm', 0)
        if mm_value is not None:
            if mm_value < SAFETY_LIMITS['min_position'] or mm_value > SAFETY_LIMITS['max_position']:
                self.position_out_of_range = True
                logging.warning(f"⚠️ LVDT position out of range: {mm_value}mm")

        logging.info("✅ Initial safety check completed")

    def emergency_stop(self):
        """Execute emergency stop sequence"""
        logging.critical("🚨 EMERGENCY STOP ACTIVATED!")
        self.emergency_active = True
        self.autonomous_running = False

        # Emergency shutdown sequence
        emergency_commands = [
            ("Relay1", False),  # Motor off
            ("Opration_Bering_On", False),  # Bearing off
            ("Opration_Shaft_On", False),  # Shaft safety off
            ("Relay2", False),  # Hydraulic reverse off
            ("Relay3", False),  # Hydraulic forward off
            ("Motor_off", True)  # Safety cut active
        ]

        for node_key, value in emergency_commands:
            try:
                node = self.client.get_node(NODE_IDS[node_key])
                dtype = node.get_data_type_as_variant_type()
                variant = ua.Variant(value, dtype)
                node.set_value(variant)
                logging.critical(f"Emergency: {node_key} = {value}")
            except Exception as e:
                logging.critical(f"CRITICAL: Failed emergency stop for {node_key}: {e}")

        logging.critical("🚨 Emergency stop sequence completed")

    def _safe_shutdown_sequence(self):
        """Safe shutdown of all systems"""
        logging.info("🛑 Executing safe shutdown sequence...")

        shutdown_commands = [
            ("Relay1", False),
            ("Opration_Bering_On", False),
            ("Opration_Shaft_On", False),
            ("Relay2", False),
            ("Relay3", False)
        ]

        for node_key, value in shutdown_commands:
            self.write_value(node_key, value)
            time.sleep(0.5)

    def reset_emergency(self):
        """Reset emergency stop condition after verification"""
        if not self.read_value('Motor_off'):  # Verify hardware emergency is cleared
            self.emergency_active = False
            self.position_out_of_range = False
            self.consecutive_errors = 0
            logging.info("✅ Emergency stop reset - system ready")
            return True
        else:
            logging.warning("⚠️ Cannot reset - hardware emergency still active")
            return False

    def check_safety_interlocks(self):
        """Comprehensive safety interlock checking"""
        # Read current status
        status = self.read_all_status()

        # Check emergency stop
        if status.get('Motor_off', False):
            if not self.emergency_active:
                logging.warning("⚠️ Hardware emergency stop detected")
                self.emergency_stop()
            return False

        # Check LVDT position limits
        mm_value = status.get('mm')
        if mm_value is not None:
            if mm_value < SAFETY_LIMITS['min_position'] or mm_value > SAFETY_LIMITS['max_position']:
                if not self.position_out_of_range:
                    logging.warning(f"⚠️ Position safety limit exceeded: {mm_value}mm")
                    self.position_out_of_range = True
                    self.emergency_stop()
                return False
            else:
                self.position_out_of_range = False

        # Check hydraulic conflict
        if status.get('Relay2', False) and status.get('Relay3', False):
            logging.error("⚠️ Hydraulic conflict detected!")
            self.emergency_stop()
            return False

        # Check consecutive errors
        if self.consecutive_errors >= 5:
            logging.warning(f"⚠️ High error count: {self.consecutive_errors}")
            return False

        return True

    def execute_production_cycle(self):
        """Execute one complete production cycle"""
        cycle_number = self.cycle_count + 1
        logging.info(f"🔄 Starting production cycle #{cycle_number}")

        cycle_start_time = time.time()

        try:
            # Phase 1: Safety verification
            if not self.check_safety_interlocks():
                logging.error("❌ Safety interlock failed - cycle aborted")
                return False

            # Phase 2: System initialization
            logging.info("Phase 1: Initializing operational systems")

            # Enable staff safety first
            if not self.write_value("Opration_Shaft_On", True):
                return False
            time.sleep(1)

            # Enable bearing system
            if not self.write_value("Opration_Bering_On", True):
                return False
            time.sleep(2)

            # Clear motor safety cut
            if not self.write_value("Motor_off", False):
                return False
            time.sleep(1)

            # Phase 3: Start production
            logging.info("Phase 2: Starting motor")
            if not self.write_value("Relay1", True):
                return False

            # Phase 4: Monitor production progress
            logging.info("Phase 3: Monitoring production")
            production_start = time.time()
            max_production_time = SAFETY_LIMITS['production_time']
            target_position = SAFETY_LIMITS['target_position']

            while (time.time() - production_start) < max_production_time and self.autonomous_running:
                # Safety check during operation
                if not self.check_safety_interlocks():
                    logging.error("❌ Safety interlock during production")
                    break

                # Read sensors
                mm_value = self.read_value("mm")
                motor_feedback = self.read_value("output0")

                if mm_value is not None:
                    logging.info(f"Production progress: Position={mm_value:.1f}mm, Motor={motor_feedback}")

                    # Check for completion
                    if mm_value >= target_position:
                        logging.info(f"✅ Target position reached: {mm_value}mm")
                        break

                time.sleep(1)

            # Phase 5: Production shutdown
            logging.info("Phase 4: Stopping production")

            # Stop motor
            self.write_value("Relay1", False)
            time.sleep(1)

            # Disable bearing system
            self.write_value("Opration_Bering_On", False)
            time.sleep(1)

            # Disable staff safety
            self.write_value("Opration_Shaft_On", False)
            time.sleep(1)

            # Activate safety cut
            self.write_value("Motor_off", True)

            # Phase 6: Cycle completion
            cycle_duration = time.time() - cycle_start_time
            self.cycle_count += 1
            self.last_successful_cycle = datetime.now()

            logging.info(f"✅ Cycle #{self.cycle_count} completed in {cycle_duration:.1f}s")
            return True

        except Exception as e:
            logging.error(f"❌ Cycle error: {e}")
            self.emergency_stop()
            return False

    def autonomous_operation_loop(self):
        """Main autonomous operation loop"""
        logging.info("🤖 Autonomous operation started")

        while self.autonomous_running:
            try:
                # Safety check before cycle
                if self.check_safety_interlocks():
                    # Execute production cycle
                    success = self.execute_production_cycle()

                    if success:
                        logging.info(
                            f"✅ Cycle complete. Waiting {SAFETY_LIMITS['cycle_interval']}s before next cycle...")
                        # Wait between cycles while checking for emergency
                        for _ in range(int(SAFETY_LIMITS['cycle_interval'])):
                            if not self.autonomous_running or self.emergency_active:
                                break
                            time.sleep(1)
                    else:
                        logging.error("❌ Cycle failed - extended wait before retry")
                        time.sleep(60)  # Wait 1 minute on failure
                else:
                    logging.warning("⚠️ Safety interlock active - waiting...")
                    time.sleep(5)

            except Exception as e:
                logging.error(f"❌ Autonomous operation error: {e}")
                self.emergency_stop()
                break

        logging.info("🛑 Autonomous operation stopped")

    def monitoring_loop(self):
        """Continuous system monitoring"""
        logging.info("📊 System monitoring started")

        while self.monitoring_active:
            try:
                status = self.read_all_status()

                # Log comprehensive status every 60 seconds
                mm_value = status.get('mm', 0)
                motor_on = status.get('Relay1', False)
                motor_feedback = status.get('output0', False)
                emergency = status.get('Motor_off', False)
                bearing_on = status.get('Opration_Bering_On', False)
                shaft_on = status.get('Opration_Shaft_On', False)

                logging.info(f"📊 Status - Pos: {mm_value}mm, Motor: {motor_on}/{motor_feedback}, "
                             f"Emergency: {emergency}, Bearing: {bearing_on}, Shaft: {shaft_on}")

                # Check for anomalies
                if motor_on and not motor_feedback:
                    logging.warning("⚠️ Motor command ON but no feedback - potential issue")

                time.sleep(60)  # Monitor every minute

            except Exception as e:
                logging.error(f"Monitoring error: {e}")
                time.sleep(10)

        logging.info("📊 Monitoring stopped")

    def emergency_input_loop(self):
        """Emergency input detection"""
        logging.info("🚨 Emergency input monitoring started")
        logging.info("Press Ctrl+C at any time for emergency stop")

        try:
            while self.autonomous_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.critical("🚨 EMERGENCY STOP - Keyboard interrupt detected!")
            self.emergency_stop()

    def start_autonomous_operation(self):
        """Start autonomous operation"""
        if not self.connected:
            logging.error("❌ Not connected to PLC")
            return False

        if self.autonomous_running:
            logging.warning("⚠️ Autonomous operation already running")
            return False

        # Reset emergency if cleared
        if self.emergency_active:
            if not self.reset_emergency():
                logging.error("❌ Cannot start - emergency stop active")
                return False

        # Start all threads
        self.autonomous_running = True

        # Start autonomous operation
        self.autonomous_thread = threading.Thread(target=self.autonomous_operation_loop, daemon=True)
        self.autonomous_thread.start()

        # Start monitoring
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitoring_thread.start()

        # Start emergency input detection
        self.emergency_thread = threading.Thread(target=self.emergency_input_loop, daemon=True)
        self.emergency_thread.start()

        logging.info("✅ Autonomous operation started - system is now fully automatic")
        return True

    def stop_autonomous_operation(self):
        """Stop autonomous operation"""
        self.autonomous_running = False

        # Wait for threads to finish
        if self.autonomous_thread and self.autonomous_thread.is_alive():
            self.autonomous_thread.join(timeout=10)

        # Safe shutdown
        self._safe_shutdown_sequence()

        logging.info("🛑 Autonomous operation stopped")

    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)

    def get_system_statistics(self):
        """Get comprehensive system statistics"""
        runtime = datetime.now() - self.start_time

        return {
            "System Runtime": str(runtime),
            "Total Cycles": self.cycle_count,
            "Total Errors": self.error_count,
            "Consecutive Errors": self.consecutive_errors,
            "Emergency Status": "ACTIVE" if self.emergency_active else "Clear",
            "Autonomous Running": self.autonomous_running,
            "Last Successful Cycle": self.last_successful_cycle.strftime(
                "%Y-%m-%d %H:%M:%S") if self.last_successful_cycle else "None",
            "Current Position": f"{self.current_status.get('mm', 'N/A')} mm"
        }

    def print_system_status(self):
        """Print comprehensive system status"""
        print("\n" + "=" * 70)
        print("              AUTONOMOUS PLC SYSTEM STATUS")
        print("=" * 70)

        stats = self.get_system_statistics()
        status = self.current_status

        print(f"🔌 Connection: {'Connected' if self.connected else 'Disconnected'}")
        print(f"🤖 Autonomous Mode: {'RUNNING' if self.autonomous_running else 'STOPPED'}")
        print(f"🚨 Emergency: {stats['Emergency Status']}")
        print(f"📈 Cycles Completed: {stats['Total Cycles']}")
        print(f"⚠️ Total Errors: {stats['Total Errors']}")
        print(f"🕐 Runtime: {stats['System Runtime']}")

        print(f"\n📍 Current PLC Values:")
        print(f"   LVDT Position: {status.get('mm', 'N/A')} mm")
        print(f"   Motor Control (Relay1): {'ON' if status.get('Relay1', False) else 'OFF'}")
        print(f"   Motor Feedback (output0): {'ON' if status.get('output0', False) else 'OFF'}")
        print(f"   Safety Cut (Motor_off): {'ACTIVE' if status.get('Motor_off', False) else 'Clear'}")
        print(f"   Bearing System: {'ON' if status.get('Opration_Bering_On', False) else 'OFF'}")
        print(f"   Shaft Safety: {'ON' if status.get('Opration_Shaft_On', False) else 'OFF'}")
        print(f"   Hydraulic Forward: {'ON' if status.get('Relay3', False) else 'OFF'}")
        print(f"   Hydraulic Reverse: {'ON' if status.get('Relay2', False) else 'OFF'}")

        print("=" * 70)


def main():
    """Main program - Fully Autonomous Operation"""
    print("🏭 AUTONOMOUS PLC CONTROL SYSTEM")
    print("=" * 50)
    print("This system will operate autonomously without human interaction.")
    print("Press Ctrl+C at any time for emergency stop.")
    print("=" * 50)

    # Create system instance
    system = AutonomousPLCSystem()

    try:
        # Connect to PLC
        print("\n🔌 Connecting to PLC...")
        if not system.connect():
            print("❌ Cannot connect to PLC. Exiting.")
            return

        # Show initial status
        system.read_all_status()
        system.print_system_status()

        # Start autonomous operation
        print("\n🤖 Starting autonomous operation...")
        if system.start_autonomous_operation():
            print("✅ System is now running autonomously!")
            print("📊 Status updates will appear every 60 seconds.")
            print("🚨 Use Ctrl+C for emergency stop.")

            # Keep main thread alive
            while system.autonomous_running:
                time.sleep(60)
                system.print_system_status()

        else:
            print("❌ Failed to start autonomous operation")

    except KeyboardInterrupt:
        print("\n🚨 EMERGENCY STOP REQUESTED!")
        system.emergency_stop()

    except Exception as e:
        logging.error(f"❌ System error: {e}")
        system.emergency_stop()

    finally:
        print("\n🛑 Shutting down system...")
        system.disconnect()
        print("✅ System shutdown complete")
        print("📝 Check 'autonomous_plc.log' for complete operation log")


if __name__ == "__main__":
    main()
