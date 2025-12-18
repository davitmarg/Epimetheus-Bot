import os
import sys
from dotenv import load_dotenv

# Ensure project root is on sys.path for test imports
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load environment variables from .env file for all tests
load_dotenv()
