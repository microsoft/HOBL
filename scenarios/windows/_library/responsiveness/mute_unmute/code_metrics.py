# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import csv
import os
import time

from core.parameters import Params


STATE_ATTRIBUTE = "_annoyance_metrics_state"
T0_SEMANTICS = "host_immediately_before_inputinject_rpc"
T1_SEMANTICS = "host_after_successful_visual_detector"
CLOCK_DOMAIN = "host_monotonic_perf_counter"


def _get_param(scenario, name):
    return Params.get(scenario.component, name, log=False)


def _append_row(result_dir, filename, header, row):
    os.makedirs(result_dir, exist_ok=True)
    path = os.path.join(result_dir, filename)
    exists = os.path.exists(path)
    with open(path, "a", newline="") as output:
        writer = csv.writer(output)
        if not exists:
            writer.writerow(header)
        writer.writerow(row)


def _measurement_offset(scenario, wall_time):
    daq_start_time = getattr(scenario, "daq_start_time", 0)
    return wall_time - daq_start_time if daq_start_time else 0.0


def _write_event(scenario, tag, wall_time):
    _append_row(
        scenario.result_dir,
        "annoyance_events.csv",
        ["Event", "TimeSeconds"],
        [f"annoyance:{tag}", f"{_measurement_offset(scenario, wall_time):.6f}"],
    )


def _probe_start(scenario, state, probe_name, web_phase, slot_id):
    if state.get("active_probe"):
        raise RuntimeError("An annoyance probe is already active")

    counts = state.setdefault("probe_counts", {})
    iteration = counts.get(probe_name, 0) + 1
    counts[probe_name] = iteration
    wall_time = time.time()
    state["active_probe"] = {
        "name": probe_name,
        "iteration": iteration,
        "web_phase": web_phase,
        "slot_id": slot_id,
        "start_wall": wall_time,
        "start_counter": time.perf_counter(),
    }
    _write_event(scenario, f"{probe_name}:{iteration}:begin", wall_time)


def _interaction_start(scenario, state):
    probe = state.get("active_probe")
    if not probe:
        raise RuntimeError("Cannot start an interaction outside an annoyance probe")
    if state.get("active_interaction"):
        raise RuntimeError("An annoyance interaction is already active")

    interaction_name = _get_param(scenario, "interaction_name")
    state["active_interaction"] = {
        "name": interaction_name,
        "start_wall": None,
        "start_counter": None,
        "end_wall": None,
        "end_counter": None,
        "input_action_id": "",
        "endpoint_action_id": "",
        "input_dispatch_count": 0,
    }


def _input_dispatched(scenario, action):
    state = getattr(scenario, STATE_ATTRIBUTE, None) or {}
    probe = state.get("active_probe")
    interaction = state.get("active_interaction")
    if not probe or not interaction:
        return
    if action.get("annoyance_timing_role") != "stimulus":
        return

    interaction["input_dispatch_count"] += 1
    if interaction["start_counter"] is not None:
        return

    wall_time = time.time()
    interaction["start_wall"] = wall_time
    interaction["start_counter"] = time.perf_counter()
    interaction["input_action_id"] = action.get("id", "")
    _write_event(
        scenario,
        f"{probe['name']}:{probe['iteration']}:{interaction['name']}:input_begin",
        wall_time,
    )


def _visual_detected(scenario, action):
    state = getattr(scenario, STATE_ATTRIBUTE, None) or {}
    interaction = state.get("active_interaction")
    if not interaction or interaction["start_counter"] is None:
        return
    if action.get("annoyance_timing_role") != "endpoint":
        return

    interaction["end_counter"] = time.perf_counter()
    interaction["end_wall"] = time.time()
    interaction["endpoint_action_id"] = action.get("id", "")


def _interaction_end(scenario, state):
    probe = state.get("active_probe")
    interaction = state.pop("active_interaction", None)
    if not probe or not interaction:
        raise RuntimeError("Cannot end an interaction that is not active")
    if interaction["start_counter"] is None:
        raise RuntimeError("Interaction ended before InputInject dispatch")
    bounded_settle = (
        interaction["name"] == "dismiss_quick_settings"
        and _get_param(scenario, "dismiss_check_mode") == "delay"
    )
    if interaction["end_counter"] is None and bounded_settle:
        interaction["end_counter"] = time.perf_counter()
        interaction["end_wall"] = time.time()
        interaction["endpoint_action_id"] = "bounded_settle_delay"
    elif interaction["end_counter"] is None:
        raise RuntimeError("Interaction ended before visual-state detection")

    latency_ms = (
        interaction["end_counter"] - interaction["start_counter"]
    ) * 1000.0
    if bounded_settle:
        detector = "bounded_settle_delay"
    else:
        detector = {
            "close_file_explorer": "native_check_until_not_found",
            "close_pictures_explorer": "native_check_until_not_found",
            "dismiss_start_menu": "native_check_until_not_found",
            "dismiss_quick_settings": "native_check_until_found",
            "show_less_apps": "native_check_until_not_found",
        }.get(interaction["name"], "native_check_until_found")
    _append_row(
        scenario.result_dir,
        "annoyance_latency.csv",
        [
            "Probe",
            "Iteration",
            "WebPhase",
            "SlotId",
            "Interaction",
            "StartTimeSeconds",
            "LatencyMilliseconds",
            "Status",
            "Detector",
            "T0Semantics",
            "T1Semantics",
            "ClockDomain",
            "InputActionId",
            "EndpointActionId",
            "InputDispatchCount",
        ],
        [
            probe["name"],
            probe["iteration"],
            probe["web_phase"],
            probe["slot_id"],
            interaction["name"],
            f"{_measurement_offset(scenario, interaction['start_wall']):.6f}",
            f"{latency_ms:.3f}",
            "success",
            detector,
            T0_SEMANTICS,
            T1_SEMANTICS,
            CLOCK_DOMAIN,
            interaction["input_action_id"],
            interaction["endpoint_action_id"],
            interaction["input_dispatch_count"],
        ],
    )
    _write_event(
        scenario,
        f"{probe['name']}:{probe['iteration']}:{interaction['name']}:visible",
        interaction["end_wall"],
    )


def _probe_end(scenario, state):
    if state.get("active_interaction"):
        raise RuntimeError("Cannot end a probe while an interaction is active")

    probe = state.pop("active_probe", None)
    if not probe:
        raise RuntimeError("Cannot end an annoyance probe that is not active")

    end_counter = time.perf_counter()
    end_wall = time.time()
    occupancy_ms = (end_counter - probe["start_counter"]) * 1000.0
    _append_row(
        scenario.result_dir,
        "annoyance_probes.csv",
        [
            "Probe",
            "Iteration",
            "WebPhase",
            "SlotId",
            "StartTimeSeconds",
            "OccupancyMilliseconds",
            "Status",
        ],
        [
            probe["name"],
            probe["iteration"],
            probe["web_phase"],
            probe["slot_id"],
            f"{_measurement_offset(scenario, probe['start_wall']):.6f}",
            f"{occupancy_ms:.3f}",
            "success",
        ],
    )
    _write_event(scenario, f"{probe['name']}:{probe['iteration']}:end", end_wall)


def run(scenario):
    state = getattr(scenario, STATE_ATTRIBUTE, None)
    if state is None:
        state = {}
        setattr(scenario, STATE_ATTRIBUTE, state)
    scenario._annoyance_input_dispatched = lambda action: _input_dispatched(
        scenario, action
    )
    scenario._annoyance_visual_detected = lambda action: _visual_detected(
        scenario, action
    )

    metric_action = _get_param(scenario, "metric_action")
    probe_name = _get_param(scenario, "probe_name")
    web_phase = _get_param(scenario, "web_phase") or ""
    slot_id = _get_param(scenario, "slot_id") or ""
    handlers = {
        "probe_start": lambda: _probe_start(
            scenario, state, probe_name, web_phase, slot_id
        ),
        "interaction_start": lambda: _interaction_start(scenario, state),
        "interaction_end": lambda: _interaction_end(scenario, state),
        "probe_end": lambda: _probe_end(scenario, state),
    }
    if metric_action not in handlers:
        raise ValueError(f"Unknown annoyance metric action: {metric_action}")
    handlers[metric_action]()
