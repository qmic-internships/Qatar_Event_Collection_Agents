#!/usr/bin/env python3
"""
Main entry point for the Event Collection Agent.

This script serves as the entry point to run the application while keeping
all source code organized in the src/ directory.
"""

import sys
import os

# Add src directory to Python path so we can import from it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.app import main

if __name__ == "__main__":
    main()
