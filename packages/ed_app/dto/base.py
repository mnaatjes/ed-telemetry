"""Base Data Transfer Object (DTO) abstractions and protocols."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DataTransferObject(Protocol):
    """Protocol satisfied by frozen DTO dataclasses."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize DTO fields to a dictionary of primitive types."""
        ...
