import sys
import os

for path in ["/app", os.path.dirname(os.path.abspath(__file__))]:
    if path not in sys.path:
        sys.path.insert(0, path)

from app.main import app

__all__ = ["app"]
