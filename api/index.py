from flask import Flask
import os
import sys

# Add the project root and backend directory to the Python path
# This allows us to import modules like supabase_client directly from backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from backend.app import app

# Vercel expects the application instance to be available as 'app'
