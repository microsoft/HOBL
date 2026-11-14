# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import base64
import json
import logging
import ntpath
from pathlib import Path
import time
import uuid

from core.parameters import Params


def defaults():
    Params.setDefault(
        "enterprise_collab", "office_extended_actions", "0",
        desc="Enable PDF exports, PowerPoint media insertion, and Excel sort/pivot UI actions.",
        valOptions=["0", "1"],
    )


def enabled():
    defaults()
    value = Params.get("enterprise_collab", "office_extended_actions")
    if value not in ("0", "1"):
        raise ValueError("office_extended_actions must be 0 or 1")
    return value == "1"


def validate_configuration():
    if enabled() and Params.get("enterprise_collab", "simple_office_launch") != "1":
        raise ValueError(
            "Set enterprise_collab:simple_office_launch=1 when enabling "
            "enterprise_collab:office_extended_actions"
        )


def _docs():
    if Params.get("global", "platform") == "W365":
        root = Params.get("global", "onedrive_path")
    else:
        root = ntpath.join(Params.get("global", "userprofile"), "OneDrive")
    if not ntpath.isabs(root):
        raise ValueError("The productivity OneDrive path must be absolute")
    return ntpath.join(root, "abl_docs")


def _powershell(scenario, script):
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return scenario._call(
        ["powershell.exe", "-NoProfile -NonInteractive -EncodedCommand " + encoded],
        system=False,
    )


def _quote(value):
    return "'" + value.replace("'", "''") + "'"


def _inspect(scenario, kind, path, before=None):
    validator = ntpath.join(scenario.dut_exec_path, "enterprise_collab_resources", "office_output.ps1")
    script = (
        "$ErrorActionPreference = 'Stop'; & " + _quote(validator)
        + " -Kind " + _quote(kind) + " -Path " + _quote(path)
    )
    if before is not None:
        script += " -Before " + _quote(json.dumps(before))
    output = _powershell(scenario, script)
    return json.loads(output)


def prepare(scenario):
    if not enabled():
        return
    folder = Path(__file__).parent
    target = ntpath.join(scenario.dut_exec_path, "enterprise_collab_resources")
    _powershell(scenario, (
        "$ErrorActionPreference = 'Stop'; "
        "New-Item -ItemType Directory -Path " + _quote(target) + " -Force | Out-Null"
    ))
    scenario._upload(str(folder / "resources" / "office_output.ps1"), target, check_modified=False)
    video = scenario.resolve(r"scenarios\windows\teams\ppt.mp4")
    docs = _docs()
    _powershell(scenario, (
        "$ErrorActionPreference = 'Stop'; "
        "foreach ($path in @(" + ", ".join(_quote(ntpath.join(docs, name)) for name in (
            "FamilyBudget.xlsx", "test_long_doc.docx", "sample.pptx", "Manarola2.png"
        )) + ")) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) "
        "{ throw (' ERROR - Missing productivity asset: ' + $path) }; Write-Output $path }"
    ))
    scenario._upload(video, docs, check_modified=False)


def _element(driver, xpath):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    return WebDriverWait(driver, 60).until(EC.element_to_be_clickable((By.XPATH, xpath)))


def _type(scenario, text):
    delay = int(Params.get("global", "typing_delay"))
    scenario._send_text(text, delay)
    scenario._sleep_by(len(text) * delay / 1000 + 1)


def _app(scenario, document):
    desktop = scenario._launchDesktop()
    window = _element(desktop, "//Window[starts-with(@Name, '" + document + "')]")
    return scenario.getDriverFromWin(window)


def _phase(scenario, name, action):
    start = time.time()
    action()
    scenario._record_phase_time("prod: " + name, start, time.time() - start)


def _export_pdf(scenario, driver, document):
    output = ntpath.join(
        scenario.dut_data_path, document + "_" + uuid.uuid4().hex + ".pdf"
    )
    logging.info("Exporting PDF to %s", output)
    _type(scenario, "\ue00af")
    _type(scenario, "ea")
    filename = _element(driver, "//Edit[@Name='File name:']")
    filename.clear()
    filename.send_keys(output)
    checkbox = _element(driver, "//CheckBox[@Name='Open file after publishing']")
    if checkbox.is_selected():
        checkbox.click()
    _element(driver, "//Button[@Name='Publish']").click()
    scenario._sleep_by(5)
    _inspect(scenario, "Pdf", output)


def run_word(scenario):
    if not enabled():
        return
    driver = _app(scenario, "test_long_doc")
    _phase(scenario, "export_word_pdf", lambda: _export_pdf(scenario, driver, "word"))


def run_excel(scenario):
    if not enabled():
        return
    path = ntpath.join(_docs(), "FamilyBudget.xlsx")
    before = _inspect(scenario, "Workbook", path)
    driver = _app(scenario, "FamilyBudget")

    def sort():
        _type(scenario, "\ue00c\ue009g")
        _type(scenario, "'Additional Data'!B2:C14\ue007")
        _type(scenario, "\ue00aa")
        _type(scenario, "sa")

    def pivot():
        _type(scenario, "\ue009g")
        _type(scenario, "'Additional Data'!B2:C14\ue007")
        _type(scenario, "\ue00an")
        _type(scenario, "vt")
        _element(driver, "//Window[@Name='Create PivotTable' or @Name='PivotTable from table or range']//Button[@Name='OK']").click()
        for name in ("Category", "Cost"):
            field = _element(driver, "//CheckBox[@Name='" + name + "']")
            if not field.is_selected():
                field.click()
        _element(driver, "//*[contains(@Name, 'Sum of Cost')]")
        _type(scenario, "\ue00c\ue009s")
        scenario._sleep_by(5)
        _inspect(scenario, "Workbook", path, before)

    _phase(scenario, "sort_excel", sort)
    _phase(scenario, "create_excel_pivot", pivot)


def run_powerpoint(scenario):
    if not enabled():
        return
    docs = _docs()
    path = ntpath.join(docs, "sample.pptx")
    before = _inspect(scenario, "Presentation", path)
    driver = _app(scenario, "sample")

    def insert_media():
        _type(scenario, "\ue00c\ue009m")
        # Match the CM reference's Pictures > This Device KeyTips.
        _type(scenario, "\ue00an")
        _type(scenario, "p1d")
        filename = _element(driver, "//Edit[@Name='File name:']")
        filename.clear()
        filename.send_keys(ntpath.join(docs, "Manarola2.png"))
        _element(driver, "//Button[@Name='Insert']").click()
        scenario._sleep_by(3)
        _type(scenario, "\ue00c\ue00an")
        _type(scenario, "v")
        _element(driver, "//MenuItem[starts-with(@Name, 'This Device')]").click()
        filename = _element(driver, "//Edit[@Name='File name:']")
        filename.clear()
        filename.send_keys(ntpath.join(docs, "ppt.mp4"))
        _element(driver, "//Button[@Name='Insert']").click()
        scenario._sleep_by(5)
        _type(scenario, "\ue00c\ue009s")
        scenario._sleep_by(5)
        _inspect(scenario, "Presentation", path, before)

    _phase(scenario, "insert_powerpoint_media", insert_media)
    _phase(scenario, "export_powerpoint_pdf", lambda: _export_pdf(scenario, driver, "powerpoint"))
