"""Generic Base Driven Adapter Registry for Application Services.

Governed by ADR 0014 and SDD-012.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Generic, TypeVar

T = TypeVar("T")


class BaseAdapterRegistry(Generic[T]):
    """Generic base registry for driven adapters in the Application Service Layer."""

    def __init__(self) -> None:
        self._adapters: dict[str, T] = {}

    def _assert_driven_adapter(self, adapter: T) -> None:
        """Enforce that the registered adapter resides strictly in src/infrastructure/."""
        module_path = type(adapter).__module__
        if not module_path.startswith("infrastructure."):
            raise TypeError(
                f"Adapter Registry only accepts Driven Adapters from 'src/infrastructure/', "
                f"got: {type(adapter).__qualname__} from '{module_path}'"
            )

    def register(self, key: str, adapter: T) -> None:
        """Register a driven adapter under a unique alphanumeric key."""
        if not key or not isinstance(key, str):
            raise ValueError("Registry key must be a non-empty string.")
        if key in self._adapters:
            raise KeyError(f"Adapter with key '{key}' is already registered.")
        self._assert_driven_adapter(adapter)
        self._adapters[key] = adapter

    def get(self, key: str) -> T:
        """Retrieve a registered driven adapter by key."""
        if key not in self._adapters:
            raise KeyError(f"No adapter registered under key '{key}'.")
        return self._adapters[key]

    def get_all(self) -> Sequence[T]:
        """Return all registered driven adapters in registration order."""
        return tuple(self._adapters.values())

    def list_keys(self) -> Sequence[str]:
        """Return all registered keys in registration order."""
        return tuple(self._adapters.keys())

    def __len__(self) -> int:
        return len(self._adapters)

    def __contains__(self, key: object) -> bool:
        return key in self._adapters

    def __iter__(self) -> Iterator[str]:
        return iter(self._adapters)
