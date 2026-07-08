"""Ensures the repository root is importable as `core` without requiring
`pip install -e .` first. Kept deliberately trivial — this is test
infrastructure, not application code.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
