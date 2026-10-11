# Legacy backend check scripts — do not run casually

These scripts come from the earlier ResilienceRoute phases (5B–6H). They are kept for
history and are **not** part of the maintained test suite (`backend/tests/`, run with
`pytest` from `backend/`; `pytest.ini` only collects `tests/`).

Several of them (`test_phase5b.py`, `test_phase5c.py`, `e2e_test.py`,
`test_operational_fixes.py`, …) send HTTP requests to `http://127.0.0.1:8000` **at
import time** and create, modify or close records. Running them against a live backend
changes its database. If you must run one, point it at a throwaway backend started with
a fresh `DATABASE_PATH`.

Their pass/fail claims (e.g. in `docs/archive/`) predate the AEGIS-COP work and are not
current evidence; see `docs/project/IMPLEMENTATION_STATUS.md` for that.

They were moved here from `backend/`; scripts that add their own directory to
`sys.path` expect to sit in `backend/`, so copy one back temporarily if you need to run it.
