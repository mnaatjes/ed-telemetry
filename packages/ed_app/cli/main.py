"""Command-line interface entrypoints."""

import sys

from ed_app.bootstrap import build_engine


def main() -> int:
    """Execute smoke test startup of the telemetry daemon."""
    engine = build_engine()
    engine.start()
    print("ed-telemetry baseline verified: engine started successfully")
    engine.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
