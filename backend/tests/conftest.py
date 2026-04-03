import sys
import os

# backend/ folder ko Python path mein add karo
# Isse 'from services.xxx import ...' kaam karega chahe kahin se bhi pytest run ho
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
