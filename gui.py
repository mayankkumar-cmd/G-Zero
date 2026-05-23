import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import hid
from hidpp import HIDPP20Device

class GZeroGUI:
    """Manages the modern dark-themed user interface and events for the DPI Controller."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("G-Zero DPI Controller")
        self.root.geometry("480x420")
        self.root.resizable(False, False)
        
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
        
        # Setup modern styles and draw components
        self.setup_styles()
        self.build_ui()
        
        # Start connection & health check background thread
        self.polling_thread = threading.Thread(target=self.device_polling_loop, daemon=True)
        self.polling_thread.start()
        
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
        
        title_label = tk.Label(title_frame, text="LIGHTSPEED", font=("Helvetica", 10, "bold"), fg=self.colors["accent"], bg=self.colors["bg"])
        title_label.pack(anchor="w")
        
        subtitle_label = tk.Label(title_frame, text="G-Zero Customizer", font=("Helvetica", 16, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        subtitle_label.pack(anchor="w")

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
        
        # DPI display readout
        dpi_readout_frame = tk.Frame(self.card, bg=self.colors["card"], pady=10)
        dpi_readout_frame.pack(fill="x", padx=20)
        
        self.dpi_val_label = tk.Label(dpi_readout_frame, text="---", font=("Helvetica", 36, "bold"), fg=self.colors["text_secondary"], bg=self.colors["card"])
        self.dpi_val_label.pack(side="left")
        
        self.dpi_suffix = tk.Label(dpi_readout_frame, text="DPI", font=("Helvetica", 14, "bold"), fg=self.colors["accent"], bg=self.colors["card"])
        self.dpi_suffix.pack(side="left", padx=10, pady=15)
        
        # 3. Slider sensitivity bar
        slider_frame = tk.Frame(self.card, bg=self.colors["card"], pady=15)
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
        tk.Label(bounds_frame, text="12000 DPI", font=("Helvetica", 8), fg=self.colors["text_secondary"], bg=self.colors["card"]).pack(side="right")

        # 4. Presets buttons
        presets_frame = tk.Frame(self.card, bg=self.colors["card"], pady=10)
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
            
        # 5. Bottom apply outline button
        bottom_frame = tk.Frame(self.root, bg=self.colors["bg"], pady=15)
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

    def update_ui_connected(self, dpi):
        self.draw_status_dot(self.colors["success"])
        self.status_label.configure(text="Connected (G304 / G305 Lightspeed)", fg=self.colors["success"])
        
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

    def update_ui_disconnected(self, message):
        self.draw_status_dot(self.colors["warning"])
        self.status_label.configure(text=message, fg=self.colors["text_secondary"])
        self.dpi_val_label.configure(text="---", fg=self.colors["text_secondary"])
        
        self.slider.configure(state="disabled")
        self.apply_btn.configure(
            state="disabled", 
            bg=self.colors["card"], 
            fg=self.colors["text_secondary"],
            highlightbackground=self.colors["border"]
        )
        for btn in self.preset_buttons:
            btn.configure(state="disabled", fg=self.colors["text_secondary"])

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
            self.root.after(0, lambda: self.update_ui_connected(confirmed_dpi))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showwarning("Connection Warning", str(e)))

    def device_polling_loop(self):
        """Monitors and maintains real-time communication with the mouse."""
        while self.running:
            time.sleep(1.0)
            
            if self.mouse.device:
                # Active connection, query current DPI value
                if self.is_dragging:
                    continue
                try:
                    dpi = self.mouse.get_dpi()
                    self.root.after(0, lambda d=dpi: self.update_ui_connected(d))
                except Exception as e:
                    # Connection failed
                    self.mouse.close()
                    self.root.after(0, lambda: self.update_ui_disconnected("Connecting to mouse..."))
            else:
                # Disconnected, try scanned reconnection
                try:
                    success = self.mouse.open()
                    if success:
                        dpi = self.mouse.get_dpi()
                        self.root.after(0, lambda d=dpi: self.update_ui_connected(d))
                    else:
                        self.root.after(0, lambda: self.update_ui_disconnected("Mouse is asleep. Move the mouse to connect."))
                except Exception as e:
                    self.root.after(0, lambda: self.update_ui_disconnected(str(e)))
