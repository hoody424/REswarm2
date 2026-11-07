"""
Turtle Beach Command Series KB7 - Standalone Executable Launcher.
"""

import sys
import os

# Ensure repo directory is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from turtlebeach_kb7.app import run_app

if __name__ == "__main__":
    run_app()
