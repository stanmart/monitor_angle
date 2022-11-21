from math import sin, cos, asin, atan, atan2, hypot, pi, inf, nan, degrees
from copy import copy

from bokeh.plotting import show, figure
from bokeh.models import ColumnDataSource, ColorBar
from bokeh.layouts import row
from bokeh.transform import linear_cmap
from bokeh.palettes import Viridis256

CM_CONVERSION = {"mm": 0.1, "cm": 1, "m": 100, "in": 2.54, "ft": 30.48}


class Point:

    def __init__(self, x, y):
        self.x = x
        self.y = y

    @classmethod
    def from_polar_coord(cls, radius, phase):
        x = radius * cos(phase)
        y = radius * sin(phase)
        return cls(x, y)

    def __add__(self, other):
        """Vector addition"""
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        """Vector subtraction"""
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        """Multiplication by scalar"""
        return Point(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar):
        """Division by scalar"""
        return Point(self.x / scalar, self.y / scalar)

    def __matmul__(self, other):
        """Inner (scalar) product"""
        return (self.x * other.x) + (self.y * other.y)

    def __abs__(self):
        return hypot(self.x, self.y)

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

    def phase(self):
        return atan2(self.y, self.x)

    def to_polar_coord(self):
        radius = abs(self)
        phase = self.phase()
        return radius, phase

    def rotate(self, angle):
        radius, phase = self.to_polar_coord()
        return Point.from_polar_coord(radius, phase + angle)

    __str__ = __repr__


class Monitor:

    def __init__(self, diagonal_length, aspect_ratio, radius=inf, diagonal_unit="in", radius_unit="mm"):

        if diagonal_unit not in CM_CONVERSION or radius_unit not in CM_CONVERSION:
            raise ValueError(f"units must be one of: {', '.join(CM_CONVERSION.keys())}")

        self.diagonal_length = diagonal_length * CM_CONVERSION[diagonal_unit]
        self.radius = radius * CM_CONVERSION[radius_unit]
        self.aspect_ratio = aspect_ratio

        self.left_end = None
        self.right_end = None
        self.circle_center = None

    def arc_width(self):
        """Calculates the arc width of the monitor and returns it in centimeters"""
        diagonal_angle = atan(1 / self.aspect_ratio)
        arc_width = cos(diagonal_angle) * self.diagonal_length
        return arc_width

    def chord_width(self):
        """Calculates the physical (chord) width of the monitor and returns it in centimeters"""
        arc_width = self.arc_width()
        if self.radius == inf:
            chord_width = arc_width
        else:
            central_angle = arc_width / self.radius
            chord_width = 2 * self.radius * sin(central_angle / 2)
        return chord_width

    def height(self):
        """Calculates the height of a monitor in centimeters"""
        diagonal_angle = atan(1 / self.aspect_ratio)
        height = sin(diagonal_angle) * self.diagonal_length
        return height

    def display_area(self):
        """Calculate the display area of a monitor in square centimeters"""
        return self.height() * self.arc_width()

    def depth(self):
        """Calculates the depth of a (possibly curved) screen"""
        if self.radius == inf:
            depth = 0
        else:
            central_angle = self.arc_width() / self.radius
            depth = self.radius * (1 - cos(central_angle / 2))
        return depth

    def arc_angle(self, position):
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

    def midpoint(self):
        return (self.left_end + self.right_end) / 2

    def get_circle_center(self):
        if self.radius == inf:
            circle_center = Point(nan, nan)
        else:
            chord_direction = (self.left_end - self.right_end).phase()
            midpoint_to_center_direction = chord_direction + pi / 2
            midpoint_to_center_length = self.radius - self.depth()
            circle_center = self.midpoint() + Point.from_polar_coord(midpoint_to_center_length,
                                                                     midpoint_to_center_direction)
        return circle_center

    def get_coordinate(self, position):
        """Get the coordinates of the monitor in a given position"""
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

    def viewing_angle(self, position, angle_unit="degrees"):
        """Get the coordinates and viewing angle between of a point of the monitor"""
        if angle_unit not in ["degrees", "radians"]:
            raise ValueError("angle unit must be either degrees or radians")
        position = self.get_coordinate(position)
        if self.radius == inf:
            chord_direction = (self.left_end - self.right_end).phase()
            screen_normal = (chord_direction - pi / 2) % (2 * pi)
        else:
            screen_normal = (position - self.circle_center).phase()
        view_phase = position.phase()
        view_angle_radians = view_phase - screen_normal
        if angle_unit == "radians":
            return position, view_angle_radians
        else:
            return position, degrees(view_angle_radians)


class Setup:

    def __init__(self, monitors, viewing_distance, mode="perpendicular", distance_unit="cm"):
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

    def _add_monitor(self, monitor, side, mode, rotate=None):
        monitor = copy(monitor)
        width = monitor.chord_width()

        if side == "middle":
            chord_distance = self.viewing_distance - monitor.depth()
            monitor.left_end = Point(-width / 2, chord_distance)
            monitor.right_end = Point(width / 2, chord_distance)
            if rotate:
                half_angle = atan((monitor.chord_width() / 2) / self.viewing_distance)
                monitor.left_end = monitor.left_end.rotate(-half_angle)
                monitor.right_end = monitor.right_end.rotate(-half_angle)
            self.monitors = [monitor]

        elif side == "left":
            adjacent_monitor = self.monitors[0]
            monitor.right_end = adjacent_monitor.left_end
            if mode == "perpendicular":
                end_dist, right_end_phase = monitor.right_end.to_polar_coord()
                half_angle = asin((monitor.chord_width() / 2) / end_dist)
                monitor.left_end = Point.from_polar_coord(end_dist, right_end_phase + 2 * half_angle)
            elif mode == "smooth":
                adjacent_monitor_phase = adjacent_monitor.midpoint().phase()
                curvature_diff = adjacent_monitor.arc_angle(0) - monitor.arc_angle(1)
                monitor_phase = adjacent_monitor_phase + curvature_diff
                monitor.left_end = monitor.right_end + Point.from_polar_coord(width, monitor_phase + pi / 2)
            self.monitors.insert(0, monitor)

        elif side == "right":
            adjacent_monitor = self.monitors[-1]
            monitor.left_end = adjacent_monitor.right_end
            if mode == "perpendicular":
                end_dist, left_end_phase = monitor.left_end.to_polar_coord()
                half_angle = asin((monitor.chord_width() / 2) / end_dist)
                monitor.right_end = Point.from_polar_coord(end_dist, left_end_phase - 2 * half_angle)
            elif mode == "smooth":
                adjacent_monitor_phase = adjacent_monitor.midpoint().phase()
                curvature_diff = adjacent_monitor.arc_angle(1) - monitor.arc_angle(0)
                monitor_phase = adjacent_monitor_phase + curvature_diff
                monitor.right_end = monitor.left_end + Point.from_polar_coord(width, monitor_phase - pi / 2)
            self.monitors.append(monitor)

        monitor.circle_center = monitor.get_circle_center()

    def get_viewing_angles(self, point_per_monitor=100, abs_angle=True):
        data = {"monitor": [], "x": [], "y": [], "viewing_angle": []}
        for monitor_num, monitor in enumerate(self.monitors):
            for i in range(point_per_monitor):
                position = i / (point_per_monitor - 1)
                position, angle = monitor.viewing_angle(position)
                if abs_angle:
                    angle = abs(angle)
                data["monitor"].append(monitor_num)
                data["x"].append(position.x)
                data["y"].append(position.y)
                data["viewing_angle"].append(angle)
        return data

    def get_line_segments(self, segment_per_monitor=99, abs_angle=True):
        data = self.get_viewing_angles(segment_per_monitor + 1, abs_angle)
        new_data = {"monitor": [], "x": [], "y": [], "viewing_angle": []}
        prev_monitor = data["monitor"][0]
        prev_x = data["x"][0]
        prev_y = data["y"][0]
        prev_viewing_angle = data["viewing_angle"][0]
        for monitor, x, y, viewing_angle in zip(data["monitor"][1:], data["x"][1:], data["y"][1:],
                                                data["viewing_angle"][1:]):
            if monitor == prev_monitor:
                new_data["monitor"].append(monitor)
                new_data["x"].append([prev_x, x])
                new_data["y"].append([prev_y, y])
                new_data["viewing_angle"].append((prev_viewing_angle + viewing_angle) / 2)
            prev_monitor = monitor
            prev_x = x
            prev_y = y
            prev_viewing_angle = viewing_angle
        return new_data


def compare_setups(setup_1, setup_2, line_segments=200):
    data_1 = setup_1.get_line_segments(line_segments // len(setup_1.monitors))
    data_2 = setup_2.get_line_segments(line_segments // len(setup_2.monitors))

    min_angle = min(data_1["viewing_angle"] + data_2["viewing_angle"])
    max_angle = max(data_1["viewing_angle"] + data_2["viewing_angle"])

    source_1 = ColumnDataSource(data_1)
    source_2 = ColumnDataSource(data_2)

    mapper = linear_cmap(field_name="viewing_angle", palette=Viridis256, low=min_angle, high=max_angle)
    color_bar = ColorBar(color_mapper=mapper["transform"], label_standoff=12, border_line_color=None, location=(0, 0))

    fig_1 = figure(width=400, height=400, match_aspect=True, aspect_scale=1)
    fig_1.toolbar.logo = None
    fig_1.toolbar_location = None
    fig_1.multi_line("x", "y", color=mapper, source=source_1, line_width=3)
    fig_1.circle(0, 0, size=10)

    fig_2 = figure(width=500,
                   height=400,
                   match_aspect=True,
                   aspect_scale=1,
                   x_range=fig_1.x_range,
                   y_range=fig_1.y_range)
    fig_2.multi_line("x", "y", color=mapper, source=source_2, line_width=3)
    fig_2.circle(0, 0, size=10)

    fig_2.add_layout(color_bar, "right")

    fig = row(fig_1, fig_2)
    show(fig)

    total_arc_width_1 = sum(monitor.arc_width() for monitor in setup_1.monitors)
    max_height_1 = max(monitor.height() for monitor in setup_1.monitors)
    display_area_1 = sum(monitor.display_area() for monitor in setup_1.monitors)

    total_arc_width_2 = sum(monitor.arc_width() for monitor in setup_2.monitors)
    max_height_2 = max(monitor.height() for monitor in setup_2.monitors)
    display_area_2 = sum(monitor.display_area() for monitor in setup_2.monitors)

    print(" " * 27, "|", "Setup 1".rjust(10), "Setup 2".rjust(10))
    print("-" * 28 + "+" + "-" * 22)
    print("Total screen width (cm)".ljust(27), "|", "{:>10.2f} {:>10.2f}".format(total_arc_width_1, total_arc_width_2))
    print("Largest screen height (cm)".ljust(27), "|", "{:>10.2f} {:>10.2f}".format(max_height_1, max_height_2))
    print("Total screen area (cm^2)".ljust(27), "|", "{:>10.2f} {:>10.2f}".format(display_area_1, display_area_2))


if __name__ == "__main__":
    setup_1 = Setup(monitors=[Monitor(24, 16 / 9), Monitor(24, 16 / 9)],
                    viewing_distance=60,
                    distance_unit="cm",
                    mode="perpendicular")

    setup_2 = Setup(monitors=[Monitor(34, 21 / 9, radius=1500)], viewing_distance=60, distance_unit="cm")

    compare_setups(setup_1, setup_2, line_segments=200)