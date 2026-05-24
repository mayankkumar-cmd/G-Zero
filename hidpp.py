import time
import threading
import hid

LOGITECH_VID = 0x046D
FEATURE_ADJUSTABLE_DPI = 0x2201

class HIDPP20Device:
    """Handles low-level Logitech HID++ 2.0 communication with the G304/G305 mouse."""
    
    def __init__(self, path=None):
        self.path = path
        self.device = None
        self.feature_idx = None
        self.battery_feature_idx = None
        self.fw_feature_idx = None
        self.name_feature_idx = None
        self.current_dpi = None
        self.lock = threading.Lock()

    def check_for_errors(self, res):
        """Checks a response packet for standard HID++ 2.0 error reports and raises ConnectionError if found."""
        if res and len(res) >= 6 and res[2] == 0x8F:
            err_code = res[5]
            err_map = {
                0: "No error",
                1: "Unknown error",
                2: "Invalid argument",
                3: "Parameter out of range",
                4: "Hardware error",
                5: "Logitech internal error",
                6: "Invalid feature index",
                7: "Invalid function ID",
                8: "Device is busy. Nudge the mouse and try again.",
                9: "Feature or command unsupported"
            }
            err_text = err_map.get(err_code, f"Unknown HID++ error (code {err_code})")
            raise ConnectionError(f"HID++ Error: {err_text}")

    def get_feature_index(self, feature_id):
        """Queries the root feature table for the 1-based index of a feature ID."""
        if not self.device:
            return None
        try:
            # IRoot GetFeature command: Function 0, software ID 1
            # Feature ID is 16-bit big-endian
            packet_root = [0x11, 0x01, 0x00, 0x00, feature_id >> 8, feature_id & 0xFF] + [0]*14
            self.device.write(packet_root)
            res = self.device.read(20, timeout_ms=800)
            self.check_for_errors(res)
            if res and len(res) >= 5 and res[3] == 0x00:
                return res[4]
            return None
        except:
            return None

    def open(self):
        """Attempts to open the control interface and query dynamic feature indices."""
        with self.lock:
            try:
                # Find the receiver control interface if path is not provided
                if not self.path:
                    for device in hid.enumerate():
                        if device['vendor_id'] == LOGITECH_VID:
                            if device['interface_number'] == 2 and device['usage_page'] == 0xFF00 and device['usage'] == 0x02:
                                self.path = device['path']
                                break
                
                if not self.path:
                    raise ConnectionError("G304/G305 receiver control interface not found.")

                self.device = hid.device()
                self.device.open_path(self.path)
                
                # Flush read queue before sending commands
                self.flush()
                
                # Query root feature table for dynamic feature indices
                self.feature_idx = self.get_feature_index(0x2201)  # Adjustable DPI
                
                if self.feature_idx and self.feature_idx > 0:
                    self.battery_feature_idx = self.get_feature_index(0x1000)  # Battery Status
                    self.fw_feature_idx = self.get_feature_index(0x0003)  # Firmware Info
                    self.name_feature_idx = self.get_feature_index(0x0005)  # Device Name
                    return True
                else:
                    self.close()
                    raise ConnectionError("Mouse is asleep. Move the mouse to connect.")
            except Exception as e:
                self.close()
                raise e

    def get_battery_status(self):
        """Queries the current battery status (percentage and charging state)."""
        with self.lock:
            if not self.device or not self.battery_feature_idx:
                return None
            
            try:
                self.flush()
                # Function 0: GetBatteryLevelStatus, software ID 1 -> Byte 3 is 0x01
                packet_get = [0x11, 0x01, self.battery_feature_idx, 0x01] + [0]*16
                self.device.write(packet_get)
                res = self.device.read(20, timeout_ms=500)
                self.check_for_errors(res)
                
                if res and res[3] == 0x01:
                    pct = res[4]  # Byte 4: BatteryDischargeLevel in %
                    status_val = res[6]  # Byte 6: BatteryStatus enum
                    
                    status_map = {
                        0: "Discharging",
                        1: "Recharging",
                        2: "Final Stage",
                        3: "Complete",
                        4: "Low Charging",
                        5: "Invalid",
                        6: "Thermal Error",
                        7: "Charge Error"
                    }
                    status_text = status_map.get(status_val, "Unknown")
                    return {
                        "percentage": pct,
                        "status": status_text
                    }
                return None
            except:
                return None

    def get_firmware_info(self):
        """Queries firmware information (prefix, version, build) of the main application."""
        with self.lock:
            if not self.device or not self.fw_feature_idx:
                return None
            
            try:
                self.flush()
                # Function 1: GetFwInfo, entity = 0, software ID 1 -> Byte 3 is 0x11, Byte 4 is 0x00
                packet_get = [0x11, 0x01, self.fw_feature_idx, 0x11, 0x00] + [0]*15
                self.device.write(packet_get)
                res = self.device.read(20, timeout_ms=500)
                self.check_for_errors(res)
                
                if res and res[3] == 0x11:
                    # Bytes 5, 6, 7: FwPrefix (3 ASCII chars)
                    prefix = "".join(chr(res[i]) for i in (5, 6, 7) if 32 <= res[i] <= 126)
                    # Bytes 8, 9: FwVersion (BCD format)
                    version = f"{res[8]:02X}.{res[9]:02X}"
                    # Bytes 10, 11: FwBuild (16-bit)
                    build = (res[10] << 8) | res[11]
                    return f"{prefix} {version} (Build {build:04d})"
                return None
            except:
                return None

    def get_device_name(self):
        """Queries the product name of the connected device directly from dynamic feature 0x0005."""
        with self.lock:
            if not self.device or not self.name_feature_idx:
                return None
            
            try:
                self.flush()
                # Function 0: GetCount, software ID 1 -> Byte 3 is 0x01
                packet_count = [0x11, 0x01, self.name_feature_idx, 0x01] + [0]*16
                self.device.write(packet_count)
                res = self.device.read(20, timeout_ms=500)
                self.check_for_errors(res)
                
                if res and res[3] == 0x01:
                    name_length = res[4]
                    if name_length == 0:
                        return None
                        
                    name_bytes = bytearray()
                    char_offset = 0
                    while char_offset < name_length:
                        self.flush()
                        # Function 1: GetDeviceName, Byte 4: charIndex, software ID 1 -> Byte 3 is 0x11
                        packet_name = [0x11, 0x01, self.name_feature_idx, 0x11, char_offset] + [0]*15
                        self.device.write(packet_name)
                        res = self.device.read(20, timeout_ms=500)
                        self.check_for_errors(res)
                        
                        if res and res[3] == 0x11:
                            chunk_size = min(15, name_length - char_offset)
                            name_bytes.extend(res[5:5+chunk_size])
                            char_offset += 15
                        else:
                            break
                    
                    device_name = name_bytes.decode('ascii', errors='ignore').strip()
                    device_name = "".join(ch for ch in device_name if 32 <= ord(ch) <= 126)
                    return device_name if device_name else None
                return None
            except:
                return None

    def flush(self):
        """Clears all pending reports in the read buffer."""
        if self.device:
            while True:
                res = self.device.read(20, timeout_ms=2)
                if not res:
                    break

    def get_dpi(self):
        """Queries the current active hardware DPI of the mouse."""
        with self.lock:
            if not self.device or not self.feature_idx:
                raise ConnectionError("Device not connected.")
            
            try:
                self.flush()
                # Function 2: GetSensorDpi
                packet_get = [0x11, 0x01, self.feature_idx, 0x21, 0x00] + [0]*15
                self.device.write(packet_get)
                res = self.device.read(20, timeout_ms=500)
                self.check_for_errors(res)
                
                if res and res[3] == 0x21:
                    dpi = (res[5] << 8) | res[6]
                    self.current_dpi = dpi
                    return dpi
                raise ConnectionError("Mouse is asleep. Move the mouse to activate.")
            except Exception as e:
                raise e

    def set_dpi(self, dpi_val):
        """Sets the current active hardware DPI of the mouse."""
        with self.lock:
            if not self.device or not self.feature_idx:
                raise ConnectionError("Device not connected.")
            
            # Bound check
            dpi_val = int(dpi_val)
            dpi_val = round(dpi_val / 50) * 50
            dpi_val = max(200, min(12000, dpi_val))
            
            try:
                self.flush()
                # Function 3: SetSensorDpi
                packet_set = [0x11, 0x01, self.feature_idx, 0x31, 0x00, dpi_val >> 8, dpi_val & 0xFF] + [0]*13
                self.device.write(packet_set)
                
                res = self.device.read(20, timeout_ms=800)
                self.check_for_errors(res)
                if res and res[3] == 0x31:
                    self.current_dpi = dpi_val
                    return dpi_val
                raise ConnectionError("Failed to apply DPI. Move the mouse constantly to wake it up.")
            except Exception as e:
                raise e

    def close(self):
        """Safely closes the device."""
        if self.device:
            try:
                self.device.close()
            except:
                pass
            self.device = None
            self.feature_idx = None
            self.battery_feature_idx = None
            self.fw_feature_idx = None
            self.name_feature_idx = None
