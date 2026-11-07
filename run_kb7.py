"""
Turtle Beach Command Series KB7 - Standalone Executable Launcher.
"""

import sys
import os
import traceback

# Ensure repo directory is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# In PyInstaller --noconsole (runw.exe) mode, sys.stdout / sys.stderr can be None or invalid
log_path = os.path.join(os.path.expanduser("~"), ".kb7_app.log")
try:
    _log_file = open(log_path, "w", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = _log_file
    if sys.stderr is None:
        sys.stderr = _log_file
except Exception:
    pass

from turtlebeach_kb7.app import run_app

if __name__ == "__main__":
    try:
        run_app()
    except Exception as e:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"FATAL: {e}\n{traceback.format_exc()}\n")
        except Exception:
            pass
