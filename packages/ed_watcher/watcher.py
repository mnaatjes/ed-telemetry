"""Inbound journal watcher adapter."""


class JournalWatcher:
    """Minimal journal watcher implementation satisfying WatcherPort."""

    def __init__(self) -> None:
        self._active = False

    def start(self) -> None:
        """Start listening for journal events."""
        self._active = True

    def stop(self) -> None:
        """Stop listening for journal events."""
        self._active = False

    @property
    def is_active(self) -> bool:
        """Return True if watcher is actively listening."""
        return self._active
