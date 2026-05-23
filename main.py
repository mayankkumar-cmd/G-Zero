import sys
import os
import tkinter as tk
import ctypes
from gui import GZeroGUI

def set_immersive_dark_title_bar(window):
    """Uses the Windows DWM API via ctypes to force standard title bar into Dark Mode."""
    # Ensure window has been fully drawn/updated so the parent HWND is finalized
    window.update()
    
    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
    value = ctypes.c_int(1)
    
    try:
        # Get standard window handle (HWND)
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        
        # Try modern Windows 11 / Windows 10 attribute 20
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 
            DWMWA_USE_IMMERSIVE_DARK_MODE, 
            ctypes.byref(value), 
            ctypes.sizeof(value)
        )
        
        # If it failed, fallback to older Windows 10 attribute 19
        if result != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 
                DWMWA_USE_IMMERSIVE_DARK_MODE_OLD, 
                ctypes.byref(value), 
                ctypes.sizeof(value)
            )
            
        # Force redraw of the window frame to apply DWM dark styling immediately
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0, 
            0x0027  # SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER
        )
            
    except Exception as e:
        # Fails silently on non-Windows platforms (macOS/Linux) or old Windows
        pass

def main():
    # Renders with proper high-DPI scaling on Windows systems
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
        
    # Register Taskbar App ID on Windows to display the custom window icon in the Taskbar
    try:
        myappid = 'com.gzero.dpicustomizer.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except:
        pass

    root = tk.Tk()
    
    # Resolve dynamic icon path (supports both raw running and PyInstaller bundle)
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    icon_path = os.path.join(base_path, "logo.ico")
    
    # Set window title bar icon
    try:
        root.iconbitmap(icon_path)
    except:
        pass
    
    # Initialize the GUI layout (geometry, resizable properties, widgets)
    app = GZeroGUI(root)
    
    # Force dark title bar styling on Windows AFTER GUI layout is fully built
    set_immersive_dark_title_bar(root)
    
    root.mainloop()

if __name__ == "__main__":
    main()
