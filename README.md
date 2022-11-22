# monitor_angle

A simple app to help you decide on a monitor setup. You can visualize the horizontal viewing angles of various multi-monitor setups side-by-side.

## How to use

You need to have a recently modern Python distribution (>= 3.7) and the bokeh plotting library. It is recommended to install the latter in a virtual environment. If you have those, you can serve the app locally on port 5006 using `bokeh serve`.

### Obtain repo and install dependencies
```bash
    git clone https://github.com/stanmart/monitor_angle.git
    cd monitor_angle

    python3 -m venv ./venv
    source venv/bin/activate
    pip install -r requirements.txt

```

### Run server
```bash
    source venv/bin/activate
    bokeh serve --show app.py
```
