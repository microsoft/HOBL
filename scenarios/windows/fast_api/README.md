# FastAPI maintainer release-validation workload

This scenario validates the pinned FastAPI 0.119.1 source tree as a package
maintainer would. It is not FastAPI compilation and is not an application
developer inner loop.

The Windows `fast_api` and macOS `mac_fast_api` scenarios use Python 3.12.10 and
measure:

| Metric | Workload |
|---|---|
| `build_time` | Legacy `python -m build`, producing an sdist and then a wheel from that sdist. Kept for historical continuity. |
| `uv_build_time` | Modern `uv build`, preserving the same sdist then wheel-from-sdist validation contract. |
| `test_time` | The complete upstream FastAPI test suite under coverage. |
| `scenario_runtime` | Sum of the two package builds and full upstream validation. |

Build isolation uses the Microsoft-approved Python package feed. Prep performs
an untimed uv build warm-up, and both package output directories are cleaned
before each measured build. The timed command retains uv's normal isolated
build behavior.

The separate `fast_api_app` / `mac_fast_api_app` scenarios represent application
development: controlled locked sync, `fastapi dev` readiness, import plus
OpenAPI generation, focused tests, and optional reload.

## Windows ARM64

FastAPI is pure Python, so the unavailable Windows ARM64 `httptools` wheel does
not explain package-build timing. Optional `fastapi[standard]` setup may build
`httptools` from source on native ARM64; that dependency-install behavior is
documented and measured only by the app workload's controlled sync phase.

`pip --no-compile` is not used or recommended. It was diagnostic evidence only.
