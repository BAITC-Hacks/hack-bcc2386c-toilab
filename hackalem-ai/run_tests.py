"""Run from any directory: python run_tests.py"""
import subprocess
import sys
from pathlib import Path
raise SystemExit(subprocess.call([sys.executable,"-m","pytest","-q","tests"],cwd=Path(__file__).parent))
