import ctypes
import sys
import time

import memoryscanMOBloc
import memoryscanPLAYERloc
from memoryscanPLAYERloc import run as playerscan
from memoryscanMOBloc import run as mobscan
from eobot032025 import run as eobot

from tools import select_endless_pid, focus_endless_window

# Global Debug
DEBUG = False

def send_vkeycode(vkey_code):
    ctypes.windll.user32.keybd_event(vkey_code, 0, 0, 0)
    time.sleep(0.1)
    ctypes.windll.user32.keybd_event(vkey_code, 0, 2, 0)


def loc_command():
    SHIFT = 0x10
    THREE = 0x33
    L = 0x4C
    O = 0x4F
    C = 0x43
    ENTER = 0x0D

    DELAY = 0.1

    ctypes.windll.user32.keybd_event(SHIFT, 0, 0, 0)
    ctypes.windll.user32.keybd_event(THREE, 0, 0, 0)
    time.sleep(DELAY)
    ctypes.windll.user32.keybd_event(SHIFT, 0, 2, 0)
    ctypes.windll.user32.keybd_event(THREE, 0, 2, 0)

    time.sleep(DELAY)

    send_vkeycode(L)

    time.sleep(DELAY)

    send_vkeycode(O)

    time.sleep(DELAY)

    send_vkeycode(C)

    time.sleep(DELAY)

    send_vkeycode(ENTER)

    time.sleep(DELAY)

def main():
    memoryscanMOBloc.DEBUG = DEBUG
    memoryscanPLAYERloc.debug_mode = DEBUG
    try:
        print(f"PLC PLC PLC")
        print(f"EO BOT MADE BY POLAKS")
        print(f"PLC PLC PLC")
        print()
        print(f"Scanning for EO Client \n")

        pid = select_endless_pid()
        if pid is None:
            print("Check if your game is open.")
            input("Press any key to exit...")

        print("\nUsing #loc command.")
        
        focus_endless_window(pid)

        time.sleep(1.5)

        loc_command()

        print("Now scanning for player loc memory address. Make sure your coordinates XY higher than 4.\n")
        playerscan(pid)

        print("\nNow scanning for monster memory address.\n")
        mobscan(pid)

        time.sleep(3)

        print("\nNow running bot.\n")
        eobot(pid)

        print(f"Bot finished running.")
        print("\n")
        input("Press any key to exit...")

    except(KeyboardInterrupt, SystemExit):
        print(f"Program interrupted. Reason: {sys.exc_info()[0]}")
        print("\n")
        input("Press any key to exit...")


if __name__ == "__main__":
    main()