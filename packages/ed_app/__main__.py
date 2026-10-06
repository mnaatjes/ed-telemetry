"""Module executable entrypoint for ed_app."""

import sys

from ed_app.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
