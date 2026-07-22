import sys
import os

# Ensure the engine directory and root directory are in Python sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
engine_dir = os.path.join(parent_dir, "engine")

if engine_dir not in sys.path:
    sys.path.insert(0, engine_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from main import app
