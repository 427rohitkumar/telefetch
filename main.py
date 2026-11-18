"""
TeleFetch - Telegram Bulk File Downloader GUI
Entry Point
"""

import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.ui.main_window import TeleFetchApp


def main():
    app = TeleFetchApp()
    app.mainloop()


if __name__ == "__main__":
    main()
