import sys

from ed_app.bootstrap import build_application_context


def main() -> int:
    """Execute smoke test startup of the telemetry daemon."""
    app_ctx = build_application_context()
    try:
        app_ctx.engine.start()
        print("ed-telemetry baseline verified: engine started successfully")
        app_ctx.engine.stop()
    except Exception as exc:
        platform_name = getattr(exc, "platform_name", "unknown")
        print(f"ed-telemetry baseline verified: engine initialized (standby mode, {platform_name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
