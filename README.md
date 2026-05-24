# G-Zero: Universal Logitech Gaming Mouse DPI & Battery Controller

[![Platform: Windows](https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows&logoColor=white)](https://microsoft.com)
[![Language: Python](https://img.shields.io/badge/Language-Python-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Framework: Tkinter](https://img.shields.io/badge/Framework-Tkinter-4B8BBE?style=flat-square&logo=desktop&logoColor=white)](https://docs.python.org/3/library/tkinter.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](LICENSE)

**G-Zero** is a modern dark-themed, ultra-lightweight Windows utility designed to control the hardware settings, active DPI, and battery tracking of **all Logitech gaming mice** that support the HID++ 2.0 protocol with **0% background CPU and RAM overhead**.

> [!NOTE]
> **Universal Compatibility:** G-Zero is model-agnostic. It dynamically queries your mouse's internal feature table over USB to fetch its specifications, supporting everything from wired gaming mice to wireless Lightspeed transceivers (such as the G304, G305, G Pro Wireless, GPX Superlight, G502, G703, and more).

Unlike the official **Logitech G HUB** software (which occupies over 400 MB of space, runs persistent background telemetry, and consumes system resources), **G-Zero** connects directly to the mouse hardware over USB, applies your custom settings instantly, and can be closed immediately. The mouse remembers the configurations in its physical onboard memory.

---

## Downloads

You do not need to install Python or set up dependencies. Go to the [GitHub Releases](https://github.com/mayankkumar-cmd/G-Zero/releases) tab and download the pre-compiled **`G-Zero.exe`** standalone executable. Double-click to run it instantly.

---

## Features

- 🔋 **Zero Background Overhead:** Configure your settings in seconds and exit. The mouse retains the active configurations at the hardware level.
- 🎛️ **Adaptive DPI Slider:** Dynamically scales its bounds based on your sensor's hardware limits. Automatically supports up to `12000` DPI for standard sensors and up to `25600` DPI for high-end HERO 16K/25K sensors.
- 🔋 **Dynamic Battery Status (Feature `0x1000`):** Real-time percentage readouts and power states (Discharging, Recharging, Complete) mapped via a vector battery canvas that changes color reactively.
- 🏷️ **Onboard Name & Telemetry (Features `0x0005` & `0x0003`):** Dynamically resolves your friendly product name and firmware prefixes/builds from the mouse ROM.
- 🔄 **Non-Blocking Background Polling:** USB communication operates on a separate background thread with hardware locks. Throttles battery queries to once every 30 seconds to conserve wireless battery.

---

## Project Structure

```
G-Zero/
├── main.py            # High-DPI entry point (initializes Tkinter)
├── gui.py             # Flat dark layout, button animations, vector canvas, and updates
├── hidpp.py           # HID++ 2.0 dynamic feature lookups, packet framing, and raw USB I/O
├── requirements.txt   # Dependencies list
├── .gitignore         # Excluded files list for Git
└── README.md          # Documentation
```

---

## Running from Source (Requires Python)

### Prerequisites
- **Python 3.10+** (must be installed on Windows)
- **Logitech Gaming Mouse** plugged in (wired or wireless receiver)

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
   **Wireless Sleep Cycle:** Wireless mice go to sleep after idle periods. While launching the app or applying DPI, keep moving the mouse slightly to ensure the Lightspeed receiver can route the command packets to the peripheral hardware.

---

## How It Works: Logitech HID++ 2.0 Protocol

**G-Zero** replicates the core protocol behavior of open-source drivers like `libratbag`:
1. It connects to the Logitech transceiver on Windows on the raw vendor-defined channel: **Usage Page 0xFF00, Usage 0x02**.
2. It queries the **HID++ 2.0 Root Feature Table (`0x0000`)** to dynamically locate the indices of requested features (e.g., `0x2201` for Adjustable DPI, `0x1000` for battery status, `0x0003` for firmware version).
3. It sends standard **HID++ 2.0 Long Packets (`0x11`, 20 bytes)** to read and write parameters directly to the hardware.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
