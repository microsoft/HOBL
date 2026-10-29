import logging
from core.parameters import Params

def run(scenario):
    logging.debug('Executing code block: code_1LCYJ1C.py')

    host_path   = Params.get('procyon', 'host_path')
    license_key = Params.get('procyon', 'key')

    if scenario.platform.lower() == "macos":
        target = f"{scenario.dut_exec_path}/procyon_resources"
        mac_procyon_resources = f"scenarios\\macos\\{scenario.module}\\{scenario.resources}"
        prep_paths = [host_path, mac_procyon_resources]
    else:
        target = f"{scenario.dut_exec_path}\\procyon_resources"
        prep_paths = [host_path]

    if not scenario.checkPrepStatusNew([("procyon", prep_paths)]):
        return

    # Verify parameters
    if host_path == "" or host_path is None:
        logging.warning("Procyon host_path is not set. Not installing")
        return

    if license_key == "":
        scenario.error_fail("Procyon license_key is not set")

    logging.info("Preparing Procyon for first use")

    logging.info(f"Uploading Procyon setup files to {target}")
    scenario._upload(host_path + "\\*", target, check_modified=False)

    logging.info("Running Procyon setup")
    if scenario.platform.lower() == "macos":
        scenario._upload(f"{mac_procyon_resources}\\*", target, check_modified=False)
        scenario._call(["zsh", f"{target}/mac_procyon_prep.sh {license_key}"])
    else:
        scenario._call([f"{target}\\procyon-setup.exe", "/s /sms"])
        scenario._call(["C:\\Program Files\\UL\\Procyon\\ProcyonCmd.exe", f"--register={license_key}"])

    scenario.createPrepStatusControlFile(suffix=prep_paths, module="procyon")
    scenario._sleep_to_now()
