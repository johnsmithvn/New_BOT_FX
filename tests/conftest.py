"""
tests/conftest.py

Shared fixtures for bot unit tests.
Adds project root to sys.path so 'core.*' imports resolve correctly.
"""

import sys
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
