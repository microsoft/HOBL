import csv
import os
import shutil
import sys
import time

sys.path.insert(0, r"C:\HOBL")
from core import app_scenario
from core import call_rpc
from scenarios.windows._library.responsiveness.mute_unmute import code_metrics

RESULT = r"C:\HOBL\latency_hook_test"
shutil.rmtree(RESULT, ignore_errors=True)
os.makedirs(RESULT)

params = {
    "metric_action": "probe_start",
    "probe_name": "synthetic_probe",
    "web_phase": "validation",
    "slot_id": "hook_test",
    "interaction_name": "synthetic_interaction",
    "dismiss_check_mode": "image",
}
code_metrics._get_param = lambda scenario, name: params.get(name, "")


class FakeScenario:
    pass


scenario = FakeScenario()
scenario.result_dir = RESULT
scenario.daq_start_time = time.time() - 1
scenario.component = "synthetic"
scenario.log_scenario_events = False
scenario.captures = {"cap": object()}
scenario.default_scale = [1.0]
scenario.default_click_time = 100
scenario.typing_delay = 100
scenario.dut_coord_scaler = 1.0
scenario.current_screen = 0
scenario.dut_ip = "127.0.0.1"
scenario.rpc_port = 8000
scenario.scenario_accumulated_time = 0.0
scenario.daq_accumulated_time = 0.0
scenario._get_screen_size = lambda screen: (1000, 1000)
scenario._sleep_by = lambda seconds: None
scenario._capture_screen = lambda *args, **kwargs: (time.sleep(0.05), object())[1]
scenario._check_by_template = lambda *args, **kwargs: False

original_plugin_call = call_rpc.plugin_call
call_rpc.plugin_call = lambda *args, **kwargs: '{"result":"ok"}'
try:
    code_metrics.run(scenario)
    params["metric_action"] = "interaction_start"
    code_metrics.run(scenario)

    click = {
        "id": "INPUT001",
        "type": "Click Coord",
        "description": "Synthetic input",
        "enabled": True,
        "x": "0.5",
        "y": "0.5",
        "delay": "0",
        "annoyance_timing_role": "stimulus",
    }
    assert app_scenario.Scenario.process_action(scenario, click) == 0

    check = {
        "id": "ENDPOINT001",
        "type": "Check Until Not Found",
        "description": "Synthetic visible endpoint",
        "enabled": True,
        "capture_id": "cap",
        "file_name": ["template.png"],
        "x": "0",
        "y": "0",
        "w": "1",
        "h": "1",
        "timeout": "1",
        "delay": "0",
        "match_threshold": "",
        "annoyance_timing_role": "endpoint",
    }
    assert app_scenario.Scenario.process_action(scenario, check) == 0

    time.sleep(0.20)
    params["metric_action"] = "interaction_end"
    code_metrics.run(scenario)

    params["interaction_name"] = "dismiss_quick_settings"
    params["dismiss_check_mode"] = "delay"
    params["metric_action"] = "interaction_start"
    code_metrics.run(scenario)
    assert app_scenario.Scenario.process_action(scenario, click) == 0
    time.sleep(0.05)
    params["metric_action"] = "interaction_end"
    code_metrics.run(scenario)
finally:
    call_rpc.plugin_call = original_plugin_call

with open(os.path.join(RESULT, "annoyance_latency.csv"), newline="") as source:
    rows = list(csv.DictReader(source))
row = rows[0]
latency = float(row["LatencyMilliseconds"])
assert 30 <= latency <= 150, latency
assert row["InputActionId"] == "INPUT001", row
assert row["EndpointActionId"] == "ENDPOINT001", row
assert row["InputDispatchCount"] == "1", row
assert row["T0Semantics"] == "host_immediately_before_inputinject_rpc", row
assert row["T1Semantics"] == "host_after_successful_visual_detector", row
bounded = rows[1]
bounded_latency = float(bounded["LatencyMilliseconds"])
assert 30 <= bounded_latency <= 150, bounded_latency
assert bounded["Detector"] == "bounded_settle_delay", bounded
assert bounded["EndpointActionId"] == "bounded_settle_delay", bounded
print(
    f"Latency hook validation PASS: detector={latency:.3f} ms "
    f"bounded={bounded_latency:.3f} ms"
)
shutil.rmtree(RESULT)
