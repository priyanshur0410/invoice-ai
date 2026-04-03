import sys
import os

# Sirf tab path add karo jab backend/ already path mein na ho
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)