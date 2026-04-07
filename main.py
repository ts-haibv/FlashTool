#!/usr/bin/env python3
"""FlashTool — Cross-platform G6 ROM Flashing Application.

Usage:
    python main.py
"""

import sys
import customtkinter as ctk
from flash_tool.ui.main_window import MainWindow


def main():
    # Set appearance
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    # Launch app
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
