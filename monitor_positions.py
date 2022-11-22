from math import sin, cos, asin, atan, atan2, hypot, pi, inf, nan, degrees
from dataclasses import dataclass, field
from typing import Optional

from bokeh.plotting import figure, Figure, Row, show
from bokeh.models import ColumnDataSource, ColorBar, LinearColorMapper, GlyphRenderer
from bokeh.layouts import row
from bokeh.palettes import Viridis256
from bokeh.core.validation import silence
from bokeh.core.validation.warnings import MISSING_RENDERERS

CM_CONVERSION: dict[str, float] = {"mm": 0.1, "cm": 1, "m": 100, "in": 2.54, "ft": 30.48}


@dataclass
class PointAngleData:
    monitor_num: list[int] = field(default_factory=list)
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    viewing_angle: list[float] = field(default_factory=list)


@dataclass
class LineAngleData:
    monitor_num: list[int] = field(default_factory=list)
    x: list[list[float]] = field(default_factory=list)
    y: list[list[float]] = field(default_factory=list)
    viewing_angle: list[float] = field(default_factory=list)

    def plot(self,
             colormap: Optional[LinearColorMapper],
             show_colorbar: bool = False,
             width: int = 400,
             height: int = 400,
             toolbar_location: Optional[str] = "below") -> tuple[Figure, GlyphRenderer]:
        """Plot the viewing angle data."""

        source = ColumnDataSource(vars(self))

        if colormap is None:
            min_angle = min(self.viewing_angle)
            max_angle = max(self.viewing_angle)
            colormap = LinearColorMapper(palette=Viridis256, low=min_angle, high=max_angle)

        fig = figure(width=width, height=height, match_aspect=True, aspect_scale=1, toolbar_location=toolbar_location)

        line = fig.multi_line("x",
                              "y",
                              color={
                                  "field": "viewing_angle",
                                  "transform": colormap
                              },
                              source=source,
                              line_width=3)
        fig.circle(0, 0, size=10)

        if show_colorbar:
            colorbar = ColorBar(color_mapper=colormap, label_standoff=12, border_line_color=None, location=(0, 0))
            fig.add_layout(colorbar, "right")

        return fig, line


@dataclass
class Point:
    """A class to represent a point in 2D space"""
    x: float
    y: float

    @classmethod
    def from_polar_coord(cls, radius: float, phase: float):
        x = radius * cos(phase)
        y = radius * sin(phase)
        return cls(x, y)

    def __add__(self, other: "Point") -> "Point":
        """Vector addition"""
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        """Vector subtraction"""
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Point":
        """Multiplication by scalar"""
        return Point(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: float) -> "Point":
        """Division by scalar"""
        return Point(self.x / scalar, self.y / scalar)

    def __matmul__(self, other: "Point") -> float:
        """Inner (scalar) product"""
        return (self.x * other.x) + (self.y * other.y)

    def __abs__(self) -> float:
        """Euclidean norm"""
        return hypot(self.x, self.y)

    def phase(self) -> float:
        """Returns the phase of the point in radians"""
        return atan2(self.y, self.x)

    def to_polar_coord(self) -> tuple[float, float]:
        """Returns the polar coordinates (radius and phase) of the point"""
        radius = abs(self)
        phase = self.phase()
        return radius, phase

    def rotate(self, angle: float) -> "Point":
        """Rotates the point by the given angle in radians"""
        radius, phase = self.to_polar_coord()
        return Point.from_polar_coord(radius, phase + angle)


class Monitor:
    """Represents an unplaced monitor"""
    diagonal_length: float
    radius: float
    aspect_ratio: float

    def __init__(self,
                 diagonal_length: float,
                 aspect_ratio: float,
                 radius: float = inf,
                 diagonal_unit: str = "in",
                 radius_unit: str = "mm"):

        if diagonal_unit not in CM_CONVERSION or radius_unit not in CM_CONVERSION:
            raise ValueError(f"units must be one of: {', '.join(CM_CONVERSION.keys())}")

        self.diagonal_length = diagonal_length * CM_CONVERSION[diagonal_unit]
        self.radius = radius * CM_CONVERSION[radius_unit]
        self.aspect_ratio = aspect_ratio

        self.left_end = None
        self.right_end = None
        self.circle_center = None

    def arc_width(self) -> float:
        """Calculates the arc width of the monitor and returns it in centimeters"""
        diagonal_angle = atan(1 / self.aspect_ratio)
        arc_width = cos(diagonal_angle) * self.diagonal_length
        return arc_width

    def chord_width(self) -> float:
        """Calculates the physical (chord) width of the monitor and returns it in centimeters"""
        arc_width = self.arc_width()
        if self.radius == inf:
            chord_width = arc_width
        else:
            central_angle = arc_width / self.radius
            chord_width = 2 * self.radius * sin(central_angle / 2)
        return chord_width

    def height(self) -> float:
        """Calculates the height of a monitor in centimeters"""
        diagonal_angle = atan(1 / self.aspect_ratio)
        height = sin(diagonal_angle) * self.diagonal_length
        return height

    def display_area(self) -> float:
        """Calculate the display area of a monitor in square centimeters"""
        return self.height() * self.arc_width()

    def depth(self) -> float:
        """Calculates the depth of a (possibly curved) screen"""
        if self.radius == inf:
            depth = 0
        else:
            central_angle = self.arc_width() / self.radius
            depth = self.radius * (1 - cos(central_angle / 2))
        return depth

    def arc_angle(self, position) -> float:
        """Calculates the angle between the chord of the monitor and the tangent
        of the arc at a given position.
        """
        if position < 0 or position > 1:
            raise ValueError("position must be between 0 (left) and 1 (right)")
        if self.radius == inf:
            arc_angle = 0
        else:
            central_angle = self.arc_width() / self.radius
            arc_angle = (0.5 - position) * central_angle
        return arc_angle


class PlacedMonitor(Monitor):
    """Represents a monitor placed in 2D space"""
    left_end: Point
    right_end: Point
    circle_center: Point

    def __init__(self, monitor: Monitor, left_end: Point, right_end: Point):
        self.diagonal_length = monitor.diagonal_length
        self.radius = monitor.radius
        self.aspect_ratio = monitor.aspect_ratio
        self.left_end = left_end
        self.right_end = right_end
        self.circle_center = self.get_circle_center()

    def midpoint(self) -> Point:
        """Returns the midpoint of chord of the monitor"""
        return (self.left_end + self.right_end) / 2

    def get_circle_center(self) -> Point:
        """Calculates the point from which each point of the monitor is perpendicular to the viewer"""
        if self.radius == inf:
            circle_center = Point(nan, nan)
        else:
            chord_direction = (self.left_end - self.right_end).phase()
            midpoint_to_center_direction = chord_direction + pi / 2
            midpoint_to_center_length = self.radius - self.depth()
            circle_center = self.midpoint() + Point.from_polar_coord(midpoint_to_center_length,
                                                                     midpoint_to_center_direction)
        return circle_center

    def get_coordinate(self, position: float) -> Point:
        """Get the coordinates of a point of the monitor"""
        if position < 0 or position > 1:
            raise ValueError("position must be between 0 (left) and 1 (right)")
        if self.radius == inf:
            return (self.left_end * (1 - position)) + (self.right_end * position)
        else:
            left_end_from_center = self.left_end - self.circle_center
            right_end_from_center = self.right_end - self.circle_center
            position_from_center_direction = (left_end_from_center.phase() * (1 - position) +
                                              right_end_from_center.phase() * position)
            position_from_center = Point.from_polar_coord(self.radius, position_from_center_direction)
            return self.circle_center + position_from_center

    def viewing_angle(self, position: float, angle_unit="degrees") -> tuple[Point, float]:
        """Get the coordinates and viewing angle of a point of the monitor"""
        if angle_unit not in ["degrees", "radians"]:
            raise ValueError("angle unit must be either degrees or radians")
        point = self.get_coordinate(position)
        if self.radius == inf:
            chord_direction = (self.left_end - self.right_end).phase()
            screen_normal = (chord_direction - pi / 2) % (2 * pi)
        else:
            screen_normal = (point - self.circle_center).phase()
        view_phase = point.phase()
        view_angle_radians = view_phase - screen_normal
        if angle_unit == "radians":
            return point, view_angle_radians
        else:
            return point, degrees(view_angle_radians)


class Setup:
    """Represents a setup of monitors"""
    viewing_distance: float
    monitors: list[PlacedMonitor]

    def __init__(self,
                 monitors: list[Monitor],
                 viewing_distance: float,
                 mode: str = "perpendicular",
                 distance_unit: str = "cm"):
        if distance_unit not in CM_CONVERSION:
            raise ValueError(f"units must be one of: {', '.join(CM_CONVERSION.keys())}")
        if mode not in ["perpendicular", "smooth"]:
            raise ValueError("mode must be either perpendicular or smooth")

        self.viewing_distance = viewing_distance * CM_CONVERSION[distance_unit]
        self.monitors = []

        num_monitors = len(monitors)
        if num_monitors % 2 == 0:
            if mode == "perpendicular":
                self._add_monitor(monitors[num_monitors // 2], side="middle", mode=mode, rotate=True)
                left_monitors = monitors[:num_monitors // 2]
                right_monitors = monitors[num_monitors // 2 + 1:]
            else:
                self._add_monitor(Monitor(0, 1), side="middle", mode=mode)
                left_monitors = monitors[:num_monitors // 2]
                right_monitors = monitors[num_monitors // 2:]
        else:
            self._add_monitor(monitors[num_monitors // 2], side="middle", mode=mode)
            left_monitors = monitors[:num_monitors // 2]
            right_monitors = monitors[num_monitors // 2 + 1:]

        for monitor in reversed(left_monitors):
            self._add_monitor(monitor, "left", mode=mode)
        for monitor in right_monitors:
            self._add_monitor(monitor, "right", mode=mode)

        if num_monitors % 2 == 0 and mode == "smooth":
            del self.monitors[num_monitors // 2]

    def _add_monitor(self, monitor: Monitor, side: str, mode: str, rotate: bool = False) -> None:
        """Adds a monitor to the setup. Should only be called by the constructor."""
        width = monitor.chord_width()

        if side == "middle":
            chord_distance = self.viewing_distance - monitor.depth()
            left_end = Point(-width / 2, chord_distance)
            right_end = Point(width / 2, chord_distance)
            if rotate:
                half_angle = atan((monitor.chord_width() / 2) / self.viewing_distance)
                left_end = left_end.rotate(-half_angle)
                right_end = right_end.rotate(-half_angle)
            self.monitors = [PlacedMonitor(monitor, left_end, right_end)]

        elif side == "left":
            adjacent_monitor = self.monitors[0]
            right_end = adjacent_monitor.left_end
            if mode == "perpendicular":
                end_dist, right_end_phase = right_end.to_polar_coord()
                half_angle = asin((monitor.chord_width() / 2) / end_dist)
                left_end = Point.from_polar_coord(end_dist, right_end_phase + 2 * half_angle)
            elif mode == "smooth":
                adjacent_monitor_phase = adjacent_monitor.midpoint().phase()
                curvature_diff = adjacent_monitor.arc_angle(0) - monitor.arc_angle(1)
                monitor_phase = adjacent_monitor_phase + curvature_diff
                left_end = right_end + Point.from_polar_coord(width, monitor_phase + pi / 2)
            else:
                raise ValueError("mode must be either perpendicular or smooth")
            self.monitors.insert(0, PlacedMonitor(monitor, left_end, right_end))

        elif side == "right":
            adjacent_monitor = self.monitors[-1]
            left_end = adjacent_monitor.right_end
            if mode == "perpendicular":
                end_dist, left_end_phase = left_end.to_polar_coord()
                half_angle = asin((monitor.chord_width() / 2) / end_dist)
                right_end = Point.from_polar_coord(end_dist, left_end_phase - 2 * half_angle)
            elif mode == "smooth":
                adjacent_monitor_phase = adjacent_monitor.midpoint().phase()
                curvature_diff = adjacent_monitor.arc_angle(1) - monitor.arc_angle(0)
                monitor_phase = adjacent_monitor_phase + curvature_diff
                right_end = left_end + Point.from_polar_coord(width, monitor_phase - pi / 2)
            else:
                raise ValueError("mode must be either perpendicular or smooth")
            self.monitors.append(PlacedMonitor(monitor, left_end, right_end))

    def screen_width(self, units: str = "cm") -> float:
        """Get the total width of the screen area"""
        width = sum(monitor.arc_width() for monitor in self.monitors)
        return width / CM_CONVERSION[units]

    def max_height(self, units: str = "cm") -> float:
        """Get the maximum height of the setup"""
        height = max(monitor.height() for monitor in self.monitors)
        return height / CM_CONVERSION[units]

    def display_area(self, units: str = "cm") -> float:
        """Get the total area of the screen area"""
        area = sum(monitor.display_area() for monitor in self.monitors)
        return area / CM_CONVERSION[units]**2

    def get_viewing_angles(self, point_per_monitor: int = 100, abs_angle: bool = True) -> PointAngleData:
        """Get the viewing angles of all monitors at regular intervals"""
        data = PointAngleData()
        for monitor_num, monitor in enumerate(self.monitors):
            for i in range(point_per_monitor):
                position = i / (point_per_monitor - 1)
                position, angle = monitor.viewing_angle(position)
                if abs_angle:
                    angle = abs(angle)
                data.monitor_num.append(monitor_num)
                data.x.append(position.x)
                data.y.append(position.y)
                data.viewing_angle.append(angle)
        return data

    def get_line_segments(self, segment_per_monitor: int = 99, abs_angle: bool = True) -> LineAngleData:
        """Get the viewing angles of all monitors at regular intervals in a format suitable for plotting"""
        data = self.get_viewing_angles(segment_per_monitor + 1, abs_angle)
        new_data = LineAngleData()
        prev_monitor_num = data.monitor_num[0]
        prev_x = data.x[0]
        prev_y = data.y[0]
        prev_viewing_angle = data.viewing_angle[0]
        for monitor, x, y, viewing_angle in zip(data.monitor_num[1:], data.x[1:], data.y[1:], data.viewing_angle[1:]):
            if monitor == prev_monitor_num:
                new_data.monitor_num.append(monitor)
                new_data.x.append([prev_x, x])
                new_data.y.append([prev_y, y])
                new_data.viewing_angle.append((prev_viewing_angle + viewing_angle) / 2)
            prev_monitor_num = monitor
            prev_x = x
            prev_y = y
            prev_viewing_angle = viewing_angle
        return new_data

    def plot(self,
             show_colorbar: bool = False,
             segment_per_monitor: int = 99,
             width: int = 400,
             height: int = 400) -> tuple[Figure, GlyphRenderer]:
        """Plot the setup and its viewing angles"""

        data = self.get_line_segments(segment_per_monitor)

        min_angle = min(data.viewing_angle)
        max_angle = max(data.viewing_angle)
        colormap = LinearColorMapper(palette=Viridis256, low=min_angle, high=max_angle)

        fig, line = data.plot(colormap=colormap, show_colorbar=show_colorbar, width=width, height=height)
        return fig, line


def compare_setups(setups: list[Setup], line_segments: int = 200, width: int = 400, height: int = 400) -> Row:
    """Plot the viewing angles of multiple setups side by side"""

    num_setups = len(setups)
    data_list = [setup.get_line_segments(line_segments // num_setups) for setup in setups]
    min_angle = min(min(data.viewing_angle) for data in data_list)
    max_angle = max(max(data.viewing_angle) for data in data_list)

    colormap = LinearColorMapper(palette=Viridis256, low=min_angle, high=max_angle)

    fig_list: list[Figure] = []
    for i, data in enumerate(data_list):
        fig, _ = data.plot(colormap=colormap, show_colorbar=False, width=width, height=height)
        if i > 0:
            fig.x_range = fig_list[0].x_range
            fig.y_range = fig_list[0].y_range
        fig_list.append(fig)

    colorbar = ColorBar(color_mapper=colormap, label_standoff=12, border_line_color=None, location=(0, 0))
    colorbar_fig = figure(height=height,
                          width=120,
                          toolbar_location=None,
                          min_border=0,
                          outline_line_color=None,
                          title='Viewing angle (degrees)',
                          title_location='right')
    colorbar_fig.title.align = 'center'  # type: ignore

    colorbar_fig.add_layout(colorbar, 'right')

    fig_row = row(*fig_list, colorbar_fig)
    return fig_row


if __name__ == "__main__":
    setup_1 = Setup(monitors=[Monitor(24, 16 / 9), Monitor(24, 16 / 9)],
                    viewing_distance=60,
                    distance_unit="cm",
                    mode="perpendicular")

    setup_2 = Setup(monitors=[Monitor(34, 21 / 9, radius=1500)], viewing_distance=60, distance_unit="cm")

    fig_row = compare_setups([setup_1, setup_2], line_segments=200)

    # temporary solution to show the plot
    silence(MISSING_RENDERERS, True)
    show(fig_row)
