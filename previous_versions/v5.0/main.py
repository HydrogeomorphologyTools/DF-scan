#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified DF-scan entry point: detects CLI vs GUI"""

import sys
import os
import multiprocessing

def main():
    # Essential for PyInstaller + Multiprocessing on Windows
    multiprocessing.freeze_support()

    # Set working directory to bundle directory if frozen
    if getattr(sys, 'frozen', False):
        os.chdir(sys._MEIPASS)

    # Detect if we are a multiprocessing child process
    is_child = any('--multiprocessing-fork' in arg for arg in sys.argv)
    
    if is_child:
        return

    # Launch dfscan_gui which handles both normal GUI and headless CLI config modes natively
    from src import dfscan_gui as gui
    gui.main()

if __name__ == "__main__":
    main()
