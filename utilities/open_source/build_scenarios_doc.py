# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Build scenarios documentation
##

import os
import argparse
import sys
from core.parameters import Params
from utilities.open_source.dump_scenarios import main as dump_scenarios_main
import importlib

def main():

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-path', '-p', default='docs\\support\\docs')
    args = arg_parser.parse_args()
    doc_path = os.path.join(args.path, "HOBL_Scenarios.md")

    # Run utiliites/open_source/dump_scenarios.py to get scenario docs
    dump_scenarios_main(print_json=False, short=False)
    from utilities.open_source.dump_scenarios import scenario_docs

    with open(doc_path, "w", encoding="utf-8") as doc_file:
        doc_file.write("# Scenarios\n\n")
        for scenario, docstring in scenario_docs.items():
            if docstring is not None:
                # write scenario heading and docstring
                doc_file.write(f"## {scenario}\n\n")
                doc_file.write(f"{docstring}\n\n")

                # Find path to scenario file
                Params.clear()
                path = None
                scenarios_dir = os.path.join(os.getcwd(), 'scenarios')
                for platform in ["windows", "macos", "common"]:
                    scenarios_dir_sub = os.path.join(os.getcwd(), 'scenarios', platform)
                    path = os.path.join(scenarios_dir_sub, scenario + ".py")
                    if os.path.isfile(path):
                        break
                    path = os.path.join(scenarios_dir_sub, scenario, scenario + ".py")
                    if os.path.isfile(path):
                        break
                if path is None:
                    print(f"ERROR Could not find scenario file for {scenario}")
                    continue

                # import scenario
                module = "scenarios." + platform + "." + scenario
                m = importlib.import_module(module)

                # get parameters for scenario
                Params.dumpDefaultWithInfo(print_json=False)

                if len(Params.defaultsInfo) == 0:
                    continue
                # write parameters to doc
                doc_file.write(f"\n<u>Parameters:</u>\n\n")
                for section in Params.defaultsInfo:
                    for key in Params.defaultsInfo[section]:
                        valOptions = Params.defaultsInfo[section][key]["valOptions"]

                        if len(valOptions) == 1 and valOptions[0].startswith("@\\"):
                            pass
                        else:
                            desc = Params.defaultsInfo[section][key]["desc"]
                            default = Params.get(section, key, log=False)
                            options = ""
                            if len(valOptions) > 0:
                                options = f" **Options:** `{', '.join(valOptions)}`"
                            doc_file.write(f"`{key}` - {desc} **Default:** `{default}` {options}\n\n")

                # Unimport the scenario so that subsequent scenarios that reference the same base modules, will get parameters reloaded.
                for module in list(sys.modules.keys()):
                    if module.startswith("scenarios."):
                        del sys.modules[module]


if __name__ == '__main__':
    main()
