import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/"catalog-service"),str(root/"assistant-service")]
