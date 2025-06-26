OSRD Extract Timetable
=====

When working with [OSRD](https://osrd.fr), you might be interested only in a
subset of trains in a timetable. This tool will help you extract those trains.

```sh
uv sync
export GATEWAY_TOKEN=<some_value>
uv run main.py
# Let the program guide you
```

See an example below

https://github.com/user-attachments/assets/c6ca9725-85e1-4049-90da-fcbc9304d29d

If you need some special SSL certificates, you can do the following.

```
export REQUESTS_CA_BUNDLE=cert.pem

```
