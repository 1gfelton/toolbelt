import os
import sys

# Desktop app configuration
DESKTOP_CONFIG = {
    'window_title': 'Payette Toolbelt',
    'width': 1200,
    'height': 800,
    'maximized': False,
    'resizable': True,
    'fullscreen': False,
    'close_server_on_exit': True,
    'on_startup': lambda: print("Payette Toolbelt starting..."),
    'on_shutdown': lambda: print("Payette Toolbelt closing...")
}

# Auto-detect if running as executable (for PyInstaller builds)
def is_executable():
    return getattr(sys, 'frozen', False)

# Get the correct base path for resources
def get_base_path():
    if is_executable():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# Corporate deployment settings
CORPORATE_CONFIG = {
    'disable_dev_tools': True,  # Disable browser dev tools in production
    'auto_start_browser': False,  # Let FlaskWebGUI handle the window
    'port_range': (8000, 8100),  # Port range for finding available ports
}