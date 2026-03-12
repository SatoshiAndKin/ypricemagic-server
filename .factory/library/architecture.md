# Architecture

Architectural decisions and patterns discovered.

---

- FastAPI app in `src/server.py`
- Parameter parsing in `src/params.py` with dataclasses (PriceParams, BatchParams)
- Generic utilities: `parse_bool_param`, `_parse_bool_with_default` — used by multiple params, not just skip_cache
- Tests in `src/tests/test_params.py` and `src/tests/test_server.py`
