"""Geometry helper."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Geometry:
    """Immutable rectangle representing an X11 window's position and size.

    Attributes:
        x: Horizontal offset from the left edge of the root window in pixels.
        y: Vertical offset from the top edge of the root window in pixels.
        width: Width of the rectangle in pixels.
        height: Height of the rectangle in pixels.

    Example:
        >>> geo = Geometry(x=10, y=20, width=800, height=600)
        >>> geo.overlaps(Geometry(x=100, y=100, width=200, height=200))
        True
    """

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
        """Check whether this rectangle overlaps with another.

        Two rectangles overlap when they share at least one pixel.  Touching
        edges (zero-area intersection) do **not** count as overlapping.

        Args:
            other: The rectangle to test against.

        Returns:
            ``True`` if the rectangles overlap, ``False`` otherwise.

        Example:
            >>> a = Geometry(0, 0, 100, 100)
            >>> b = Geometry(50, 50, 100, 100)
            >>> a.overlaps(b)
            True
        """
        if self.x + self.width <= other.x or other.x + other.width <= self.x:
            return False
        if self.y + self.height <= other.y or other.y + other.height <= self.y:
            return False
        return True
