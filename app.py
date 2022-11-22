from bokeh.layouts import column, row
from bokeh.models import NumericInput, Div, CheckboxButtonGroup, RadioButtonGroup, Column, Slider
from bokeh.io import curdoc

from monitor_positions import Monitor, Setup


def create_setup_ui() -> Column:
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

    perpendicular_radio = RadioButtonGroup(labels=["Perpendicular", "Smooth"], active=0)
    perpendicular_row = row(Div(text="Monitor alignment: "), perpendicular_radio)

    aspect_h = NumericInput(value=16, low=1, high=100, width=60)
    aspect_v = NumericInput(value=9, low=1, high=100, width=60)
    aspect_box = row(Div(text="Aspect ratio:"), aspect_h, Div(text=":"), aspect_v)
    size_input = Slider(value=24, start=10, end=60, step=1, title="Monitor size (inches)")
    size_row = row(size_input, aspect_box)

    curved_checkbox = CheckboxButtonGroup(labels=["Curved"], active=[])
    radius_slider = Slider(start=500, end=3000, value=1500, step=100, title="Radius", disabled=True)
    curve_row = row(curved_checkbox, radius_slider)

    def enable_radius_slider(attr, old, new):
        if 0 in curved_checkbox.active:  # type: ignore
            radius_slider.disabled = False  # type: ignore
        else:
            radius_slider.disabled = True  # type: ignore
    curved_checkbox.on_change("active", enable_radius_slider)

    setup_ui = column(perpendicular_row, monitor_row, size_row, curve_row)
    return setup_ui


setup_ui = create_setup_ui()
curdoc().add_root(setup_ui)
