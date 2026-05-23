# G-Zero: Lightweight Logitech G304/G305 DPI Controller

[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com)
[![Language: Python](https://img.shields.io/badge/Language-Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Framework: Tkinter](https://img.shields.io/badge/Framework-Tkinter-4B8BBE?style=flat-square&logo=desktop&logoColor=white)](https://docs.python.org/3/library/tkinter.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)

**G-Zero** is a modern dark-themed desktop utility for Windows designed to control the hardware DPI of the **Logitech G304 and G305 Lightspeed** gaming mice with **0% background CPU and RAM overhead**.

> [!WARNING]
> **Compatibility:** This tool is strictly compatible with the **Logitech G304** and **Logitech G305 Lightspeed** wireless gaming mice. It does not support any other Logitech models or third-party hardware.

Unlike the official **Logitech G HUB** software (which occupies over 400 MB of space, connects to the cloud, and runs background telemetry processes), **G-Zero** connects directly to the mouse hardware over USB, applies your custom settings instantly, and can be closed immediately. The mouse's physical onboard memory remembers your settings.

---

## Downloads

You do not need to install Python or set up dependencies. Go to the [GitHub Releases](https://github.com/mayankkumar-cmd/G-Zero/releases) tab and download the pre-compiled **`G-Zero.exe`** standalone executable. Double-click to run it instantly.

---

## Features

- 🔋 **Zero Background Overhead:** Configure your DPI in seconds and exit. The mouse retains the active settings at the hardware level.
- 🎛️ **DPI Slider:** Snaps and applies DPI settings directly on mouse release (ranges from `200` to `12000` in steps of `50`).
- ⚡ **Instant Presets:** Quick-select buttons for standard sensitivities (`400`, `800`, `1600`, `3200` DPI).
- 🔄 **Non-Blocking Background Polling:** The USB communication operates on a separate background thread with hardware locks, ensuring the GUI remains fully responsive even if the mouse goes to sleep.
- 💡 **Wake Warning:** Automated on-screen status indicator informing you if your wireless mouse has gone to sleep.

---

## Project Structure

```
G-Zero/
├── main.py            # High-DPI entry point (initializes Tkinter)
├── gui.py             # Modern flat dark card layout, button animations, and event hooks
├── hidpp.py           # Low-level Logitech HID++ 2.0 communication, packet framing, and USB writes
├── requirements.txt   # Project dependencies list
├── .gitignore         # Excluded files list for Git
└── README.md          # Documentation
```

---

## Running from Source (Requires Python)

### Prerequisites
- **Python 3.10+** (must be installed on Windows)
- **G304/G305 Lightspeed USB Receiver** plugged in

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/mayankkumar-cmd/G-Zero.git
   cd G-Zero
   ```

2. **Set up a Virtual Environment:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Controller:**
   ```bash
   python main.py
   ```

> [!IMPORTANT]
> **Keep Moving the Mouse:** Logitech wireless gaming mice go into a low-power sleep state to save battery. While launching the app or applying DPI, keep moving the mouse slightly to ensure the Lightspeed receiver can route the command packets to the peripheral hardware.

---

## How It Works: Logitech HID++ 2.0 Protocol

**G-Zero** replicates the core protocol behavior of open-source drivers like `libratbag`:
1. It connects to the Lightspeed receiver (`0xc53f`) on Windows on the raw vendor-defined channel: **Interface 2, Usage Page 0xFF00, Usage 0x02**.
2. It queries the **HID++ 2.0 Root Feature Table (`0x0000`)** to dynamically locate the index of **Adjustable DPI (`0x2201`)** (which maps dynamically to `0x1A` on typical firmware revisions).
3. It sends standard **HID++ 2.0 Long Packets (`0x11`, 20 bytes)** using **Function 2 (`0x21`)** to query the active hardware DPI and **Function 3 (`0x31`)** to write new DPI settings instantly.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
