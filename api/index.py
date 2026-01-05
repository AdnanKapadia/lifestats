from flask import Flask
import os
import sys

# Add the project root directory to the Python path
# This allows us to import from the backend directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.app import app

# Vercel expects the application instance to be available as 'app'
