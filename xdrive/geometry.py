"""Geometry helper."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Geometry:
    x: int
    y: int
    width: int
    height: int

    def __eq__(self, other):
        if isinstance(other, Geometry):
            return (
                self.x == other.x
                and self.y == other.y
                and self.width == other.width
                and self.height == other.height
            )
        return NotImplemented

    def overlaps(self, other: "Geometry") -> bool:
        """Return True if this geometry overlaps with another."""
        if self.x + self.width <= other.x or other.x + other.width <= self.x:
            return False
        if self.y + self.height <= other.y or other.y + other.height <= self.y:
            return False
        return True
