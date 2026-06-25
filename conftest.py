import sys
import os

# Make the src/ package importable from all test files and notebooks
# without requiring an editable install.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
