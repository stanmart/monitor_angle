from math import inf
from dataclasses import dataclass

from bokeh.plotting import Figure
from bokeh.layouts import column, row
from bokeh.models import NumericInput, Div, CheckboxButtonGroup, RadioButtonGroup, Column, Slider, GlyphRenderer
from bokeh.io import curdoc

from monitor_positions import Monitor, Setup


@dataclass
class MonitorData:
    """Data for a single monitor."""
    diagonal_length: float
    radius: float
    aspect_h: int
    aspect_v: int


@dataclass
class SetupData:
    """Data for the setup."""
    viewing_distance: float
    num_monitors: int
    alignment: str


@dataclass
class Widgets:
    """Widgets for the UI."""
    num_monitors: Slider
    monitor_id: RadioButtonGroup
    viewing_distance: Slider
    alignment: RadioButtonGroup
    monitor_size: Slider
    aspect_h: NumericInput
    aspect_v: NumericInput
    curved: CheckboxButtonGroup
    radius: Slider


def create_setup_ui() -> tuple[Column, Widgets]:
    """Create the UI for changing setup and monitor positions."""

    num_slider = Slider(start=1, end=5, value=2, step=1, title="Number of monitors")
    id_radio = RadioButtonGroup(labels=["1", "2"], active=0)
    monitor_row = row(num_slider, id_radio)

    def update_id_radio(attr, old, new):
        old_id = id_radio.active
        id_radio.labels = [str(i) for i in range(1, new + 1)]  # type: ignore
        if old_id <= new - 1:
            id_radio.active = old_id
        else:
            id_radio.active = new - 1

    num_slider.on_change("value", update_id_radio)

    viewing_distance_slider = Slider(start=30, end=150, value=60, step=10, title="Viewing distance (cm)")
    perpendicular_radio = RadioButtonGroup(labels=["Perpendicular", "Smooth"], active=0)
    perpendicular_row = row(viewing_distance_slider, perpendicular_radio)

    aspect_h = NumericInput(value=16, low=1, high=100, width=60)
    aspect_v = NumericInput(value=9, low=1, high=100, width=60)
    aspect_box = row(Div(text="Aspect ratio:"), aspect_h, Div(text=":"), aspect_v)
    size_input = Slider(value=24, start=10, end=60, step=1, title="Monitor size (inches)")
    size_row = row(size_input, aspect_box)

    curved_checkbox = CheckboxButtonGroup(labels=["Curved"], active=[])
    radius_slider = Slider(start=500, end=3000, value=1500, step=100, title="Radius (mm)", disabled=True)
    curve_row = row(curved_checkbox, radius_slider)

    def enable_radius_slider(attr, old, new):
        if 0 in curved_checkbox.active:  # type: ignore
            radius_slider.disabled = False  # type: ignore
        else:
            radius_slider.disabled = True  # type: ignore

    curved_checkbox.on_change("active", enable_radius_slider)

    setup_ui = column(perpendicular_row, monitor_row, size_row, curve_row)
    widgets = Widgets(num_monitors=num_slider,
                      monitor_id=id_radio,
                      viewing_distance=viewing_distance_slider,
                      alignment=perpendicular_radio,
                      monitor_size=size_input,
                      aspect_h=aspect_h,
                      aspect_v=aspect_v,
                      curved=curved_checkbox,
                      radius=radius_slider)

    return setup_ui, widgets


def create_default_plot() -> tuple[Figure, GlyphRenderer, list[MonitorData]]:
    """Create the plot for displaying the monitor positions."""
    default_monitor = MonitorData(diagonal_length=24, radius=inf, aspect_h=16, aspect_v=9)
    default_setup = SetupData(num_monitors=2, alignment="perpendicular", viewing_distance=60)
    default_monitor_data = [default_monitor] * default_setup.num_monitors

    setup = create_setup(default_setup, default_monitor_data)
    fig, line = setup.plot(width=600, show_colorbar=True)

    return (fig, line, default_monitor_data)


def create_setup(setup_data: SetupData, monitor_data: list[MonitorData]) -> Setup:
    """Create a setup from the data."""
    monitors = [
        Monitor(diagonal_length=monitor.diagonal_length,
                aspect_ratio=monitor.aspect_h / monitor.aspect_v,
                radius=monitor.radius) for monitor in monitor_data
    ]
    setup = Setup(monitors, mode=setup_data.alignment, viewing_distance=setup_data.viewing_distance)
    return setup


def create_column(title: str = ""):

    def onchange_setting(attr, old, new) -> None:
        """Callback for when the monitor data changes."""

        changed_monitor = MonitorData(diagonal_length=widgets.monitor_size.value,
                                    radius=widgets.radius.value if 0 in widgets.curved.active else inf,
                                    aspect_h=widgets.aspect_h.value,
                                    aspect_v=widgets.aspect_v.value)
        monitor_data[widgets.monitor_id.active] = changed_monitor
        alignment = "perpendicular" if widgets.alignment.active == 0 else "smooth"

        setup = create_setup(
            SetupData(
                num_monitors=widgets.num_monitors.value,  # type: ignore
                alignment=alignment,  # type: ignore
                viewing_distance=widgets.viewing_distance.value),  # type: ignore
            monitor_data)
        line.data_source.data = vars(setup.get_line_segments())


    def onchange_monitor_id(attr, old, new) -> None:
        """Callback for when the monitor ID changes."""
        monitor = monitor_data[new]
        widgets.monitor_size.value = monitor.diagonal_length
        widgets.aspect_h.value = monitor.aspect_h
        widgets.aspect_v.value = monitor.aspect_v
        if monitor.radius == inf:
            widgets.curved.active = []
            widgets.radius.disabled = True
        else:
            widgets.curved.active = [0]
            widgets.radius.disabled = False
            widgets.radius.value = monitor.radius


    def onchange_monitor_num(attr, old, new) -> None:
        """Callback for when the number of monitors changes."""
        if new > old:
            for _ in range(new - old):
                monitor_data.append(MonitorData(diagonal_length=24, radius=inf, aspect_h=16, aspect_v=9))
        else:
            for _ in range(old - new):
                monitor_data.pop()

        alignment = "perpendicular" if widgets.alignment.active == 0 else "smooth"
        setup = create_setup(
            SetupData(
                num_monitors=widgets.num_monitors.value,  # type: ignore
                alignment=alignment,  # type: ignore
                viewing_distance=widgets.viewing_distance.value),  # type: ignore
            monitor_data)
        line.data_source.data = vars(setup.get_line_segments())

    fig, line, monitor_data = create_default_plot()

    setup_ui, widgets = create_setup_ui()
    for widget in [widgets.viewing_distance, widgets.monitor_size, widgets.aspect_h, widgets.aspect_v, widgets.radius]:
        widget.on_change("value", onchange_setting)
    for widget in [widgets.curved, widgets.alignment]:
        widget.on_change("active", onchange_setting)
    widgets.monitor_id.on_change("active", onchange_monitor_id)
    widgets.num_monitors.on_change("value", onchange_monitor_num)

    return column(Div(text=f"<h2>{title}</h2>"), setup_ui, fig)


col_1 = create_column("Setup 1")
col_2 = create_column("Setup 2")
content = row(col_1, col_2)
curdoc().add_root(content)
