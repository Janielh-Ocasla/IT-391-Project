"""Compatibility entry point for the shared CIC application.

Prefer running ``python -m Backend.main`` from the repository root.
"""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR))

from Backend.main import app


if __name__ == "__main__":
    app.run(debug=True, port=5050)
