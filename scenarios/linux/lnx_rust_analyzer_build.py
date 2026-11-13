# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root.
from scenarios.rust_build_resources import scenario


class LnxRustAnalyzerBuild(scenario.RustBuildScenario):
    module = __module__.split(".")[-1]
    workload = "rust_analyzer_build"
    scenario.defaults(module)
