# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from posixpath import basename
import sys
import argparse
import glob
import os
import csv
import collections
import pandas as pd
import json

# CURRENT REPORT VERSION
RUN_REPORT_VERSION = 2.0

def main():


    arg_parser = argparse.ArgumentParser(description = "Concatenate various .csv metric files into one metrics.csv.")
    arg_parser.add_argument('-recurse', '-r', help='Search directories recursively.', action="store_true")
    arg_parser.add_argument('-dir', '-d', nargs='?', default='.', help='Directory to start search')
    arg_parser.add_argument('-goals', '-g', nargs='?', default='', help='Directory to start search')
    arg_parser.add_argument('-files', '-f', nargs='*', default=['*.csv'], help='list of .csv files, can use wildcards.')
    arg_parser.add_argument('-warn_limit', '-w', nargs='*', default='', help='limit for warn in percent.')
    arg_parser.add_argument('-goal_limit', '-l', nargs='*', default='30', help='limit for goals in percent.')
    arg_parser.add_argument('-phase_power_type', '-p', default="Total", help='Phase report power type to be rolled up to metrics file.')
    arg_parser.add_argument('-fail_on', '-o', nargs='+', default='', help='Metrics to fail on')
    args = arg_parser.parse_args()

    args.files =  ['rundown.csv', '*power_data.csv', 'maxim_summary*.csv', '*power_light_summary.csv', '*e3_power_summary.csv', '*ConfigPre.csv', '*ConfigPost.csv', '*top_processes.csv', '*socwatch.csv', '*.csv']
    print (args.dir)
    print (args.files)
    print (args.goals)
    # print ("Goal limit: " + args.goal_limit[0])
    # print ("Warn limit: " + args.warn_limit[0])
    # time.sleep(60)

    fail_on = [x.replace("_", " ") for x in args.fail_on]
    #goal_limit and warn_linit are passed as percentage
    goal_limit = (int(args.goal_limit[0]) + 100) / 100
    # warn_limit = (int(args.warn_limit[0]) + 100) / 100
    print ("Goal limit: " + str(round(goal_limit,3)))
    # print ("Warn limit: " + str(round(warn_limit,3)))

    dirpath = os.path.abspath(args.dir)
    for basepath in args.files:
        print ("Basepath: " + basepath)

    # List of csv files we don't want to rollup.
    exception_list = [
        "*_metrics.csv",
        "*_full_processes.csv",
        "*_PerfResult.csv",
        "batlog.csv",
        "log.csv",
        "maxim_trace_*.csv",
        "*_pm.csv",
        "*_session_summary.csv",
        "phase_time.csv",
        "scenario_events.csv",
        "*_power_heavy.csv",
        "srumutil.csv",
        "*_DAQ.csv"
    ]

    def is_exception(file):
        for exception in exception_list:
            if glob.fnmatch.fnmatch(file, exception):
                return True
        return False

    def is_float(value):
        try:
            float(value)
            return True
        except ValueError:
            return False

    # def walklevel(path, depth = 1):
    #     """It works just like os.walk, but you can pass it a level parameter
    #        that indicates how deep the recursion will go.
    #        If depth is 1, the current directory is listed.
    #        If depth is 0, nothing is returned.
    #        If depth is -1 (or less than 0), the full depth is walked.
    #     """
    #     # If depth is negative, just walk
    #     # Not using yield from for python2 compat
    #     # and copy dirs to keep consistant behavior for depth = -1 and depth = inf
    #     if depth < 0:
    #         for root, dirs, files in os.walk(path):
    #             yield root, dirs[:], files
    #         return
    #     elif depth == 0:
    #         return

    #     # path.count(os.path.sep) is safe because
    #     # - On Windows "\\" is never allowed in the name of a file or directory
    #     # - On UNIX "/" is never allowed in the name of a file or directory
    #     # - On MacOS a literal "/" is quitely translated to a ":" so it is still
    #     #   safe to count "/".
    #     base_depth = path.rstrip(os.path.sep).count(os.path.sep)
    #     for root, dirs, files in os.walk(path):
    #         yield root, dirs[:], files
    #         cur_depth = root.count(os.path.sep)
    #         if base_depth + depth <= cur_depth:
    #             del dirs[:]

    # Process .csv files
    act_scenario = ""
    for root, dirs, files in os.walk(dirpath):
        found_one = False
        run_name = ""
        metrics = collections.OrderedDict()
        daq_metrics = collections.OrderedDict()
        pm_metrics = collections.OrderedDict()
        pm_summary_metrics = collections.OrderedDict()
        e3_metrics = collections.OrderedDict()
        phase_metrics = collections.OrderedDict()
        full_config_metrics = collections.OrderedDict()
        config_metrics = collections.OrderedDict()
        run_info_metrics = collections.OrderedDict()
        study_var_metrics = {}
        rails = {"Mean":{}}
        # metrics = []

        # Loop through .csv files we want to roll up
        for arg_file in args.files:
            match = False
            # Loop through files in run folder and read .csv files that match arg list
            for file in files: 
                # print("File: " + file)
                if glob.fnmatch.fnmatch(file, arg_file):
                    if is_exception(file):
                        continue
                    # Don't rollup files under the "socwatch" or "phm" folders
                    if root[-8:].lower() == "socwatch":
                        break
                    if root[-3:].lower() == "phm":
                        break
                    match = True
                    found_one = True
                    print (u"Processing: " + root + os.sep + file)
                    inputfile = root + os.sep + file
                    with open(inputfile) as csvfile:
                        try:
                            reader = csv.reader(csvfile, delimiter=',', quotechar='"')
                            for r in reader:
                                if "rails.csv" in file:
                                    if len(r) == 5:
                                        # rail_key = r[0].split()[-1].lower()
                                        # if rail_key in rails["mean"].keys():
                                        if "power" in r[0].lower() or "voltage" in r[0].lower():
                                            rails["Mean"][r[0]] = r[2]
                                            # rails["maximum"][rail_key][r[0]] = r[3]
                                            # rails["minimum"][rail_key][r[0]] = r[4]
                                elif len(r) > 1:
                                    if r[1] == "NaN":
                                        r[1] = ""
                                    m = round(float(r[1]), 3) if is_float(r[1]) else r[1]
                                    try:
                                        # Check if the string is "nan"
                                        if str(m).lower() == "nan":
                                            continue
                                    except:
                                        pass
                                    if "_power_data.csv" in file:
                                        daq_metrics[r[0]] = m
                                    elif "_power_light.csv" in file:
                                        pm_metrics[r[0]] = m
                                    elif "_power_light_summary.csv" in file:
                                        pm_summary_metrics[r[0]] = m
                                    elif "_e3_power_summary.csv" in file:
                                        e3_metrics[r[0]] = m
                                    elif "Config.csv" in file:
                                        full_config_metrics[r[0]] = r[1]
                                    elif "ConfigPre.csv" in file:
                                        config_metrics[r[0]] = r[1]
                                    elif "ConfigPost.csv" in file:
                                        config_metrics[r[0]] = r[1]
                                    elif "run_info.csv" in file:
                                        run_info_metrics[r[0]] = r[1]
                                    elif "study_vars.csv" in file:
                                        simplied_key = r[0].replace("VAR_", '')
                                        study_var_metrics[simplied_key] = r[1]
                                    else:
                                        metrics[r[0]] = m
                        except:
                            print (u"WARNING - Could not read: " + inputfile)

        run_name = os.path.basename(root)
        # if 'Scenario' in metrics:
        #     act_scenario = metrics["Scenario"]
        #     print("Setting act_scenario to: " + act_scenario)

        # if 'Scenario' not in metrics:
        #     # Then this is probably a phase report sub folder, so use previously found Scenario
        #     metrics['Scenario'] = act_scenario
        #     print("Setting Scenario to: " + act_scenario)

        # if 'Test Name' not in metrics:
        #     metrics['Test Name'] = run_name[0:-4]

        if not match:
            print (u"File not found: " + root + os.sep + arg_file)

        if found_one:
            # We don't want to generate *metrics.csv file for phase folders, except for level 1 abl_prod, abl_idle, and abl_web
            is_l1_phase = ("." in os.path.basename(root) and len((os.path.basename(root).split("."))[1].split("_")) == 2)
            is_only_l1 = run_name.split(".")[0] in ["abl_web", "web", "abl_prod", "productivity", "abl_prod_poc", "abl_idle", "idle_apps", "abl_standby"]
            print("Found one: " + root + ", scenario: " + act_scenario + ", is_l1_phase: " + str(is_l1_phase) + ", only_l1: " + str(is_only_l1))
            if (is_l1_phase and not is_only_l1):
                print ("Found1: " + root)
                json_name = root + os.sep + run_name + "_metrics.json"
                print (u"Writing JSON file: " + json_name)
                phase_report = {}
                for key, value in daq_metrics.items():
                    phase_report[key] = value
                phase_report["Scenario"] = run_name.split(".")[0]
                phase_report["Test Name"] = run_name[0:-4]
                with open(json_name, 'w') as file:
                    json.dump(phase_report, file, indent=4)


            # # Add power data in top level metrics file and generate metrics file for level 1 phases.
            if os.path.exists(os.path.dirname(os.path.dirname(root)) + os.sep + "phase_time.csv"):
                print ("Found2: " + os.path.dirname(root))
                json_name = os.path.dirname(os.path.dirname(root)) + os.sep + os.path.basename(os.path.dirname(os.path.dirname(root))) + "_metrics.json"
                print (u"Writing json file: " + json_name)
                with open(json_name, 'r') as file:
                    data = json.load(file)
                
                # Check if "all" key is in data
                if "All" not in data["DAQ"]["Phase"].keys():
                    data["DAQ"]["Phase"]["All"] = {}
                # match the phase power that we want to see and write to the metrics.json file.
                metrics_lower = {k.lower():v for k,v in daq_metrics.items()}
                phase_power_types = args.phase_power_type.split(",")
                for power_type in phase_power_types:
                    if (power_type +" Power (W)").lower() in metrics_lower:
                        data["DAQ"]["Phase"]["All"]["Phase " + power_type +" Power (W) " + run_name.split(".")[-1].rsplit("_", 1)[0]] = metrics_lower[(power_type +" Power (W)").lower()]
                with open(json_name, 'w') as file:
                    json.dump(data, file, indent=4)
                
            if os.path.exists(root + os.sep + "hobl.log"):
                json_name = root + os.sep + run_name + "_metrics.json"
                print (u"Writing JSON file: " + json_name)

                run_obj = {}

                # Insert the report version
                run_obj["Run Report Version"] = RUN_REPORT_VERSION 

                # Put these ones at top
                for key in metrics.keys():
                    # Copy key run values
                    if key == "Run Path" or key == "Run URL" or key == "Run Type" or key == "Run Number" or key == "Scenario" or key == "Test Name":
                        run_obj[key] = metrics[key]

                # # Add Config data to run
                # run_obj["Config"] = config_obj[0]

                # Initialize sections
                for key in run_info_metrics.keys():
                    run_obj[key] = run_info_metrics[key]
                run_obj["DAQ"] = {}
                run_obj["DAQ"]["Summary"] = {}
                run_obj["DAQ"]["Rails"] = rails
                run_obj["DAQ"]["Phase"] = {}
                for key in daq_metrics.keys():
                    run_obj["DAQ"]["Summary"][key] = daq_metrics[key]
                run_obj["PM"] = {}
                run_obj["PM"]["Summary"] = {}
                run_obj["PM"]["Rails"] = {}
                for key in pm_metrics.keys():
                    run_obj["PM"]["Rails"][key] = pm_metrics[key]
                for key in pm_summary_metrics.keys():
                    run_obj["PM"]["Summary"][key] = pm_summary_metrics[key]
                run_obj["E3"] = {}
                for key in e3_metrics.keys():
                    run_obj["E3"][key] = e3_metrics[key]
                run_obj["Config"] = {}
                for key in full_config_metrics.keys():
                    run_obj["Config"][key] = full_config_metrics[key]
                for key in config_metrics.keys():
                    if key == "Test Name" or key == "Scenario":
                        continue
                    run_obj["Config"][key] = config_metrics[key]
                run_obj["Variables"] = study_var_metrics

                run_obj["Metrics"] = {}
                for key in metrics.keys():
                    run_obj["Metrics"][key] = metrics[key]
     

                with open(json_name, 'w') as f:
                    json.dump(run_obj, f, indent=4)


            if (args.goals != "" and args.goals != None):
                # Only check goals on main runs, not phases
                if os.path.exists(root + os.sep + "hobl.log"):
                    goals = pd.read_csv(args.goals, index_col=0, header=0, sep=',')
                    goals.dropna(how='all', inplace=True)
                    #metrics = pd.read_csv(csv_name, names=['metric', 'val'], index_col=0, sep=',')
                    scenario = config_metrics['Test Name']
                    if scenario in goals or "Default" in goals or "default" in goals:
                        all_metrics = [run_info_metrics, daq_metrics, pm_metrics, e3_metrics, full_config_metrics, config_metrics, metrics]

                        result_dict = {}
                        for metric in all_metrics:
                            for key, val in metric.items():
                                if 'Process' in key:
                                    try:
                                        res_key = 'Process ' + val.split('-')[1]
                                        res_val = val.split('-')[0].replace('mW', '')
                                        result_dict[res_key] = res_val
                                    except:
                                        pass
                                else:
                                    result_dict[key] = val

                        # Convert all goal data to lower case
                        goals.columns = goals.columns.str.lower()
                        print(goals)
                        print("Scenario: " + str(scenario))

                        # Iterate through metrics in goals file for this scenario
                        failed_metrics = []
                        fail_on_metrics = []
                        # warn_flag = ""
                        fail_flag = ""

                        for result_metric in result_dict:
                            # result_val = result_dict['val'][result_metric]
                            result_val = result_dict[result_metric]
                            # print ("result_val: " + str(result_val))
                            fail = False
                            fail_reason = ""
                            goal = ""
                            goal_val = ""

                            if "Process" in result_metric:
                                matching_goals = (goal for goal in goals.index if goal in result_metric)
                                goal = next(matching_goals, "")
                            elif result_metric in goals.index:
                                goal = result_metric

                            if goal != "":
                                if scenario in goals:
                                    goal_val = str(goals[scenario][goal])
                                    print("Goal check for " + result_metric + ": Goal=" + goal_val + ", Result=" + str(result_val))
                                else:
                                    print("Scenario " + scenario + " not found in goals csv file.")
                                    continue

                                if '-' in goal_val:
                                    if (float(result_val) > float(goal_val.split('-')[1])):
                                        fail = True
                                        fail_reason = ":HIGH"
                                    if (float(result_val) < float(goal_val.split('-')[0])):
                                        fail = True
                                        fail_reason = ":LOW"
                                elif '+' in goal_val:
                                    tmp_goal_limit = float((int(goal_val.split('+')[1].replace('%', '')))/100)
                                    if (float(result_val) > (float(goal_val.split('+')[0]) * (1.0 + tmp_goal_limit))):
                                        fail = True
                                        fail_reason = ":HIGH"
                                    if (float(result_val) < (float(goal_val.split('+')[0]) * (1.0 - tmp_goal_limit))):
                                        fail = True
                                        fail_reason = ":LOW"
                                elif '@' in goal_val:
                                    # Handle case where goal_val is "@60" and "result_val is "60.0".  We want them to match, so convert both to float.  But also need to match strings.
                                    goal_val_val = goal_val.split('@')[1]
                                    if (is_float(result_val) and is_float(goal_val_val)):
                                        if float(result_val) != float(goal_val_val):
                                            fail = True
                                            fail_reason = ":NOT MATCH"
                                    elif result_val != goal_val_val:
                                        fail = True
                                        fail_reason = ":NOT MATCH"
                                elif (goal_val.isdigit() or goal_val.replace('.', '').isdigit()):
                                    if (float(result_val) > float(goal_val) * goal_limit):   # goal_limit is percentage such as '30'
                                        fail = True
                                        fail_reason = ":HIGH"
                                    if (float(result_val) < float(goal_val) / goal_limit):   # goal_limit is percentage such as '30'
                                        fail = True
                                        fail_reason = ":LOW"
                                elif goal_val.isalpha() and goal_val != "nan":
                                    if goal_val not in result_val:
                                        fail = True
                                        fail_reason = ":NOT MATCH"
                                elif goal_val == "" or goal_val is None or goal_val == "nan":
                                    continue
                            # elif 'Process' in result_metric:
                                # fail = True
                                # result_metric = result_metric + ":UNEXPECTED PROCESS"
                                # print ("Metric " + result_metric + " not found in goals csv")
                            else:
                                # print ("Metric " + result_metric + " not found in goals csv")
                                continue

                            if (fail):
                                # Append failing metric to list of failed metrics
                                failed_metrics.append(result_metric + fail_reason)
                                if (result_metric in fail_on):
                                    fail_on_metrics.append ("Metric " + result_metric + fail_reason + " is not within goal limits")

                        # Append pass/fail and list of failed metrics to metrics.csv
                        # goals_check_failing_metrics: SOC Power (W) | Run Duration | 
                        # goals_check: PASS/FAIL
                        goals_check_res = {}
                        if (len(failed_metrics) > 0):
                            goals_check_res['goals_check'] = 'FAIL'
                            goals_check_res['goals_check_failing_metrics'] = ' | '.join(metric for metric in failed_metrics)
                        else:
                            goals_check_res['goals_check'] = 'PASS'
                            goals_check_res['goals_check_failing_metrics'] = 'NA'
                        print(goals_check_res)

                        json_name = root + os.sep + run_name + "_metrics.json"
                        print (u"Writing JSON file: " + json_name)
                        # Read json file and add the goals check to metrics and write it back to file. 
                        with open(json_name, 'r') as file:
                            run_obj = json.load(file)
                        for key, val in goals_check_res.items():
                            run_obj["Metrics"][key] = val
                        with open(json_name, 'w') as file:
                            json.dump(run_obj, file, indent=4)

                        if (len(fail_on_metrics) > 0):
                            print(" | ".join(fail_on_metrics))
                            assert(False), " | ".join(fail_on_metrics)

                    else:
                        print("Scenario " + scenario + " not found in goals csv file.")

        if not args.recurse:
            break

    # # Sorting power results by level first (level 1 first, then level 2) in metrics file.
    # for root, dirs, files in os.walk(dirpath):
    #     if os.path.exists(root + os.sep + "phase_time.csv"):
    #         run_name = os.path.basename(root)
    #         csv_name = root + os.sep + run_name + "_metrics.csv"

    #         if os.path.exists(csv_name):
    #             print (u"Sorting CSV file: " + csv_name)
    #             general = collections.OrderedDict()
    #             level1 = collections.OrderedDict()
    #             level2 = collections.OrderedDict()
    #             with open(csv_name, mode ='r') as csvFile:
    #                 reader = csv.reader(csvFile)
    #                 for row in reader:
    #                     if row[0].startswith("Phase"):
    #                         if "_" in row[0]:
    #                             level2[row[0]] = row[1]
    #                         else:
    #                             level1[row[0]] = row[1]
    #                     else:
    #                         general[row[0]] = row[1]

    #             with open(csv_name, 'w') as csvfile:
    #                 writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    #                 for key in general:
    #                     writer.writerow([key, general[key]])
    #                 for key in level1:
    #                     writer.writerow([key, level1[key]])
    #                 for key in level2:
    #                     writer.writerow([key, level2[key]])

    sys.exit(0)
    
if __name__ == "__main__":
    main()
