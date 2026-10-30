#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified MSF entry point: detects CLI vs GUI"""

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
    # These children should not try to launch CLI or GUI logic themselves
    is_child = any('--multiprocessing-fork' in arg for arg in sys.argv)
    
    if is_child:
        # The multiprocessing module handles the child logic via freeze_support()
        return

    # If any REAL arguments are provided (other than the script name), use CLI mode
    # We filter out the executable name and any internal multi-processing flags
    real_args = [arg for arg in sys.argv[1:] if not arg.startswith('--multiprocessing-fork')]
    
    if len(real_args) > 0:
        from src import msf_cli as cli
        cli.main()
    else:
        # Otherwise, launch the GUI
        from src import msf_gui as gui
        gui.main()

if __name__ == "__main__":
    main()
