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
        self.report_rate_feature_idx = None
        self.onboard_profiles_feature_idx = None
        self.current_dpi = None
        # Sensor DPI capabilities, resolved from the hardware on open().
        # These defaults only apply if the sensor never answers getSensorDpiList.
        self.dpi_min = 200
        self.dpi_max = 12000
        self.dpi_step = 50
        self.dpi_list = None
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
                # Find any Logitech device with standard HID++ 2.0 endpoint (Usage Page 0xFF00, Usage 0x02)
                if not self.path:
                    for device in hid.enumerate():
                        if device['vendor_id'] == LOGITECH_VID:
                            if device['usage_page'] == 0xFF00 and device['usage'] == 0x02:
                                self.path = device['path']
                                break
                
                if not self.path:
                    raise ConnectionError("Logitech HID++ 2.0 device control interface not found.")

                self.device = hid.device()
                self.device.open_path(self.path)
                
                # Flush read queue before sending commands
                self.flush()
                
                # Query root feature table for dynamic feature indices
                self.feature_idx = self.get_feature_index(0x2201)  # Adjustable DPI
                
                if self.feature_idx and self.feature_idx > 0:
                    self.query_dpi_capabilities()  # Resolve the sensor's real DPI range
                    self.battery_feature_idx = self.get_feature_index(0x1000)  # Battery Status
                    self.fw_feature_idx = self.get_feature_index(0x0003)  # Firmware Info
                    self.name_feature_idx = self.get_feature_index(0x0005)  # Device Name
                    self.report_rate_feature_idx = self.get_feature_index(0x8060)  # Adjustable Report Rate
                    self.onboard_profiles_feature_idx = self.get_feature_index(0x8100)  # Onboard Profiles
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

    def query_dpi_capabilities(self):
        """Reads the sensor's supported DPI range from feature 0x2201 Function 1 (GetSensorDpiList).

        The caller must already hold self.lock (this is invoked from open()).

        The 7 big-endian 16-bit values returned by the sensor are either a discrete list of
        selectable DPI values, or a range where a value above 0xE000 encodes the step size
        (step = value - 0xE000) and the surrounding values are the range bounds. Either form
        is terminated by a 0x0000 entry. If parsing yields nothing usable the conservative
        defaults set in __init__ are left in place.
        """
        if not self.device or not self.feature_idx:
            return

        try:
            self.flush()
            # Function 1: GetSensorDpiList, sensor 0, software ID 1 -> Byte 3 is 0x11
            packet_get = [0x11, 0x01, self.feature_idx, 0x11, 0x00] + [0]*15
            self.device.write(packet_get)
            res = self.device.read(20, timeout_ms=500)
            self.check_for_errors(res)

            if not res or res[3] != 0x11:
                return

            # Byte 4 echoes the sensor index; the list occupies bytes 5..18
            values = []
            step = None
            for i in range(7):
                raw = (res[5 + i*2] << 8) | res[6 + i*2]
                if raw == 0:
                    break
                if raw > 0xE000:
                    step = raw - 0xE000
                else:
                    values.append(raw)

            if not values:
                return

            if step:
                # Range form: first value is the minimum, last is the maximum
                self.dpi_min = min(values)
                self.dpi_max = max(values)
                self.dpi_step = step
                self.dpi_list = None
            else:
                # Discrete form: only the listed values are selectable
                self.dpi_list = sorted(set(values))
                self.dpi_min = self.dpi_list[0]
                self.dpi_max = self.dpi_list[-1]
                self.dpi_step = None
        except:
            # Sensor asleep or the function is unsupported; keep the defaults
            pass

    def clamp_dpi(self, dpi_val):
        """Clamps and snaps a DPI value onto the grid the sensor actually accepts.

        Pure arithmetic against the cached capabilities, so it takes no lock and is safe to
        call from the UI thread or from inside an already-locked method such as set_dpi().
        """
        dpi_val = int(dpi_val)

        if self.dpi_list:
            # Discrete sensors only accept listed values; pick the closest one
            return min(self.dpi_list, key=lambda v: abs(v - dpi_val))

        step = self.dpi_step or 50
        dpi_val = max(self.dpi_min, min(self.dpi_max, dpi_val))
        # Snap onto the step grid anchored at the sensor minimum, not at zero
        snapped = self.dpi_min + round((dpi_val - self.dpi_min) / step) * step
        return int(max(self.dpi_min, min(self.dpi_max, snapped)))

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
                    # Never clamp below a DPI the hardware is already running at; covers
                    # sensors whose capability query failed or under-reported its range
                    if dpi > self.dpi_max:
                        self.dpi_max = dpi
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
            
            # Bound check against the sensor's own reported capabilities
            dpi_val = self.clamp_dpi(dpi_val)

            try:
                # Silently disable Onboard Profiles if the feature is supported
                # This switches the mouse to Host Mode, which is required to change settings on some mice!
                if self.onboard_profiles_feature_idx:
                    try:
                        self.flush()
                        # Function 2: Query Onboard Profiles State -> Byte 3 is 0x21
                        packet_check = [0x11, 0x01, self.onboard_profiles_feature_idx, 0x21] + [0]*16
                        self.device.write(packet_check)
                        res_check = self.device.read(20, timeout_ms=500)
                        if res_check and res_check[3] == 0x21 and res_check[4] == 0x01:
                            # Onboard Mode is active (0x01). Switch to Host Mode (0x02) via Function 1 (0x11)
                            self.flush()
                            packet_disable = [0x11, 0x01, self.onboard_profiles_feature_idx, 0x11, 0x02] + [0]*15
                            self.device.write(packet_disable)
                            res_disable = self.device.read(20, timeout_ms=500)
                            self.check_for_errors(res_disable)
                    except:
                        # If Onboard Profiles fail to disable, proceed with setting DPI anyway
                        pass

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

    def get_report_rate(self):
        """Queries the current active report rate (polling rate) in milliseconds."""
        with self.lock:
            if not self.device or not self.report_rate_feature_idx:
                return None
            
            try:
                self.flush()
                # Function 1: GetReportRate, software ID 1 -> Byte 3 is 0x11
                packet_get = [0x11, 0x01, self.report_rate_feature_idx, 0x11] + [0]*16
                self.device.write(packet_get)
                res = self.device.read(20, timeout_ms=500)
                self.check_for_errors(res)
                
                if res and res[3] == 0x11:
                    rate_ms = res[4]
                    return rate_ms
                return None
            except Exception as e:
                return None

    def set_report_rate(self, rate_ms):
        """Sets the current report rate (polling rate) in milliseconds."""
        with self.lock:
            if not self.device or not self.report_rate_feature_idx:
                raise ConnectionError("Device not connected or Report Rate feature unsupported.")
            
            try:
                # Silently disable Onboard Profiles if the feature is supported
                # This switches the mouse to Host Mode, which is required to change report rate!
                if self.onboard_profiles_feature_idx:
                    try:
                        self.flush()
                        # Function 2: Query Onboard Profiles State -> Byte 3 is 0x21
                        packet_check = [0x11, 0x01, self.onboard_profiles_feature_idx, 0x21] + [0]*16
                        self.device.write(packet_check)
                        res_check = self.device.read(20, timeout_ms=500)
                        if res_check and res_check[3] == 0x21 and res_check[4] == 0x01:
                            # Onboard Mode is active (0x01). Switch to Host Mode (0x02) via Function 1 (0x11)
                            self.flush()
                            packet_disable = [0x11, 0x01, self.onboard_profiles_feature_idx, 0x11, 0x02] + [0]*15
                            self.device.write(packet_disable)
                            res_disable = self.device.read(20, timeout_ms=500)
                            self.check_for_errors(res_disable)
                    except:
                        # If Onboard Profiles fail to disable, proceed with report rate set anyway
                        pass

                self.flush()
                # Function 2: SetReportRate, software ID 1 -> Byte 3 is 0x21
                packet_set = [0x11, 0x01, self.report_rate_feature_idx, 0x21, rate_ms] + [0]*15
                self.device.write(packet_set)
                res = self.device.read(20, timeout_ms=500)
                self.check_for_errors(res)
                
                if res and res[3] == 0x21:
                    confirmed_rate = res[4]
                    return confirmed_rate
                raise ConnectionError("Failed to apply Report Rate.")
            except Exception as e:
                raise e

    def get_supported_report_rates(self):
        """Queries the supported report rates as a list of millisecond values."""
        with self.lock:
            if not self.device or not self.report_rate_feature_idx:
                return []
            
            try:
                self.flush()
                # Function 0: GetReportRateList, software ID 1 -> Byte 3 is 0x01
                packet_get = [0x11, 0x01, self.report_rate_feature_idx, 0x01] + [0]*16
                self.device.write(packet_get)
                res = self.device.read(20, timeout_ms=500)
                self.check_for_errors(res)
                
                if res and res[3] == 0x01:
                    rate_flags = res[4]
                    rates = []
                    # Choices universe: 1=1ms, 2=2ms, 3=3ms, 4=4ms, 5=5ms, 6=6ms, 7=7ms, 8=8ms
                    for i in range(8):
                        if (rate_flags >> i) & 0x01:
                            rates.append(i + 1)
                    return rates
                return []
            except Exception as e:
                return []

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
            self.report_rate_feature_idx = None
            self.onboard_profiles_feature_idx = None
            # Reset sensor capabilities so a different mouse is re-profiled on reconnect
            self.dpi_min = 200
            self.dpi_max = 12000
            self.dpi_step = 50
            self.dpi_list = None
