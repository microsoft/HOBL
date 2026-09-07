# FastAPI maintainer release-validation workload

`mac_fast_api` is the macOS counterpart of Windows `fast_api`. It validates the
pinned FastAPI 0.119.1 source tree with Python 3.12.10 as a package maintainer
would; it is not application compilation or an application inner loop.

The scenario reports legacy `python -m build` as `build_time`, modern
sdist-then-wheel `uv build` as `uv_build_time`, and the complete upstream suite
under coverage as `test_time`. `scenario_runtime` is their sum. macOS also
reports user, system, and CPU time for each phase.

The separate `mac_fast_api_app` scenario uses the same locked sample application
as Windows and reports setup, startup, import/OpenAPI, focused tests, and reload
as distinct metrics. See
`scenarios/common/fast_api_app_workload/README.md` for the shared contract.

`pip --no-compile` is not used or recommended.
