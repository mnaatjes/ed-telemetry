"""Module executable entrypoint for services."""

import sys

from interfaces.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
