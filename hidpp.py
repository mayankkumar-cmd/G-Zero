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
        self.current_dpi = None
        self.lock = threading.Lock()

    def open(self):
        """Attempts to open the control interface and query the adjustable DPI feature index."""
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
                
                # Query root feature table for Adjustable DPI (0x2201) index
                packet_root = [0x11, 0x01, 0x00, 0x01, 0x22, 0x01] + [0]*14
                self.device.write(packet_root)
                res = self.device.read(20, timeout_ms=800)
                
                if res and len(res) >= 5:
                    self.feature_idx = res[4]
                    return True
                else:
                    self.close()
                    raise ConnectionError("Mouse is asleep. Move the mouse to connect.")
            except Exception as e:
                self.close()
                raise e

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
