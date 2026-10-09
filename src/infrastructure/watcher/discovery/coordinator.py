"""Path discovery coordinator managing overrides, platform gating, and resolution."""

from __future__ import annotations

import os
from pathlib import Path

from infrastructure.watcher.discovery.exceptions import (
    InvalidPathOverrideError,
    JournalPathNotFoundError,
    UnsupportedPlatformError,
)
from infrastructure.watcher.discovery.models import DiscoveryResult, SupportedPlatform
from infrastructure.watcher.discovery.protocols import PathDiscoveryStrategy
from infrastructure.watcher.discovery.strategies.linux import LinuxProtonPathStrategy
from infrastructure.watcher.discovery.strategies.windows import WindowsPathStrategy

ENV_JOURNAL_DIR = "ED_JOURNAL_DIR"


class PathDiscoverer:
    """
    Coordinates Elite Dangerous journal directory discovery.

    Resolves candidate paths following strict precedence:
    1. Explicit parameter override.
    2. Environment variable override ($ED_JOURNAL_DIR).
    3. Host platform automated strategy (Windows or Linux Proton).
    """

    def __init__(
        self,
        strategy: PathDiscoveryStrategy | None = None,
        platform_type: SupportedPlatform | None = None,
    ) -> None:
        self._platform_type = platform_type or SupportedPlatform.from_current_platform()
        if strategy is not None:
            self._strategy: PathDiscoveryStrategy | None = strategy
        elif self._platform_type == SupportedPlatform.WINDOWS:
            self._strategy = WindowsPathStrategy()
        elif self._platform_type == SupportedPlatform.LINUX:
            self._strategy = LinuxProtonPathStrategy()
        else:
            self._strategy = None

    def discover_journal_directory(
        self,
        override_path: Path | str | None = None,
    ) -> DiscoveryResult:
        """
        Discover and return the validated Elite Dangerous journal directory.

        Args:
            override_path: Optional explicit parameter override.

        Returns:
            DiscoveryResult containing resolved canonical Path and discovery source.

        Raises:
            InvalidPathOverrideError: When an explicit override does not exist or is not a directory.
            UnsupportedPlatformError: When running on an unsupported OS without an automated strategy.
            JournalPathNotFoundError: When all candidate locations fail to exist.
        """
        # 1. Parameter Override
        if override_path is not None:
            resolved = Path(override_path).expanduser().resolve()
            self._validate_override(resolved, source="parameter")
            return DiscoveryResult(resolved_path=resolved, discovery_source="parameter_override")

        # 2. Environment Variable Override
        env_override = os.environ.get(ENV_JOURNAL_DIR)
        if env_override:
            resolved = Path(env_override).expanduser().resolve()
            self._validate_override(resolved, source="environment")
            return DiscoveryResult(resolved_path=resolved, discovery_source="env_override")

        # 3. Platform Gate Check
        if self._platform_type == SupportedPlatform.UNSUPPORTED or self._strategy is None:
            import sys

            raise UnsupportedPlatformError(platform_name=sys.platform)

        # 4. Automated Platform Strategy Execution
        candidates = self._strategy.find_candidates()
        for candidate in candidates:
            resolved_candidate = candidate.expanduser().resolve()
            if resolved_candidate.is_dir():
                return DiscoveryResult(
                    resolved_path=resolved_candidate,
                    discovery_source=f"platform_{self._platform_type.value}",
                )

        # 5. All Candidates Exhausted
        raise JournalPathNotFoundError(
            inspected_paths=candidates,
            platform_name=self._strategy.platform_name,
        )

    def _validate_override(self, path: Path, source: str) -> None:
        """Validate that an explicit override path exists and is a readable directory."""
        if not path.exists():
            raise InvalidPathOverrideError(target_path=path, source=source, reason="does_not_exist")
        if not path.is_dir():
            raise InvalidPathOverrideError(target_path=path, source=source, reason="not_a_directory")
