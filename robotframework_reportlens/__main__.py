"""Allow running as python -m robotframework_reportlens."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
