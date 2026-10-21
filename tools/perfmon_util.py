# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import os
import re
import pandas as pd
from enum import Enum
import fnmatch
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import time
import datetime
import csv

def parse_luid_engine(s):
    m = re.search(
        r"pid_([0-9]+)_luid_0x([0-9A-Fa-f]+)_0x([0-9A-Fa-f]+).*?engtype_([A-Za-z0-9]+)",
        s
    )

    if not m:
        return ("unknown", "unknown_unknown", "unknown")

    pid     = int(m.group(1))
    high    = int(m.group(2), 16)
    low     = int(m.group(3), 16)
    engtype = m.group(4)

    return (pid, f"0x{high:08X}_0x{low:08X}", engtype)

def parse_process(s):
    m = re.search(r"Process\((.*)\)\\", s)

    if not m:
        return "unknown"

    return m.group(1)

def csv_to_map(csvtext):
    reader = csv.reader(csvtext.split("\n"))
    out = {}

    for row in reader:
        # Expected format: luid,adapter_name,adapter_type
        if len(row) != 3:
            continue

        key = row[0].strip()
        val = row[2].strip() or row[1].strip()

        out[key] = val

    return out

def limit_n(n):
    if 100 < n < 101:
        return 100.0
    if n < 1:
        return float(round(n))
    return n

def counter_match(s, counters):
    for counter in counters:
        ok = fnmatch.fnmatch(s, f"*{counter}")
        if ok:
            return True
    return False

def parse_float_util(s):
    s = s.replace('"', '').strip()
    return float(s) if s != "" else 0.0

class CounterType(Enum):
    GPU_ENGINE  = 1
    PROCESS_ID  = 2
    PROCESS_CPU = 3
    PROCESS_MEM = 4
    OTHER       = 5

class Tool(Scenario):
    '''
    Trace specified performance counters that report utilization.

    '''
    module = __module__.split('.')[-1]

    # Set default parameters
    Params.setDefault(module, 'include_processes',   '0', desc="Include counters for individual processes", valOptions=["0", "1"])
    Params.setDefault(module, 'process_id_counter',  '\\Process(*)\\ID Process', desc="Process ID counter to use (per process)")
    Params.setDefault(module, 'process_cpu_counter', '\\Process(*)\\% Processor Time', desc="Process CPU counter to use (per process)")
    Params.setDefault(module, 'process_mem_counter', '\\Process(*)\\Working Set', desc="Process memory counter to use (per process)")
    Params.setDefault(module, 'cpu_counter',         '\\Processor(_Total)\\% Processor Time', desc="CPU counter to use")
    Params.setDefault(module, 'memory_counter',      '\\Memory\\Available Bytes', desc="Memory counter to use")
    Params.setDefault(module, 'gpu_counter',         '\\GPU Engine(*engtype_3D)\\Utilization Percentage', desc="GPU counter to use (per process, per instance)")
    Params.setDefault(module, 'npu_counter',         '\\GPU Engine(*engtype_Compute)\\Utilization Percentage', desc="NPU counter to use (per process, per instance)")

    # Get parameters
    process_id_counter  = Params.get(module, 'process_id_counter')
    process_cpu_counter = Params.get(module, 'process_cpu_counter')
    process_mem_counter = Params.get(module, 'process_mem_counter')
    cpu_counter         = Params.get(module, 'cpu_counter')
    memory_counter      = Params.get(module, 'memory_counter')
    gpu_counter         = Params.get(module, 'gpu_counter')
    npu_counter         = Params.get(module, 'npu_counter')
    include_processes   = Params.get(module, 'include_processes') != "0"

    counters = " ".join(f'"{c}"' for c in [cpu_counter, memory_counter, process_id_counter, process_cpu_counter, process_mem_counter, gpu_counter, npu_counter])

    def initCallback(self, scenario):
        # Initialization code

        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario

        blg_filename   = "perfmon_util.blg"
        csv_filename   = "perfmon_util.csv"
        trace_filename = "perfmon_util.trace"

        self.dut_output_path = os.path.join(self.scenario.dut_data_path, f"{self.module}")
        self.blg_path_dut = os.path.join(self.dut_output_path, blg_filename)
        self.csv_path_dut = os.path.join(self.dut_output_path, csv_filename)

        self.result_output_path = os.path.join(self.scenario.result_dir, f"{self.module}")
        self.blg_path_result   = os.path.join(self.result_output_path, blg_filename)
        self.csv_path_result   = os.path.join(self.result_output_path, csv_filename)
        self.trace_path_result = os.path.join(self.result_output_path, trace_filename)

        luid_to_name_exe           = "map_luid_to_name.exe"
        self.luid_to_name_map_path = os.path.join(self.scenario.dut_exec_path, luid_to_name_exe)

        if self._call(["cmd.exe", "/c echo %PROCESSOR_ARCHITECTURE%"]).strip().lower() == "arm64":
            arch = "arm64"
        else:
            arch = "x64"

        self.scenario._upload(f"utilities\\open_source\\map_luid_to_name\\{arch}\\{luid_to_name_exe}", self.scenario.dut_exec_path)

        self.cleanup()

    def testBeginCallback(self):
        self.total_mem_bytes = int(self._call(["pwsh.exe", "-Command (Get-CimInstance -ClassName Win32_ComputerSystem).TotalPhysicalMemory"]).strip())
        self.num_logical_cores = int(self._call(["pwsh.exe", "-Command (Get-CimInstance Win32_Processor).NumberOfLogicalProcessors"]).strip())
        self.luid_to_name_map = csv_to_map(self._call([self.luid_to_name_map_path], log_output=False))
        self.pid_map = {}
        self._remote_make_dir(self.dut_output_path)

        self._call(["typeperf.exe", f"{self.counters} -si 1 -f bin -o {self.blg_path_dut} -sc 0 -y"], blocking=False)

    def testEndCallback(self):
        self.cleanup()
        self._call(["relog.exe", f"{self.blg_path_dut} -c {self.counters} -f csv -o {self.csv_path_dut} -y"], log_output=False)

    def cleanup(self):
        self._kill("typeperf.exe", timeout=120)

    def get_col(self, k, truncate):
        name  = self.luid_to_name_map.get(k[1], k[1])
        parts = []

        if k[0]:
            pid_name = k[0]
            if isinstance(pid_name, int):
                pid_name = self.pid_map.get(k[0])
                parts.append(pid_name or f"Process-{k[0]}")
            else:
                parts.append(pid_name)

        parts.append(name)

        if not truncate:
            parts.append(k[2])

        return f"{' '.join(map(str, parts))} (%)"

    def dataReadyCallback(self):
        first_line = True
        remaining_order = []
        proc_cols = []
        luid_util_map, col_to_luid = {}, {}
        df = None

        # os.makedirs(os.path.join(self.scenario.result_dir, f"{self.module}"), exist_ok=True) # make dir for storing results

        with open(self.csv_path_result, "r") as f:
            for line in f:
                if "Time" in line:
                    _, _, _, *remaining_entries = line.split(",")

                    for entry in remaining_entries:
                        entry = entry.replace('"', '').strip()

                        if counter_match(entry, [self.gpu_counter, self.npu_counter]):
                            luid = parse_luid_engine(entry)
                            luid_util_map.setdefault(luid, 0.0)
                            luid_util_map.setdefault((None,) + luid[1:], 0.0)
                            remaining_order.append((CounterType.GPU_ENGINE, luid))
                        elif counter_match(entry, [self.process_id_counter]):
                            remaining_order.append((CounterType.PROCESS_ID, parse_process(entry)))
                        elif counter_match(entry, [self.process_cpu_counter]):
                            luid = (parse_process(entry), "CPU", None)
                            luid_util_map.setdefault(luid, 0.0)
                            remaining_order.append((CounterType.PROCESS_CPU, luid))
                        elif counter_match(entry, [self.process_mem_counter]):
                            luid = (parse_process(entry), "Memory", None)
                            luid_util_map.setdefault(luid, 0.0)
                            remaining_order.append((CounterType.PROCESS_MEM, luid))
                        else:
                            remaining_order.append((CounterType.OTHER, None))

                    columns = ["Timestamp", "CPU (%)", "Memory (%)"]
                    for k in luid_util_map:
                        col = self.get_col(k, False)
                        if k[0]:
                            proc_cols.append(col)
                        col_to_luid[col] = k
                        columns.append(col)
                    df = pd.DataFrame(columns=columns)

                    continue

                timestamp, cpu_util, mem_util, *remaining_utils = line.split(",")

                luid_util_map_i = dict.fromkeys(luid_util_map, 0.0)
                for i, util in enumerate(remaining_utils):
                    if remaining_order[i][0] == CounterType.GPU_ENGINE:
                        gpu_util = util.replace('"', '').strip()
                        gpu_util = float(gpu_util) if gpu_util != "" else 0.0

                        luid = remaining_order[i][1]
                        luid_util_map_i[luid] += gpu_util
                        luid_util_map_i[(None,) + luid[1:]] += gpu_util
                    elif remaining_order[i][0] == CounterType.PROCESS_ID:
                        process_util = util.replace('"', '').strip()
                        process_util = int(process_util) if process_util != "" else None
                        self.pid_map[process_util] = remaining_order[i][1]
                    elif remaining_order[i][0] == CounterType.PROCESS_CPU:
                        luid_util_map_i[remaining_order[i][1]] = parse_float_util(util) / self.num_logical_cores
                    elif remaining_order[i][0] == CounterType.PROCESS_MEM:
                        luid_util_map_i[remaining_order[i][1]] = 100.0 * parse_float_util(util) / self.total_mem_bytes

                for k in luid_util_map:
                    luid_util_map[k] += luid_util_map_i[k]

                # Convert timestamp in the format "MM/DD/YYYY HH:MM:SS.MS" to seconds since epoch
                dt = datetime.datetime.strptime(timestamp.strip('"'), '%m/%d/%Y %H:%M:%S.%f')
                timestamp = time.mktime(dt.timetuple()) * 1000.0 + dt.microsecond / 1000.0

                if first_line:
                    first_line = False
                    # Use this as the starting time
                    self.start_time = float(timestamp) / 1000.0
                timestamp = float(timestamp) / 1000.0 - self.start_time

                # Convert available memory to used memory percentage
                mem_util = mem_util.replace('"', '').strip()
                mem_util = float(mem_util) if mem_util != "" else 0.0
                mem_util = 100.0 * (1.0 - (mem_util / self.total_mem_bytes))

                cpu_util = cpu_util.replace('"', '').strip()
                cpu_util = float(cpu_util) if cpu_util != "" else 0.0

                row = [timestamp, cpu_util, mem_util]
                for k in luid_util_map_i:
                    row.append(limit_n(luid_util_map_i[k]))
                df.loc[len(df)] = row

        try:
            os.remove(self.blg_path_result)
        except Exception as e:
            logging.error(f"Error deleting file: {e}")

        if df is None or len(df) <= 0:
            return

        cols_to_drop = list(df.columns[3:][df.iloc[:, 3:].eq(0).all()])
        df = df.drop(columns=cols_to_drop + ([] if self.include_processes else proc_cols))

        ordered_cols = list(df.columns[:3]) + sorted(
            df.columns[3:],
            key=lambda c: col_to_luid[c][0] is not None
        )
        df = df[ordered_cols]

        pid_luid_counts = {}
        for col in df.columns[3:]:
            k = col_to_luid[col]
            pid_luid = (k[0], k[1])
            pid_luid_counts[pid_luid] = pid_luid_counts.get(pid_luid, 0) + 1

        rename_cols = {}
        for col in df.columns[3:]:
            k = col_to_luid[col]
            pid_luid = (k[0], k[1])
            rename_cols[col] = self.get_col(k, pid_luid_counts[pid_luid] == 1)
        df = df.rename(columns=rename_cols)

        # Merge duplicate process columns
        df = df.groupby(level=0, axis=1, sort=False).sum()

        rounding_dict = {df.columns[0]: 1}
        for col in df.columns[1:]:
            rounding_dict[col] = 2
        df = df.round(rounding_dict)

        df.iloc[:, 1:].mean().round(3).reset_index().to_csv(
            self.csv_path_result, header=False, index=False
        )

        df.to_csv(self.trace_path_result, index=False)
