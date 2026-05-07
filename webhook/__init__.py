import sys
import os

# Add the webhook folder to Python's path
# This means both local and Render can find database and models
sys.path.insert(0, os.path.dirname(__file__))