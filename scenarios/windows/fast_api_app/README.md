# FastAPI application developer workload

`fast_api_app` measures a pinned FastAPI 0.119.1 application on native Windows
with Python 3.12.10. It uses the shared project and phase definitions in
`scenarios/common/fast_api_app_workload/README.md`.

The default five-loop run reports controlled offline locked sync, `fastapi dev`
readiness, import plus OpenAPI generation, and focused application tests.
`scenario_runtime` includes startup, import/OpenAPI, and tests only.

## Reload

Windows reload measurement must use an external foreground server so the
benchmark harness does not change Uvicorn's console-control topology:

```powershell
# First run fast_api_app once with reload_mode=none to create the locked venv.
pwsh <drive>\hobl_bin\fast_api_app_resources\fast_api_app_reload_server.ps1 -Port 8765
```

Keep that terminal in the foreground, then configure:

```ini
[fast_api_app]
reload_mode=external
reload_port=8765
```

The scenario does not force WatchFiles polling and does not replace Uvicorn's
graceful restart with hard termination. The external reload run reuses the
existing venv, so it reports reload/start/import/test metrics but intentionally
omits `sync_time`; use the preceding default run for that metric.

On Windows ARM64, prep builds the unavailable optional `httptools` wheel
natively from its sdist. That setup is cache priming, not a package-build phase.
