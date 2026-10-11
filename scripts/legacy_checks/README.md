# Legacy exploratory scripts — not part of the test suite

Ad-hoc scripts from the ResilienceRoute phase used to probe hazard maths, routing and
the weather provider. They are not maintained and are not collected by `pytest`.

- `test_hazard.py` sends GET requests to a live backend at `http://127.0.0.1:8000` when
  run (or collected by pytest) and asserts on its responses.
- `test_weather.py` calls the external Open-Meteo API through the weather service
  (network required).
- `test_hazard_math.py`, `test_routing.py` exercise service code directly and may need
  the OSM graph / DEM paths configured.
- They were moved here from `scripts/`; scripts that add `../backend` to `sys.path` need
  that path adjusted (`../../backend`) before they can run.

The maintained, offline tests live in `backend/tests/`.
