# FastAPI application developer workload

This shared project backs HOBL's Windows `fast_api_app` and macOS
`mac_fast_api_app` scenarios. It represents a newly created FastAPI application,
not FastAPI package-maintainer release validation.

## Pinned inputs

- Python 3.12.10
- FastAPI 0.119.1 with the `standard` extra
- One checked-in cross-platform `uv.lock`
- The Microsoft-approved Python package feed

The app has Pydantic request/response models, dependency injection, an in-memory
store, list/get/create routes, and a health endpoint with an editable build
marker. The focused tests cover those application behaviors.

## Metrics

| Metric | Timed operation |
|---|---|
| `sync_time` | Delete the project `.venv`, then run default `uv sync --frozen --offline` from a cache primed during prep. Network downloads are not timed, and uv's default lazy-bytecode behavior is preserved. |
| `server_start_time` | Launch `fastapi dev` and poll until `/health` returns the expected build marker. |
| `import_openapi_time` | Start a fresh app Python process, import the app, generate OpenAPI, and validate its path count. |
| `app_test_time` | Run the focused application pytest suite. |
| `reload_time` | Edit the build marker and poll until the already-running reload server returns the new value. Optional and reported separately. |
| `scenario_runtime` | `server_start_time + import_openapi_time + app_test_time`. Sync and reload are deliberately excluded. |

Each phase is repeated by the harness, and HOBL reports the median. Detailed
per-iteration CSV, JSON, and logs are retained with the scenario results.
An external reload run reuses the existing app venv and therefore omits
`sync_time`; run the default no-reload workload first for the controlled sync
metric.

## Bytecode interpretation

Default uv sync does not eagerly compile Python bytecode, unlike a default pip
install. The two setup timings therefore do not have identical semantics:
some `.pyc` work is deferred until modules are first imported. This workload
intentionally keeps uv's default behavior because it represents the normal uv
developer workflow. The separate `import_openapi_time` phase includes the first
fresh-process app import, where deferred bytecode work can appear.

Controlled warm-cache medians for this same 46-package lock and Python 3.12.10
were:

| Install mode | Windows | WSL2 |
|---|---:|---:|
| Default `uv sync` | 1.899s | 0.146s |
| `uv sync --compile-bytecode` | 5.078s | 0.684s |
| Default offline venv + pip install | 54.35s | 9.16s |
| Pip install with `--no-compile` | 20.47s | 5.589s |

If package-manager installation is compared, `uv sync --compile-bytecode` is
the controlled eager-bytecode uv comparison. HOBL does not add that comparison
to this application workload or prescribe `pip --no-compile`: the latter is a
valid tradeoff for some ephemeral environments, but it shifts bytecode work to
first import. Even with eager bytecode compilation, uv remained about 10.7x
faster than default pip on Windows in the controlled data, so its advantage was
not solely deferred compilation.

## Reload interpretation

Reload is not part of the primary application-loop aggregate. On macOS the
harness may own a managed reload server. On Windows, Uvicorn restarts workers by
broadcasting `CTRL_C_EVENT` to its process console, so a benchmark-owned process
tree changes the behavior under test. Windows reload therefore requires the
provided server helper to run in a separate foreground terminal and the HOBL
scenario to use `reload_mode=external`. Run the default workload once before
starting the helper so the locked app venv exists. HOBL preserves the shared
app directory during an external reload run rather than refreshing it beneath
the foreground server.

The workload does not force WatchFiles polling and does not replace Uvicorn's
graceful worker restart with hard termination. Process-tree termination is used
only after the separately measured startup-readiness phase has completed.

## Windows ARM64

`httptools` 0.8.0 does not publish a Windows ARM64 wheel. A native ARM64 Python
cannot use the x64 wheel through transparent emulation; the installer selects
the source distribution and builds it with the native toolchain during prep.
That dependency setup is real `fastapi[standard]` behavior, but it is not the
cause of the FastAPI package-build timing and is not included in app phase
metrics.

`pip --no-compile` is not the general recommendation for this workload.
