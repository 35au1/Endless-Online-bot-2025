#!/usr/bin/env python3

import subprocess
import sys
import os

def check_pip():
    """Check if pip is installed and install it if not."""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("pip is already installed.")
        return True
    except subprocess.CalledProcessError:
        print("pip is not installed. Installing pip...")
        try:
            # This method uses ensurepip module which should be available in Python 3.4+
            subprocess.check_call([sys.executable, "-m", "ensurepip", "--upgrade"], 
                                stdout=subprocess.PIPE)
            print("pip has been installed successfully.")
            return True
        except subprocess.CalledProcessError:
            print("Failed to install pip using ensurepip.")
            print("Please install pip manually following the instructions at:")
            print("https://pip.pypa.io/en/stable/installation/")
            return False

def install_dependencies():
    """Install required dependencies for the script."""
    dependencies = [
        "pymem",
        "psutil"
    ]
    
    print("\nChecking and installing required dependencies...")
    for package in dependencies:
        try:
            # Check if package is already installed
            subprocess.check_call([sys.executable, "-m", "pip", "show", package], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"{package} is already installed.")
        except subprocess.CalledProcessError:
            print(f"Installing {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"{package} has been installed successfully.")
            except subprocess.CalledProcessError:
                print(f"Failed to install {package}. Please install it manually.")
                return False
    
    return True

def main():
    print("=== Dependency Installation for Memory Scanner Scripts ===")
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 6):
        print("Warning: These scripts were designed for Python 3.6 or later.")
        print("Some features might not work correctly with your current Python version.")
        
        response = input("Do you want to continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Installation aborted.")
            return
    
    # Check and install pip if needed
    if not check_pip():
        return
    
    # Install dependencies
    if install_dependencies():
        print("\nAll dependencies have been successfully installed!")
        print("\nYou can now run the memory scanner scripts:")
        print("1. memoryscan-PLAYERloc_XYabove4.py - Find player location")
        print("2. memoryscan-MOBloc.py - Find enemy locations")
        print("3. eobot032025.py - Bot that uses the above addresses")
    else:
        print("\nFailed to install all dependencies. Please check the error messages above.")

if __name__ == "__main__":
    main()
