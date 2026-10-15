# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import csv
import logging
import os
import statistics
import time

from core.app_scenario import Scenario
from core.parameters import Params


MEMORY_COLUMNS = (
    "PhysicalMemoryUtilizationPercent",
    "PhysicalMemoryUsedBytes",
    "PhysicalMemoryTotalBytes",
    "CommittedBytes",
    "CommitLimitBytes",
    "PercentCommittedBytesInUse",
    "AvailableBytes",
)
METADATA_COLUMNS = {"Sample", "TimestampUtc", "Elapsed_s", *MEMORY_COLUMNS}
POWER_GROUPS = {
    "Cpu": ("cpu",),
    "Gpu": ("gpu",),
    "Npu": ("npu",),
    "Memory": ("memory",),
    "Display": ("display",),
    "WiFi": ("wifi",),
    "Storage": ("storage",),
}


def _normalized_channel(name):
    normalized = name.lower().replace(" ", "_")
    return normalized[:-3] if normalized.endswith("_mw") else normalized


def _read_samples(path):
    with open(path, newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        channel_names = [name for name in (reader.fieldnames or []) if name not in METADATA_COLUMNS]
        samples = []
        for row in reader:
            try:
                elapsed = float(row["Elapsed_s"])
            except (KeyError, TypeError, ValueError):
                continue
            values = {}
            for channel in channel_names:
                try:
                    values[channel] = max(0.0, float(row[channel])) / 1000.0
                except (TypeError, ValueError):
                    values[channel] = 0.0
            memory = {}
            for column in MEMORY_COLUMNS:
                try:
                    memory[column] = max(0.0, float(row[column]))
                except (KeyError, TypeError, ValueError):
                    memory[column] = 0.0
            samples.append({
                "timestamp": row.get("TimestampUtc", ""),
                "elapsed": elapsed,
                "memory": memory,
                "values": values,
            })
    return samples, channel_names


def _write_memory_trace(path, samples, alignment_offset):
    header = ["Sample", "TimestampUtc", "SamplerElapsedSeconds", "DAQTimeSeconds"]
    header.extend(MEMORY_COLUMNS)
    with open(path, "w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(header)
        for index, sample in enumerate(samples, start=1):
            row = [
                index,
                sample["timestamp"],
                f'{sample["elapsed"]:.3f}',
                f'{sample["elapsed"] - alignment_offset:.3f}',
            ]
            row.extend(f'{sample["memory"][column]:.3f}' for column in MEMORY_COLUMNS)
            writer.writerow(row)


def _find_system_channel(channel_names):
    normalized = {name: _normalized_channel(name) for name in channel_names}
    for name, channel in normalized.items():
        if channel in {"sys", "emi_sys"} or channel.endswith("_emi_sys"):
            return name
    for name, channel in normalized.items():
        if "system" in channel and "total" in channel:
            return name
    return None


def _group_channels(channel_names):
    grouped = {}
    for group, tokens in POWER_GROUPS.items():
        grouped[group] = [
            name for name in channel_names
            if any(token in _normalized_channel(name) for token in tokens)
        ]
    return grouped


def _sample_power(sample, system_channel, grouped_channels):
    values = sample["values"]
    power = {"System": values.get(system_channel, 0.0)}
    for group, channels in grouped_channels.items():
        power[group] = sum(values.get(channel, 0.0) for channel in channels)
    return power


def _aggregate_window(samples, start, end, system_channel, grouped_channels):
    duration = max(0.0, end - start)
    energy = {name: 0.0 for name in ("System", *POWER_GROUPS)}
    covered_seconds = 0.0
    sample_count = 0
    previous_elapsed = 0.0

    for sample in samples:
        interval_start = previous_elapsed
        interval_end = sample["elapsed"]
        previous_elapsed = interval_end
        overlap = max(0.0, min(end, interval_end) - max(start, interval_start))
        if overlap <= 0:
            continue
        sample_count += 1
        covered_seconds += overlap
        power = _sample_power(sample, system_channel, grouped_channels)
        for name in energy:
            energy[name] += power[name] * overlap

    average = {
        name: (value / covered_seconds if covered_seconds > 0 else 0.0)
        for name, value in energy.items()
    }
    coverage = 100.0 * covered_seconds / duration if duration > 0 else 0.0
    return {
        "duration": duration,
        "covered_seconds": covered_seconds,
        "coverage": min(100.0, coverage),
        "sample_count": sample_count,
        "average": average,
        "energy": energy,
    }


def _read_event_windows(path):
    probes = {}
    interactions = {}
    with open(path, newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            label = row.get("Event", "")
            if not label.startswith("annoyance:"):
                continue
            try:
                timestamp = float(row["TimeSeconds"])
            except (KeyError, TypeError, ValueError):
                continue
            parts = label.split(":")
            if len(parts) == 4:
                _, probe, iteration, state = parts
                window = probes.setdefault((probe, iteration), {})
                window[state] = timestamp
            elif len(parts) == 5:
                _, probe, iteration, interaction, state = parts
                window = interactions.setdefault((probe, iteration, interaction), {})
                window[state] = timestamp
    return probes, interactions


def _read_daq_stop(path):
    with open(path, newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            if row.get("phase") == "DAQ: DAQStopTime":
                return float(row["time"])
    return 0.0


def _read_report_context(path, include_interaction=False):
    context = {}
    if not os.path.exists(path):
        return context
    with open(path, newline="", encoding="utf-8-sig") as source:
        for row in csv.DictReader(source):
            key = [row.get("Probe", ""), row.get("Iteration", "")]
            if include_interaction:
                key.append(row.get("Interaction", ""))
            context[tuple(key)] = {
                "web_phase": row.get("WebPhase", ""),
                "slot_id": row.get("SlotId", ""),
            }
    return context


def _write_scope_trace(path, records):
    power_names = ("System", *POWER_GROUPS)
    header = [
        "Scope",
        "WebPhase",
        "SlotId",
        "Probe",
        "Iteration",
        "Interaction",
        "StartTimeSeconds",
        "EndTimeSeconds",
        "DurationSeconds",
        "CoveredSeconds",
        "CoveragePercent",
        "SampleCount",
    ]
    header.extend(f"Average{name}PowerW" for name in power_names)
    header.extend(f"{name}EnergyJ" for name in power_names)

    with open(path, "w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(header)
        for record in records:
            aggregate = record["aggregate"]
            row = [
                record["scope"],
                record.get("web_phase", ""),
                record.get("slot_id", ""),
                record.get("probe", ""),
                record.get("iteration", ""),
                record.get("interaction", ""),
                f"{record['start']:.3f}",
                f"{record['end']:.3f}",
                f"{aggregate['duration']:.3f}",
                f"{aggregate['covered_seconds']:.3f}",
                f"{aggregate['coverage']:.1f}",
                aggregate["sample_count"],
            ]
            row.extend(f"{aggregate['average'][name]:.3f}" for name in power_names)
            row.extend(f"{aggregate['energy'][name]:.3f}" for name in power_names)
            writer.writerow(row)


def _summary_rows(records, resolution, alignment_offset):
    rows = [
        ("Annoyance Power Sample Interval (s)", resolution),
        ("Annoyance Power Sampler To DAQ Offset (s)", alignment_offset),
    ]
    for record in records:
        if record["scope"] == "WholeRun":
            label = "Whole Run"
        else:
            context = " ".join(
                value for value in (record.get("web_phase", ""), record.get("slot_id", ""))
                if value
            )
            label = f"{context} {record['probe']} Iteration {record['iteration']}".strip()
        aggregate = record["aggregate"]
        rows.extend([
            (f"Annoyance {label} Average System Power (W)", aggregate["average"]["System"]),
            (f"Annoyance {label} System Energy (J)", aggregate["energy"]["System"]),
            (f"Annoyance {label} Power Coverage (%)", aggregate["coverage"]),
            (f"Annoyance {label} Average CPU Power (W)", aggregate["average"]["Cpu"]),
            (f"Annoyance {label} Average GPU Power (W)", aggregate["average"]["Gpu"]),
        ])
    return rows


class Tool(Scenario):
    module = __module__.split(".")[-1]
    Params.setDefault(module, "interval_seconds", "1")
    Params.setDefault(module, "start_timeout_seconds", "10")
    Params.setDefault(module, "stop_timeout_seconds", "15")

    interval_seconds = float(Params.get(module, "interval_seconds"))
    start_timeout_seconds = float(Params.get(module, "start_timeout_seconds"))
    stop_timeout_seconds = float(Params.get(module, "stop_timeout_seconds"))

    def initCallback(self, scenario):
        self.scenario = scenario
        self.conn_timeout = False
        self.started = False
        self.test_name = self.scenario.testname
        self.script_name = "annoyance_power_sampler.ps1"
        self.script_path = os.path.join(self.scenario.dut_exec_path, self.script_name)
        self.raw_name = f"{self.test_name}_annoyance_power.trace"
        self.raw_path_dut = os.path.join(self.scenario.dut_data_path, self.raw_name)
        self.stop_path_dut = self.raw_path_dut + ".stop"
        self.started_path_dut = self.raw_path_dut + ".started"
        self.done_path_dut = self.raw_path_dut + ".done"
        self.raw_path_result = os.path.join(self.scenario.result_dir, self.raw_name)

        self.scenario._upload(
            os.path.join("utilities", "open_source", self.script_name),
            self.scenario.dut_exec_path,
            check_modified=True,
        )
        self.cleanup()
        for path in (self.raw_path_dut, self.stop_path_dut, self.started_path_dut, self.done_path_dut):
            self._call(["cmd.exe", f'/c del /q "{path}" 2>nul'], expected_exit_code="")

    def testBeginCallback(self):
        args = (
            f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{self.script_path}" '
            f'-OutFile "{self.raw_path_dut}" -StopFile "{self.stop_path_dut}" '
            f'-StartedFile "{self.started_path_dut}" -IntervalSeconds {self.interval_seconds}'
        )
        self._call(["powershell.exe", args], blocking=False, expected_exit_code="")

        deadline = time.time() + self.start_timeout_seconds
        while time.time() < deadline:
            before = time.time()
            exists = self._check_remote_file_exists(self.started_path_dut, in_exec_path=False)
            after = time.time()
            if exists:
                self.sampler_start_host = (before + after) / 2.0
                self.started = True
                logging.info("Annoyance power sampling started.")
                return
            time.sleep(0.1)
        raise RuntimeError("Annoyance power sampler did not start")

    def testEndCallback(self):
        if not self.started or self.conn_timeout:
            return
        self._call(["cmd.exe", f'/c echo stop>"{self.stop_path_dut}"'], expected_exit_code="")
        deadline = time.time() + self.stop_timeout_seconds
        while time.time() < deadline:
            if self._check_remote_file_exists(self.done_path_dut, in_exec_path=False):
                for path in (self.stop_path_dut, self.started_path_dut, self.done_path_dut):
                    self._call(["cmd.exe", f'/c del /q "{path}" 2>nul'], expected_exit_code="")
                logging.info("Annoyance power sampling stopped.")
                return
            time.sleep(0.1)
        self.cleanup()
        raise RuntimeError("Annoyance power sampler did not stop cleanly")

    def testTimeoutCallback(self):
        self.conn_timeout = True

    def cleanup(self):
        command = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*-File*annoyance_power_sampler.ps1*' } | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        self._call(["powershell.exe", f'-NoProfile -Command "{command}"'], expected_exit_code="")

    def dataReadyCallback(self):
        if not os.path.exists(self.raw_path_result):
            logging.warning("Annoyance power trace was not copied back.")
            return

        samples, channel_names = _read_samples(self.raw_path_result)
        if not samples:
            logging.warning("Annoyance power trace contains no usable samples.")
            return
        system_channel = _find_system_channel(channel_names)
        if system_channel is None:
            logging.warning("Annoyance power trace does not contain a system-total channel.")
            return

        grouped_channels = _group_channels(channel_names)
        event_path = os.path.join(self.scenario.result_dir, "annoyance_events.csv")
        probe_report_path = os.path.join(self.scenario.result_dir, "annoyance_probes.csv")
        interaction_report_path = os.path.join(self.scenario.result_dir, "annoyance_latency.csv")
        phase_path = os.path.join(self.scenario.result_dir, "phase_time.csv")
        if not os.path.exists(event_path) or not os.path.exists(phase_path):
            logging.warning("Annoyance event or phase timing data is missing.")
            return

        alignment_offset = self.scenario.daq_start_time - self.sampler_start_host
        daq_stop = _read_daq_stop(phase_path)
        probe_windows, interaction_windows = _read_event_windows(event_path)
        probe_context = _read_report_context(probe_report_path)
        interaction_context = _read_report_context(
            interaction_report_path, include_interaction=True
        )
        probe_records = []
        interaction_records = []

        whole_start = alignment_offset
        whole_end = alignment_offset + daq_stop
        probe_records.append({
            "scope": "WholeRun",
            "start": 0.0,
            "end": daq_stop,
            "aggregate": _aggregate_window(
                samples, whole_start, whole_end, system_channel, grouped_channels
            ),
        })

        for (probe, iteration), window in sorted(probe_windows.items()):
            if "begin" not in window or "end" not in window:
                continue
            start = window["begin"]
            end = window["end"]
            context = probe_context.get((probe, iteration), {})
            probe_records.append({
                "scope": "Probe",
                "web_phase": context.get("web_phase", ""),
                "slot_id": context.get("slot_id", ""),
                "probe": probe,
                "iteration": iteration,
                "start": start,
                "end": end,
                "aggregate": _aggregate_window(
                    samples,
                    alignment_offset + start,
                    alignment_offset + end,
                    system_channel,
                    grouped_channels,
                ),
            })

        for (probe, iteration, interaction), window in sorted(interaction_windows.items()):
            if "input_begin" not in window or "visible" not in window:
                continue
            start = window["input_begin"]
            end = window["visible"]
            context = interaction_context.get((probe, iteration, interaction), {})
            interaction_records.append({
                "scope": "Interaction",
                "web_phase": context.get("web_phase", ""),
                "slot_id": context.get("slot_id", ""),
                "probe": probe,
                "iteration": iteration,
                "interaction": interaction,
                "start": start,
                "end": end,
                "aggregate": _aggregate_window(
                    samples,
                    alignment_offset + start,
                    alignment_offset + end,
                    system_channel,
                    grouped_channels,
                ),
            })

        intervals = [
            samples[index]["elapsed"] - samples[index - 1]["elapsed"]
            for index in range(1, len(samples))
            if samples[index]["elapsed"] > samples[index - 1]["elapsed"]
        ]
        resolution = statistics.median(intervals) if intervals else self.interval_seconds
        prefix = os.path.join(self.scenario.result_dir, self.test_name)
        _write_memory_trace(
            prefix + "_annoyance_memory.csv", samples, alignment_offset
        )
        _write_scope_trace(prefix + "_annoyance_probe_power.trace", probe_records)
        _write_scope_trace(prefix + "_annoyance_interaction_power.trace", interaction_records)

        with open(prefix + "_annoyance_power_data.csv", "w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            for name, value in _summary_rows(probe_records, resolution, alignment_offset):
                writer.writerow([name, f"{value:.3f}"])
        logging.info(
            "Annoyance power reporting complete: %d samples, %d probes, %d interactions.",
            len(samples),
            max(0, len(probe_records) - 1),
            len(interaction_records),
        )