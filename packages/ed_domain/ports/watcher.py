"""Abstract ports for inbound telemetry watchers."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class WatcherPort(Protocol):
    """Contract for inbound file and telemetry watchers."""

    def start(self) -> None:
        """Start listening or polling for telemetry events."""
        ...

    def stop(self) -> None:
        """Stop listening or polling."""
        ...
