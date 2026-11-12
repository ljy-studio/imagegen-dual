"""Resolve data beside the skill, including a frozen portable executable."""
from pathlib import Path
import sys

BUNDLED = bool(getattr(sys, 'frozen', False))
ROOT = Path(sys.executable).resolve().parent if BUNDLED else Path(__file__).resolve().parents[1]
