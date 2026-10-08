# FastAPI application developer workload

`mac_fast_api_app` measures the same pinned FastAPI 0.119.1 application and
phase contract as Windows `fast_api_app`. See
`scenarios/common/fast_api_app_workload/README.md` for exact definitions.

The default five-loop run reports controlled offline locked sync, `fastapi dev`
readiness, import plus OpenAPI generation, and focused tests. Reload is excluded
from `scenario_runtime`.

Set `reload_mode=managed` to include edit-to-reloaded-response as the separate
`reload_time` metric. `reload_mode=external` is also available when a server is
already running in another foreground terminal. Neither mode forces WatchFiles
polling or changes Uvicorn's restart behavior.

`pip --no-compile` is not used or recommended.
