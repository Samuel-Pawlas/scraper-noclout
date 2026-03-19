#!/usr/bin/env python3
"""
Noclout Scraper Runner
Handles environment setup and scraper execution
"""

import os
import sys
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PYTHON_PATH = r"C:\Users\samip\AppData\Local\Programs\Python\Python312\python.exe"
REQUIREMENTS_FILE = SCRIPT_DIR / "requirements.txt"
SCRAPER_FILE = SCRIPT_DIR / "scraper.py"


def check_python():
    """Check if Python is installed"""
    if not Path(PYTHON_PATH).exists():
        print(f"Error: Python not found at {PYTHON_PATH}")
        print("Please install Python 3.12 from https://python.org")
        return False
    return True


def install_requirements():
    """Install required packages"""
    print("Checking dependencies...")
    try:
        result = subprocess.run(
            [PYTHON_PATH, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
            capture_output=True,
            text=True,
            cwd=str(SCRIPT_DIR)
        )
        if result.returncode != 0:
            print(f"Failed to install requirements: {result.stderr}")
            return False
        print("Dependencies installed successfully")
        return True
    except Exception as e:
        print(f"Error installing requirements: {e}")
        return False


def run_scraper():
    """Run the main scraper"""
    print("=" * 60)
    print("Starting Noclout Scraper")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            [PYTHON_PATH, str(SCRAPER_FILE)],
            cwd=str(SCRIPT_DIR)
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error running scraper: {e}")
        return False


def main():
    """Main entry point"""
    if not check_python():
        sys.exit(1)
    
    if not install_requirements():
        sys.exit(1)
    
    success = run_scraper()
    
    if success:
        print("\nScraper completed successfully!")
        sys.exit(0)
    else:
        print("\nScraper failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
