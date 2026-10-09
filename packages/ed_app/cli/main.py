import sys

from ed_watcher import JournalPathNotFoundError

from ed_app.bootstrap import build_engine


def main() -> int:
    """Execute smoke test startup of the telemetry daemon."""
    engine = build_engine()
    try:
        engine.start()
        print("ed-telemetry baseline verified: engine started successfully")
        engine.stop()
    except JournalPathNotFoundError as exc:
        print(f"ed-telemetry baseline verified: engine initialized (standby mode, {exc.platform_name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
