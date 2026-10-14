"""Forwarding stub for manage_alert_retention.py."""
import sys
from pathlib import Path

# Add scripts directory to path if needed
scripts_dir = Path(__file__).resolve().parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from manage_alert_retention import main

if __name__ == "__main__":
    main()
