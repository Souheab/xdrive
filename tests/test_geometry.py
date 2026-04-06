"""Unit tests for the Geometry dataclass."""

import pytest

from xdrive.geometry import Geometry


class TestGeometryEquality:
    def test_equal_geometries(self):
        g1 = Geometry(x=10, y=20, width=100, height=200)
        g2 = Geometry(x=10, y=20, width=100, height=200)
        assert g1 == g2

    def test_unequal_x(self):
        g1 = Geometry(x=0, y=0, width=100, height=100)
        g2 = Geometry(x=1, y=0, width=100, height=100)
        assert g1 != g2

    def test_unequal_y(self):
        g1 = Geometry(x=0, y=0, width=100, height=100)
        g2 = Geometry(x=0, y=1, width=100, height=100)
        assert g1 != g2

    def test_unequal_width(self):
        g1 = Geometry(x=0, y=0, width=100, height=100)
        g2 = Geometry(x=0, y=0, width=200, height=100)
        assert g1 != g2

    def test_unequal_height(self):
        g1 = Geometry(x=0, y=0, width=100, height=100)
        g2 = Geometry(x=0, y=0, width=100, height=200)
        assert g1 != g2

    def test_not_equal_to_non_geometry(self):
        g = Geometry(x=0, y=0, width=100, height=100)
        assert g.__eq__("not a geometry") is NotImplemented

    def test_frozen_immutability(self):
        g = Geometry(x=0, y=0, width=100, height=100)
        with pytest.raises((AttributeError, TypeError)):
            g.x = 5  # type: ignore[misc]


class TestGeometryOverlaps:
    def test_overlapping_geometries(self):
        g1 = Geometry(x=0, y=0, width=100, height=100)
        g2 = Geometry(x=50, y=50, width=100, height=100)
        assert g1.overlaps(g2)
        assert g2.overlaps(g1)

    def test_non_overlapping_horizontal(self):
        g1 = Geometry(x=0, y=0, width=100, height=100)
        g2 = Geometry(x=100, y=0, width=100, height=100)
        assert not g1.overlaps(g2)

    def test_non_overlapping_vertical(self):
        g1 = Geometry(x=0, y=0, width=100, height=100)
        g2 = Geometry(x=0, y=100, width=100, height=100)
        assert not g1.overlaps(g2)

    def test_adjacent_does_not_overlap(self):
        g1 = Geometry(x=0, y=0, width=50, height=50)
        g2 = Geometry(x=50, y=0, width=50, height=50)
        assert not g1.overlaps(g2)

    def test_fully_contained_overlaps(self):
        outer = Geometry(x=0, y=0, width=200, height=200)
        inner = Geometry(x=50, y=50, width=100, height=100)
        assert outer.overlaps(inner)
        assert inner.overlaps(outer)

    def test_corner_touch_does_not_overlap(self):
        g1 = Geometry(x=0, y=0, width=100, height=100)
        g2 = Geometry(x=100, y=100, width=100, height=100)
        assert not g1.overlaps(g2)

    def test_partial_x_overlap_no_y_overlap(self):
        g1 = Geometry(x=0, y=0, width=100, height=50)
        g2 = Geometry(x=50, y=60, width=100, height=50)
        assert not g1.overlaps(g2)

    def test_hashable(self):
        g = Geometry(x=1, y=2, width=3, height=4)
        s = {g}
        assert g in s
