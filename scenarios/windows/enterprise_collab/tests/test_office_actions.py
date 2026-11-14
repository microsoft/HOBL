# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch
import zipfile


ROOT = Path(__file__).parents[1]


def load_helper():
    params = types.ModuleType("core.parameters")
    params.Params = Mock()
    spec = importlib.util.spec_from_file_location("office_ui", ROOT / "office_ui.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"core.parameters": params}):
        spec.loader.exec_module(module)
    return module


class OfficeActionsTests(unittest.TestCase):
    def setUp(self):
        self.module = load_helper()
        self.values = {
            "office_extended_actions": "1", "platform": "Windows",
            "simple_office_launch": "1",
            "userprofile": r"D:\Users\Lab User", "typing_delay": "50",
            "onedrive_path": r"E:\Synced documents",
        }
        self.module.Params.get.side_effect = lambda section, key: self.values[key]
        self.scenario = Mock(dut_exec_path=r"D:\hobl bin", dut_data_path=r"D:\hobl data")

    def test_disabled_actions_do_not_touch_the_dut(self):
        self.values["office_extended_actions"] = "0"
        for action in ("prepare", "run_word", "run_excel", "run_powerpoint"):
            getattr(self.module, action)(self.scenario)
        self.assertEqual(self.scenario.mock_calls, [])

    def test_invalid_gate_fails_explicitly(self):
        self.values["office_extended_actions"] = "yes"
        with self.assertRaisesRegex(ValueError, "must be 0 or 1"):
            self.module.prepare(self.scenario)
        self.scenario._upload.assert_not_called()

    def test_global_gate_does_not_enable_enterprise_actions(self):
        self.module.Params.get.side_effect = lambda section, key: (
            "0" if section == "enterprise_collab" and key == "office_extended_actions"
            else self.values[key]
        )
        self.module.prepare(self.scenario)
        self.assertEqual(self.scenario.mock_calls, [])

    def test_enabled_actions_require_the_office_lifecycle(self):
        self.values["simple_office_launch"] = "0"
        with self.assertRaisesRegex(ValueError, "simple_office_launch=1"):
            self.module.validate_configuration()
        self.values["office_extended_actions"] = "0"
        self.module.validate_configuration()

    def test_w365_uses_configured_onedrive_root(self):
        self.values["platform"] = "W365"
        self.assertEqual(self.module._docs(), r"E:\Synced documents\abl_docs")

    def test_paths_with_spaces_and_apostrophes_are_encoded(self):
        self.scenario.dut_exec_path = r"D:\lab's tools"
        self.scenario._call.return_value = '{"verified":true}'
        self.module._inspect(self.scenario, "Pdf", r"E:\report's output.pdf")
        command = self.scenario._call.call_args.args[0]
        decoded = base64.b64decode(command[1].split()[-1]).decode("utf-16-le")
        self.assertIn(r"D:\lab''s tools\enterprise_collab_resources\office_output.ps1", decoded)
        self.assertIn(r"E:\report''s output.pdf", decoded)
        self.assertFalse(self.scenario._call.call_args.kwargs["system"])

    def test_excel_creates_fields_and_validates_against_snapshot(self):
        with patch.object(self.module, "_inspect", return_value={"pivots": 1}) as inspect, \
                patch.object(self.module, "_app"), patch.object(self.module, "_element") as element:
            element.return_value.is_selected.return_value = False
            self.module.run_excel(self.scenario)
        selectors = [call.args[1] for call in element.call_args_list]
        self.assertIn("//CheckBox[@Name='Category']", selectors)
        self.assertIn("//CheckBox[@Name='Cost']", selectors)
        self.assertEqual(inspect.call_args.args[-1], {"pivots": 1})
        self.assertEqual(element.return_value.click.call_count, 3)
        names = [call.args[0] for call in self.scenario._record_phase_time.call_args_list]
        self.assertEqual(names, ["prod: sort_excel", "prod: create_excel_pivot"])

    def test_powerpoint_inserts_both_assets_before_exporting(self):
        with patch.object(self.module, "_inspect", return_value={"pictures": 1, "videos": 0}) as inspect, \
                patch.object(self.module, "_app"), patch.object(self.module, "_element") as element, \
                patch.object(self.module, "_export_pdf") as export:
            self.module.run_powerpoint(self.scenario)
        element.return_value.send_keys.assert_any_call(r"D:\Users\Lab User\OneDrive\abl_docs\Manarola2.png")
        element.return_value.send_keys.assert_any_call(r"D:\Users\Lab User\OneDrive\abl_docs\ppt.mp4")
        self.assertEqual(inspect.call_args.args[-1], {"pictures": 1, "videos": 0})
        export.assert_called_once()
        names = [call.args[0] for call in self.scenario._record_phase_time.call_args_list]
        self.assertEqual(names, ["prod: insert_powerpoint_media", "prod: export_powerpoint_pdf"])

    def test_validation_failure_is_not_reported_as_completed_phase(self):
        with patch.object(self.module, "_app"), \
                patch.object(self.module, "_export_pdf", side_effect=RuntimeError("invalid PDF")):
            with self.assertRaisesRegex(RuntimeError, "invalid PDF"):
                self.module.run_word(self.scenario)
        self.scenario._record_phase_time.assert_not_called()

    def test_enterprise_actions_are_gated_between_office_open_and_close(self):
        def strict_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key: " + key)
                result[key] = value
            return result

        actions = json.loads((ROOT / "enterprise_collab.json").read_text(), object_pairs_hook=strict_pairs)
        setup = next(action for action in actions if action["type"] == "Setup")
        setup_office = next(action for action in setup["children"] if action["id"] == "19MUF2P")
        self.assertTrue(setup_office["children"][0]["include_path"].endswith("prod_setup"))
        self.assertEqual(setup_office["children"][1]["file_name"], ["code_OFFICE_PREPARE.py"])
        run = next(action for action in actions if action["type"] == "Run Test")
        office = next(action for action in run["children"] if action["id"] == "19MUFJ9")
        self.assertTrue(office["children"][0]["include_path"].endswith("prod_open"))
        self.assertTrue(office["children"][3]["include_path"].endswith("prod_close"))
        gate = office["children"][1]
        self.assertEqual(gate["left_term"], "[enterprise_collab:office_extended_actions]")
        self.assertEqual(gate["right_term"], "1")
        codes = [child["file_name"][0] for child in gate["children"] if child["type"] == "Code"]
        self.assertEqual(codes, ["code_WORD_PDF.py", "code_EXCEL_SORT_PIVOT.py", "code_POWERPOINT_MEDIA_PDF.py"])
        for code in codes + ["code_OFFICE_PREPARE.py"]:
            self.assertTrue((ROOT / code).is_file())
        for index, app in enumerate(("word", "excel", "powerpoint")):
            self.assertTrue(gate["children"][index * 2]["include_path"].endswith("prod_" + app + "_switchto"))


class OutputValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hobl-office-test-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "output"

    def validate(self, kind, before=None):
        command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-File",
                   str(ROOT / "resources" / "office_output.ps1"), "-Kind", kind, "-Path", str(self.path)]
        if before is not None:
            command.extend(["-Before", json.dumps(before)])
        return subprocess.run(command, capture_output=True, text=True)

    def package(self, entries):
        with zipfile.ZipFile(self.path, "w") as archive:
            for name, xml in entries.items():
                archive.writestr(name, xml)

    def workbook(self, sorted_rows=True, populated=True, changed_cost=False, wrong_source=False):
        categories = [f"Category {i:02}" for i in range(12)]
        rows = list(range(12)) if sorted_rows else list(reversed(range(12)))
        before = {"pivots": 1, "names": ["Old"], "categories": categories, "costs": list(range(1, 13))}
        entries = {
            "xl/workbook.xml": '<workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Additional Data" r:id="sheet"/></sheets>'
                '<pivotCaches><pivotCache cacheId="1" r:id="cache"/></pivotCaches></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships>'
                '<Relationship Id="sheet" Target="worksheets/sheet1.xml"/>'
                '<Relationship Id="cache" Target="pivotCache/pivotCacheDefinition1.xml"/></Relationships>',
            "xl/sharedStrings.xml": "<sst>" + "".join(f"<si><t>{name}</t></si>" for name in categories) + "</sst>",
            "xl/worksheets/sheet1.xml": "<worksheet><sheetData>" + "".join(
                f'<row r="{row + 3}"><c r="B{row + 3}" t="s"><v>{i}</v></c>'
                f'<c r="C{row + 3}"><v>{999 if changed_cost and row == 0 else i + 1}</v></c></row>'
                for row, i in enumerate(rows)) + "</sheetData></worksheet>",
            "xl/pivotTables/pivotTable1.xml": '<pivotTableDefinition name="Old"/>',
            "xl/pivotTables/pivotTable2.xml": '<pivotTableDefinition name="New" cacheId="1">' + (
                '<rowFields><rowField x="0"/></rowFields>'
                '<dataFields><dataField name="Sum of Cost" fld="1" subtotal="sum"/></dataFields>'
                if populated else "") + "</pivotTableDefinition>",
            "xl/pivotCache/pivotCacheDefinition1.xml": '<pivotCacheDefinition><cacheSource>'
                f'<worksheetSource sheet="{"Wrong" if wrong_source else "Additional Data"}" ref="B2:C14"/>'
                '</cacheSource></pivotCacheDefinition>',
        }
        self.package(entries)
        return before

    def test_completed_pdf_passes(self):
        self.path.write_bytes(b"%PDF-1.7\nbody\n%%EOF\n")
        result = self.validate("Pdf")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["verified"])

    def test_pdf_validation_waits_for_publication_to_finish(self):
        self.path.write_bytes(b"%PDF-1.7\nincomplete\n")
        writer = threading.Timer(2, lambda: self.path.write_bytes(b"%PDF-1.7\nbody\n%%EOF\n"))
        writer.start()
        self.addCleanup(writer.join)
        start = time.monotonic()
        result = self.validate("Pdf")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(time.monotonic() - start, 1.5)

    def test_missing_workbook_fails_explicitly(self):
        result = self.validate("Workbook")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Office output not found", result.stderr)

    def test_real_budget_snapshot_has_twelve_rows_and_existing_pivot(self):
        self.path = ROOT.parent / "_library" / "productivity" / "prod_setup" / "abl_docs" / "FamilyBudget.xlsx"
        result = self.validate("Workbook")
        self.assertEqual(result.returncode, 0, result.stderr)
        snapshot = json.loads(result.stdout)
        self.assertEqual(len(snapshot["categories"]), 12)
        self.assertGreater(snapshot["pivots"], 0)

    def test_sorted_populated_pivot_passes(self):
        result = self.validate("Workbook", self.workbook())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unsorted_empty_wrong_source_or_changed_values_fail(self):
        for kwargs, error in (
            ({"sorted_rows": False}, "not sorted"),
            ({"populated": False}, "New Excel PivotTable"),
            ({"wrong_source": True}, "New Excel PivotTable"),
            ({"changed_cost": True}, "category/cost pairs"),
        ):
            with self.subTest(kwargs=kwargs):
                result = self.validate("Workbook", self.workbook(**kwargs))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stderr)

    def test_video_alone_does_not_count_as_picture_insertion(self):
        before = {"pictures": 0, "videos": 0}
        self.package({"ppt/slides/slide1.xml": "<slide><pic><videoFile/></pic></slide>"})
        result = self.validate("Presentation", before)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("both a new picture and a new video", result.stderr)
        self.package({"ppt/slides/slide1.xml": "<slide><pic/><pic><videoFile/></pic></slide>"})
        result = self.validate("Presentation", before)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
