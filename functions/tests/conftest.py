import sys
from pathlib import Path

# make `swimbackend` importable (functions/ is the package root)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
