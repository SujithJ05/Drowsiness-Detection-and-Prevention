import serial
import serial.tools.list_ports
import time
import threading
from abc import ABC, abstractmethod
from src import config

class HardwareInterface(ABC):
    """
    Abstract base class for hardware communication.
    Allows swapping between real Arduino and a Mock for research/testing.
    """
    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def check_status(self):
        pass

    @abstractmethod
    def apply_brakes(self):
        pass

    @abstractmethod
    def release_brakes(self):
        pass

    @abstractmethod
    def send_warning(self):
        pass

    @abstractmethod
    def close(self):
        pass


class MockHardware(HardwareInterface):
    """
    Simulated hardware for testing algorithms without physical device.
    Logs actions to console/file instead of Serial.
    """
    def __init__(self):
        self.connected = False
        print("[MockHardware] Initialized in simulation mode.")

    def connect(self):
        self.connected = True
        print("[MockHardware] Virtual connection established.")
        return True

    def check_status(self):
        return "STATUS:NORMAL"

    def apply_brakes(self):
        print("[MockHardware] *** BRAKES APPLIED ***")
        return True

    def release_brakes(self):
        print("[MockHardware] *** BRAKES RELEASED ***")
        return True

    def send_warning(self):
        print("[MockHardware] *** WARNING SIGNAL ***")
        return True

    def close(self):
        self.connected = False
        print("[MockHardware] Connection closed.")


class ArduinoHardware(HardwareInterface):
    """
    Real implementation using Serial communication with Arduino.
    """
    def __init__(self, port=config.ARDUINO_PORT, baud_rate=config.ARDUINO_BAUD_RATE):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = config.ARDUINO_TIMEOUT
        self.ser = None
        self.connected = False
        self.lock = threading.Lock()
        
        # Heartbeat
        self.running = False
        self.heartbeat_thread = None

    def connect(self):
        try:
            print(f"Connecting to Arduino on {self.port}...")
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout
            )
            time.sleep(2)  # Wait for Arduino reset
            with self.lock:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
            self.connected = True
            print(f"Successfully connected to {self.port}")
            
            # Start Heartbeat
            self.running = True
            self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
            
            return True
        except Exception as e:
            print(f"Arduino connection failed: {e}")
            self.connected = False
            return False

    def _heartbeat_loop(self):
        while self.running and self.connected:
            self.send_command("HEARTBEAT", expect_response=False)
            time.sleep(config.HEARTBEAT_INTERVAL)

    def send_command(self, command, expect_response=True):
        if not self.connected or not self.ser:
            return False
        
        with self.lock:
            try:
                full_command = f"{command}\n".encode()
                self.ser.write(full_command)
                
                if expect_response:
                    time.sleep(0.05)
                    if self.ser.in_waiting > 0:
                        response = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        return response
                return True
            except Exception as e:
                print(f"Error sending {command}: {e}")
                self.connected = False
                return False

    def check_status(self):
        return self.send_command("STATUS")

    def apply_brakes(self):
        return self.send_command("BRAKE")

    def release_brakes(self):
        return self.send_command("RELEASE")

    def send_warning(self):
        return self.send_command("WARNING")

    def close(self):
        self.running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=1.0)
            
        if self.ser:
            self.release_brakes()
            with self.lock:
                self.ser.close()
            print("Arduino connection closed.")

def create_hardware_service():
    """Factory function to return the correct hardware interface."""
    if config.HARDWARE_ENABLED:
        return ArduinoHardware()
    else:
        return MockHardware()

# For backward compatibility (if needed by other imports)
HardwareService = ArduinoHardware
