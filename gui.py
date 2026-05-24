import sys
import os
import time
import threading
import subprocess
import urllib.request
import json
import tkinter as tk
from tkinter import ttk, messagebox
import hid
from hidpp import HIDPP20Device

class GZeroGUI:
    """Manages the modern dark-themed user interface and events for the DPI Controller."""

    def __init__(self, root):
        self.root = root
        self.root.title("G-Zero DPI Controller")
        self.root.geometry("480x460")
        self.root.resizable(False, False)
        self.version = "v0.3"
        self.update_url = None
        self.update_tag = None

        # Color Palette - Premium Modern Dark Mode
        self.colors = {
            "bg": "#121214",
            "card": "#1C1C1F",
            "accent": "#00C2FF",        # Glowing Cyan
            "accent_hover": "#0099C7",
            "text": "#FFFFFF",
            "text_secondary": "#8E8E93",
            "success": "#34C759",
            "warning": "#FF9500",
            "danger": "#FF3B30",
            "border": "#2C2C2E"
        }

        self.root.configure(bg=self.colors["bg"])

        # Hardware backend
        self.mouse = HIDPP20Device()

        # State variables
        self.running = True
        self.is_dragging = False
        self.cached_fw_info = None
        self.cached_device_name = None

        # Setup modern styles and draw components
        self.setup_styles()
        self.build_ui()

        # Start connection & health check background thread
        self.polling_thread = threading.Thread(target=self.device_polling_loop, daemon=True)
        self.polling_thread.start()

        # Start background check for application updates on GitHub Releases
        self.update_thread = threading.Thread(target=self.check_for_app_updates, daemon=True)
        self.update_thread.start()

        # Intercept window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Horizontal.TScale",
                        background=self.colors["card"],
                        troughcolor=self.colors["bg"],
                        slidercolor=self.colors["accent"],
                        sliderthickness=14)

    def build_ui(self):
        # 1. Title bar
        title_frame = tk.Frame(self.root, bg=self.colors["bg"], pady=15)
        title_frame.pack(fill="x", padx=25)

        # Left side of Title Bar: Labels
        labels_sub_frame = tk.Frame(title_frame, bg=self.colors["bg"])
        labels_sub_frame.pack(side="left")

        title_label = tk.Label(labels_sub_frame, text="LIGHTSPEED", font=("Helvetica", 10, "bold"), fg=self.colors["accent"], bg=self.colors["bg"])
        title_label.pack(anchor="w")

        self.subtitle_label = tk.Label(labels_sub_frame, text="G-Zero Customizer", font=("Helvetica", 16, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        self.subtitle_label.pack(anchor="w")

        # Right side of Title Bar: Glowing update button (hidden by default)
        self.update_btn = tk.Button(
            title_frame,
            text="",
            font=("Helvetica", 8, "bold"),
            fg=self.colors["accent"],
            bg=self.colors["bg"],
            activebackground=self.colors["accent"],
            activeforeground=self.colors["bg"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["border"],
            padx=10,
            pady=4,
            command=self.start_download
        )
        # Packed dynamically when an update is found

        # 2. Main display card
        self.card = tk.Frame(self.root, bg=self.colors["card"], bd=1, relief="flat", highlightbackground=self.colors["border"], highlightcolor=self.colors["border"], highlightthickness=1)
        self.card.pack(fill="both", expand=True, padx=25, pady=5)

        # Connection status sub-bar
        status_frame = tk.Frame(self.card, bg=self.colors["card"], pady=10)
        status_frame.pack(fill="x", padx=20)

        self.status_dot = tk.Canvas(status_frame, width=12, height=12, bg=self.colors["card"], highlightthickness=0)
        self.status_dot.pack(side="left")
        self.draw_status_dot(self.colors["warning"])

        self.status_label = tk.Label(status_frame, text="Scanning for receiver...", font=("Helvetica", 9, "medium" if sys.platform != "win32" else "bold"), fg=self.colors["text_secondary"], bg=self.colors["card"])
        self.status_label.pack(side="left", padx=8)

        # DPI display readout & Battery card
        dpi_readout_frame = tk.Frame(self.card, bg=self.colors["card"], pady=10)
        dpi_readout_frame.pack(fill="x", padx=20)

        self.dpi_val_label = tk.Label(dpi_readout_frame, text="---", font=("Helvetica", 36, "bold"), fg=self.colors["text_secondary"], bg=self.colors["card"])
        self.dpi_val_label.pack(side="left")

        self.dpi_suffix = tk.Label(dpi_readout_frame, text="DPI", font=("Helvetica", 14, "bold"), fg=self.colors["accent"], bg=self.colors["card"])
        self.dpi_suffix.pack(side="left", padx=10, pady=15)

        # Battery display container on the right
        self.battery_frame = tk.Frame(dpi_readout_frame, bg=self.colors["bg"], bd=1, relief="flat", highlightbackground=self.colors["border"], highlightcolor=self.colors["border"], highlightthickness=1, padx=12, pady=6)
        self.battery_frame.pack(side="right", padx=5)

        battery_sub_left = tk.Frame(self.battery_frame, bg=self.colors["bg"])
        battery_sub_left.pack(side="left", padx=(0, 8))

        self.battery_canvas = tk.Canvas(battery_sub_left, width=32, height=16, bg=self.colors["bg"], highlightthickness=0)
        self.battery_canvas.pack(anchor="w")

        self.battery_state_label = tk.Label(battery_sub_left, text="---", font=("Helvetica", 7, "bold"), fg=self.colors["text_secondary"], bg=self.colors["bg"])
        self.battery_state_label.pack(anchor="w", pady=(2, 0))

        self.battery_pct_label = tk.Label(self.battery_frame, text="--%", font=("Helvetica", 20, "bold"), fg=self.colors["text_secondary"], bg=self.colors["bg"])
        self.battery_pct_label.pack(side="right")

        # 3. Slider sensitivity bar
        slider_frame = tk.Frame(self.card, bg=self.colors["card"], pady=12)
        slider_frame.pack(fill="x", padx=20)

        self.dpi_var = tk.IntVar(value=800)
        self.slider = ttk.Scale(slider_frame, from_=200, to=12000, variable=self.dpi_var, orient="horizontal", style="Horizontal.TScale", command=self.on_slider_move)
        self.slider.pack(fill="x")
        self.slider.configure(state="disabled")

        self.slider.bind("<Button-1>", self.on_slider_press)
        self.slider.bind("<ButtonRelease-1>", self.on_slider_release)

        bounds_frame = tk.Frame(slider_frame, bg=self.colors["card"])
        bounds_frame.pack(fill="x", pady=4)
        tk.Label(bounds_frame, text="200 DPI", font=("Helvetica", 8), fg=self.colors["text_secondary"], bg=self.colors["card"]).pack(side="left")
        self.max_bound_label = tk.Label(bounds_frame, text="12000 DPI", font=("Helvetica", 8), fg=self.colors["text_secondary"], bg=self.colors["card"])
        self.max_bound_label.pack(side="right")

        # 4. Presets buttons
        presets_frame = tk.Frame(self.card, bg=self.colors["card"], pady=8)
        presets_frame.pack(fill="x", padx=20)

        presets_label = tk.Label(presets_frame, text="QUICK PRESETS", font=("Helvetica", 8, "bold"), fg=self.colors["text_secondary"], bg=self.colors["card"])
        presets_label.pack(anchor="w", pady=5)

        buttons_layout_frame = tk.Frame(presets_frame, bg=self.colors["card"])
        buttons_layout_frame.pack(fill="x")

        self.preset_values = [400, 800, 1600, 3200]
        self.preset_buttons = []
        for val in self.preset_values:
            btn = self.create_modern_button(buttons_layout_frame, f"{val}", lambda v=val: self.apply_dpi(v))
            btn.pack(side="left", expand=True, fill="x", padx=4)
            btn.configure(state="disabled")
            self.preset_buttons.append(btn)

        # 5. Telemetry diagnostics row
        telemetry_frame = tk.Frame(self.card, bg=self.colors["card"])
        telemetry_frame.pack(fill="x", padx=20, pady=(10, 12))

        divider = tk.Frame(telemetry_frame, height=1, bg=self.colors["border"])
        divider.pack(fill="x", pady=(0, 8))

        self.telemetry_label = tk.Label(telemetry_frame, text="SYS: G304/G305 | FW: Unknown | PROT: HID++ 2.0", font=("Consolas", 8), fg=self.colors["text_secondary"], bg=self.colors["card"])
        self.telemetry_label.pack(anchor="w")

        # 6. Bottom apply outline button
        bottom_frame = tk.Frame(self.root, bg=self.colors["bg"], pady=12)
        bottom_frame.pack(fill="x", padx=25)

        self.apply_btn = tk.Button(
            bottom_frame,
            text="APPLY HARDWARE DPI",
            font=("Helvetica", 9, "bold"),
            fg=self.colors["text_secondary"],
            bg=self.colors["card"],
            activebackground=self.colors["accent"],
            activeforeground=self.colors["bg"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["border"],
            padx=18,
            pady=8,
            command=lambda: self.apply_dpi(self.dpi_var.get())
        )
        self.apply_btn.pack(side="right")
        self.apply_btn.configure(state="disabled")

        self.apply_btn.bind("<Enter>", self.on_apply_enter)
        self.apply_btn.bind("<Leave>", self.on_apply_leave)

        # Initial draw of battery canvas
        self.draw_battery(0, "Disconnected")

    def draw_status_dot(self, color):
        self.status_dot.delete("all")
        self.status_dot.create_oval(2, 2, 10, 10, fill=color, outline="")

    def create_modern_button(self, parent, text, command):
        btn = tk.Button(parent, text=text, font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"], activebackground=self.colors["accent"], activeforeground=self.colors["bg"], relief="flat", bd=0, highlightthickness=1, highlightbackground=self.colors["border"], highlightcolor=self.colors["border"], pady=6, command=command)
        btn.bind("<Enter>", lambda e: btn.configure(bg=self.colors["border"]) if btn["state"] != "disabled" else None)
        btn.bind("<Leave>", lambda e: btn.configure(bg=self.colors["bg"]) if btn["state"] != "disabled" else None)
        return btn

    def on_apply_enter(self, event):
        if self.mouse.device:
            self.apply_btn.configure(
                bg=self.colors["accent"],
                fg=self.colors["bg"],
                highlightbackground=self.colors["accent"]
            )

    def on_apply_leave(self, event):
        if self.mouse.device:
            self.apply_btn.configure(
                bg=self.colors["bg"],
                fg=self.colors["accent"],
                highlightbackground=self.colors["accent"]
            )

    def on_slider_press(self, event):
        self.is_dragging = True

    def on_slider_release(self, event):
        self.is_dragging = False
        self.apply_dpi(self.dpi_var.get())

    def on_slider_move(self, val):
        dpi = int(float(val))
        snapped_dpi = round(dpi / 50) * 50
        self.dpi_var.set(snapped_dpi)
        self.dpi_val_label.configure(text=f"{snapped_dpi}")

    def on_close(self):
        self.running = False
        self.mouse.close()
        self.root.destroy()

    def draw_battery(self, pct, state):
        self.battery_canvas.delete("all")
        if state == "Disconnected" or pct == 0:
            border_color = self.colors["border"]
            fill_color = self.colors["text_secondary"]
        else:
            border_color = self.colors["accent"]
            if pct <= 15:
                fill_color = self.colors["danger"]
            elif pct <= 30:
                fill_color = self.colors["warning"]
            else:
                fill_color = self.colors["success"]

        # Outer shell
        self.battery_canvas.create_rectangle(2, 2, 26, 14, outline=border_color, width=1.5)
        # Positive terminal knob
        self.battery_canvas.create_rectangle(26, 5, 29, 11, outline=border_color, width=1.5, fill=border_color)

        # Inner fill level
        if pct > 0:
            fill_pct = min(100, max(0, pct))
            fill_width = int(20 * (fill_pct / 100))
            if fill_width > 0:
                self.battery_canvas.create_rectangle(4, 4, 4 + fill_width, 12, fill=fill_color, outline="")

    def clean_device_name(self, name):
        """Shortens long Logitech device names to keep GUI telemetry clean and prevent layout overflow."""
        if not name:
            return "G304/G305"

        # Check for specific supported models first to keep branding premium
        if "G304" in name:
            return "G304 Lightspeed" if "Lightspeed" in name else "G304"
        if "G305" in name:
            return "G305 Lightspeed" if "Lightspeed" in name else "G305"

        # Generic cleaner fallback
        suffixes = [
            " Lightspeed Wireless Gaming Mouse",
            " Wireless Gaming Mouse",
            " Gaming Mouse",
            " Lightspeed",
            " Wireless"
        ]
        cleaned = name
        for s in suffixes:
            cleaned = cleaned.replace(s, "")
        return cleaned[:20]

    def update_ui_connected(self, dpi, battery_info=None, fw_info=None, device_name=None):
        self.draw_status_dot(self.colors["success"])
        self.status_label.configure(text="Connected", fg=self.colors["success"])

        # Dynamically scale sensor bounds based on active DPI (supports high-end HERO 16K/25K sensors)
        if dpi > 12000:
            self.slider.configure(to=25600)
            self.max_bound_label.configure(text="25600 DPI")
        else:
            self.slider.configure(to=12000)
            self.max_bound_label.configure(text="12000 DPI")

        if not self.is_dragging:
            self.dpi_val_label.configure(text=f"{dpi}", fg=self.colors["text"])
            self.dpi_var.set(dpi)

        self.slider.configure(state="normal")
        self.apply_btn.configure(
            state="normal",
            fg=self.colors["accent"],
            bg=self.colors["bg"],
            highlightbackground=self.colors["accent"]
        )
        for btn in self.preset_buttons:
            btn.configure(state="normal", fg=self.colors["text"])

        # Clean and shorten name for UI layout safety
        cleaned_name = self.clean_device_name(device_name)

        # Update Header Subtitle
        if device_name:
            self.subtitle_label.configure(text=cleaned_name, fg=self.colors["text"])
        else:
            self.subtitle_label.configure(text="G-Zero Customizer", fg=self.colors["text"])

        # Update Battery status
        if battery_info:
            pct = battery_info["percentage"]
            status = battery_info["status"]
            self.battery_pct_label.configure(text=f"{pct}%", fg=self.colors["text"])
            self.battery_state_label.configure(text=status, fg=self.colors["accent"] if status != "Discharging" else self.colors["text_secondary"])
            self.draw_battery(pct, status)
        else:
            self.battery_pct_label.configure(text="--%", fg=self.colors["text_secondary"])
            self.battery_state_label.configure(text="---", fg=self.colors["text_secondary"])
            self.draw_battery(0, "Disconnected")

        # Update Firmware diagnostics telemetry row
        if fw_info:
            self.telemetry_label.configure(text=f"SYS: {cleaned_name} | FW: {fw_info} | PROT: HID++ 2.0", fg=self.colors["text_secondary"])
        else:
            self.telemetry_label.configure(text=f"SYS: {cleaned_name} | FW: Unknown | PROT: HID++ 2.0", fg=self.colors["text_secondary"])

    def update_ui_disconnected(self, message):
        self.draw_status_dot(self.colors["warning"])
        self.status_label.configure(text=message, fg=self.colors["text_secondary"])
        self.dpi_val_label.configure(text="---", fg=self.colors["text_secondary"])
        self.subtitle_label.configure(text="G-Zero Customizer", fg=self.colors["text"])

        self.slider.configure(state="disabled")
        self.apply_btn.configure(
            state="disabled",
            bg=self.colors["card"],
            fg=self.colors["text_secondary"],
            highlightbackground=self.colors["border"]
        )
        for btn in self.preset_buttons:
            btn.configure(state="disabled", fg=self.colors["text_secondary"])

        # Reset battery and firmware displays
        self.battery_pct_label.configure(text="--%", fg=self.colors["text_secondary"])
        self.battery_state_label.configure(text="---", fg=self.colors["text_secondary"])
        self.draw_battery(0, "Disconnected")
        self.telemetry_label.configure(text="SYS: G304/G305 | FW: Unknown | PROT: HID++ 2.0", fg=self.colors["text_secondary"])

    def apply_dpi(self, dpi_val):
        dpi_val = int(dpi_val)
        dpi_val = round(dpi_val / 50) * 50
        dpi_val = max(200, min(12000, dpi_val))

        self.dpi_val_label.configure(text=f"{dpi_val}")
        self.dpi_var.set(dpi_val)

        threading.Thread(target=self.bg_apply_dpi, args=(dpi_val,), daemon=True).start()

    def bg_apply_dpi(self, dpi_val):
        try:
            confirmed_dpi = self.mouse.set_dpi(dpi_val)
            # Use last fetched battery, FW and name info on instant update
            self.root.after(0, lambda: self.update_ui_connected(confirmed_dpi, self.last_battery_info, self.cached_fw_info, self.cached_device_name))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showwarning("Connection Warning", str(e)))

    def device_polling_loop(self):
        """Monitors and maintains real-time communication with the mouse."""
        poll_counter = 0
        self.last_battery_info = None
        self.cached_device_name = None

        while self.running:
            time.sleep(1.0)

            if self.mouse.device:
                if self.is_dragging:
                    continue
                try:
                    dpi = self.mouse.get_dpi()

                    # Fetch dynamic device name and firmware info once per connection
                    if not self.cached_device_name:
                        self.cached_device_name = self.mouse.get_device_name()

                    if not self.cached_fw_info:
                        self.cached_fw_info = self.mouse.get_firmware_info()

                    # Query battery status every 30 seconds to minimize receiver duty cycle
                    if poll_counter % 30 == 0 or self.last_battery_info is None:
                        self.last_battery_info = self.mouse.get_battery_status()

                    poll_counter += 1
                    self.root.after(0, lambda d=dpi, b=self.last_battery_info, f=self.cached_fw_info, n=self.cached_device_name: self.update_ui_connected(d, b, f, n))
                except Exception as e:
                    # Connection failed, reset all parameters
                    self.mouse.close()
                    self.cached_fw_info = None
                    self.cached_device_name = None
                    self.last_battery_info = None
                    poll_counter = 0
                    self.root.after(0, lambda: self.update_ui_disconnected("Connecting to mouse..."))
            else:
                # Disconnected, try scanned reconnection
                try:
                    success = self.mouse.open()
                    if success:
                        dpi = self.mouse.get_dpi()
                        self.cached_device_name = self.mouse.get_device_name()
                        self.cached_fw_info = self.mouse.get_firmware_info()
                        self.last_battery_info = self.mouse.get_battery_status()
                        poll_counter = 1
                        self.root.after(0, lambda d=dpi, b=self.last_battery_info, f=self.cached_fw_info, n=self.cached_device_name: self.update_ui_connected(d, b, f, n))
                    else:
                        self.root.after(0, lambda: self.update_ui_disconnected("Mouse is asleep. Move the mouse to connect."))
                except Exception as e:
                    self.root.after(0, lambda: self.update_ui_disconnected(str(e)))

    def check_for_app_updates(self):
        """Asynchronously checks for new G-Zero application releases on GitHub."""
        try:
            # Query the public GitHub Releases API
            req = urllib.request.Request(
                "https://api.github.com/repos/mayankkumar-cmd/G-Zero/releases/latest",
                headers={"User-Agent": "G-Zero-Updater"}
            )
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "").strip()

                # Check if a new version is available
                if latest_tag and latest_tag != self.version:
                    # Look for G-Zero.exe asset
                    assets = data.get("assets", [])
                    download_url = None
                    for asset in assets:
                        if asset.get("name") == "G-Zero.exe":
                            download_url = asset.get("browser_download_url")
                            break

                    if download_url:
                        self.update_url = download_url
                        self.update_tag = latest_tag
                        self.root.after(0, self.show_update_badge)
        except:
            pass # Fails silently in the background

    def show_update_badge(self):
        """Displays the glowing update badge at the top-right of the title bar."""
        try:
            self.update_btn.configure(text=f"✨ Update {self.update_tag}")
            self.update_btn.pack(side="right", anchor="ne", pady=5)
        except:
            pass

    def start_download(self):
        """Triggered when the user clicks the update badge; disables the button and starts background download."""
        self.update_btn.configure(state="disabled", text="Connecting...")
        threading.Thread(target=self.download_update_thread, daemon=True).start()

    def download_update_thread(self):
        """Asynchronously streams the update binary file to a local temp file and reports progress."""
        try:
            exe_path = sys.argv[0]
            exe_dir = os.path.dirname(os.path.abspath(exe_path))
            temp_exe = os.path.join(exe_dir, "temp_gzero.exe")

            req = urllib.request.Request(self.update_url, headers={"User-Agent": "G-Zero-Updater"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_read = 0
                block_size = 16384

                with open(temp_exe, "wb") as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        bytes_read += len(buffer)
                        if total_size > 0:
                            pct = int((bytes_read / total_size) * 100)
                            self.root.after(0, lambda p=pct: self.update_btn.configure(text=f"Downloading {p}%"))

            # Download complete
            self.root.after(0, self.prompt_relaunch)
        except Exception as e:
            self.root.after(0, lambda err=e: self.reset_update_btn(f"Failed: {err}"))

    def reset_update_btn(self, err_msg):
        """Resets the update button state on download failure."""
        messagebox.showerror("Update Error", err_msg)
        self.update_btn.configure(state="normal", text=f"✨ Update {self.update_tag}")

    def prompt_relaunch(self):
        """Asks the user if they want to replace the current executable and relaunch immediately."""
        if messagebox.askyesno("Update Complete", f"G-Zero {self.update_tag} has been downloaded successfully.\n\nWould you like the app to replace itself and relaunch now?"):
            self.apply_update_and_relaunch()
        else:
            self.update_btn.configure(state="normal", text="✨ Relaunch Ready")

    def apply_update_and_relaunch(self):
        """Spawns a hidden background PowerShell script to securely swap binaries and relaunches G-Zero."""
        try:
            exe_path = sys.argv[0]
            exe_dir = os.path.dirname(os.path.abspath(exe_path))
            temp_exe = os.path.join(exe_dir, "temp_gzero.exe")

            # Handle python source mode safely
            if not exe_path.lower().endswith(".exe"):
                messagebox.showinfo("Update Complete", "Running in Python source mode. The updated executable has been downloaded as 'temp_gzero.exe' inside your project root directory!")
                return

            # Cleanse environment dictionary to prevent the new PyInstaller process
            # from inheriting the old, now-deleted _MEIPASS temp directory keys!
            clean_env = os.environ.copy()
            for key in list(clean_env.keys()):
                if "MEI" in key or "PYI" in key:
                    del clean_env[key]
            
            if "PATH" in clean_env:
                paths = clean_env["PATH"].split(os.pathsep)
                cleaned_paths = [p for p in paths if "_MEI" not in p]
                clean_env["PATH"] = os.pathsep.join(cleaned_paths)

            # Sanitized PowerShell swapping script with robust retries and asynchronous file lock bypass
            # This handles slow OS releases of G-Zero.exe safely.
            ps_script = f"""
            $pid_to_wait = {os.getpid()}
            
            while (Get-Process -Id $pid_to_wait -ErrorAction SilentlyContinue) {{
                Start-Sleep -Milliseconds 100
            }}
            
            $success = $false
            # Attempt to move the file with up to 15 retries (handles asynchronous OS file release)
            for ($i = 0; $i -lt 15; $i++) {{
                try {{
                    if (Test-Path "{temp_exe}") {{
                        Move-Item -Path "{temp_exe}" -Destination "{exe_path}" -Force -ErrorAction Stop
                        $success = $true
                        break
                    }} else {{
                        break
                    }}
                }} catch {{
                    Start-Sleep -Milliseconds 300
                }}
            }}
            
            if ($success) {{
                Start-Process "explorer.exe" -ArgumentList "`"{exe_path}`""
            }}
            """

            # Spawn PowerShell completely silently in the background (no window flashed)
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env=clean_env
            )

            # Terminate current instance immediately to let PowerShell swap
            self.on_close()
        except Exception as e:
            messagebox.showerror("Update Error", f"Failed to execute dynamic self-updater: {e}")
            self.update_btn.configure(state="normal", text="✨ Relaunch Ready")
