# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# DUT setup on USB
#
# Setup instructions:
#   Run the dut_setup scenario
#

import builtins
import logging
import os
import shutil
import subprocess
import sys
import time
from distutils.dir_util import copy_tree
from os import listdir
import core.arguments
from core.parameters import Params
import core.app_scenario
import core.call_rpc as rpc
import ntpath
import binascii
import tempfile

args = core.arguments.args
params_file = args.profile if args else ""
these_params = params_file

class DutSetup(core.app_scenario.Scenario):

    # get parameters from ini file and setup dut (dutname, password, msa configuration, wifi)
    module = __module__.split('.')[-1]
    Params.setDefault(module, 'upload_path', '')
    Params.setDefault(module, 'reboot_prompt', '1')
    Params.setDefault(module, 'local_setup', '0')
    Params.setDefault(module, 'reboot', '1')
    Params.setDefault(module, "target_path", '')
    Params.setDefault(module, 'test_signing', 'None')
    Params.setDefault(module, 'run_cmd', '0', desc="Run setup after uploading to DUT", valOptions=["1", "0"])

    # Override collection of config data, traces, and execution of callbacks 
    Params.setOverride("global", "attempts", "1")
    Params.setOverride("global", "prep_tools", "")

    Params.setOverride('global', 'web_replay_action', 'record')

    # Set default parameters
    upload_path = Params.get(module, 'upload_path')
    local_setup = Params.get(module, 'local_setup')
    target_path = Params.get(module, 'target_path')

    dut_name = Params.get('global', 'dut_name')
    dut_password = Params.get('global', 'dut_password')
    dut_wifi_name = Params.get('global', 'dut_wifi_name')
    dut_wifi_password = Params.get('global', 'dut_wifi_password')
    dut_wifi_authentication = Params.get('global', 'dut_wifi_authentication')
    msa_account = Params.get('global', 'msa_account')
    test_signing = Params.get(module, 'test_signing')
    run_cmd = Params.get(module, 'run_cmd') == "1"
    is_prep = True

    def setUp(self):
        # Don't call base setUp so that we don't interact with DUT.
        return

    def runTest(self):

        self.upload_path = Params.get(self.module, 'upload_path')

        if self.run_cmd:
            self.reboot_prompt = "0"
            if self.upload_path == "": self.upload_path = "C:\\dut_setup_files"
        else:
            self.reboot_prompt = Params.get(self.module, 'reboot_prompt')

        self.reboot = Params.get(self.module, 'reboot')
                
        # app = QtWidgets.QApplication(sys.argv)
        # Open window to query operator for usb drive selection
        if self.upload_path == "" and self.local_setup == "0" and self.target_path == "":
            print("target_path = " + self.target_path)
            self.fail("Unsupported set of parameters.")
            # usb_path = QtWidgets.QFileDialog.getExistingDirectory(None, "Enter USB drive letter to use to setup " + self.dut_name + ":", 'c:\\', QtWidgets.QFileDialog.ShowDirsOnly)
            # if usb_path == '':
            #     return
        elif self.target_path != "":
            logging.info('Writing dut_setup to ' + self.target_path)
            usb_path = self.target_path
        else:
            usb_path = 'c:\\dut_setup_files'
            if self.upload_path != "":
                self.tempdir_obj = tempfile.TemporaryDirectory()
                usb_path =  self.tempdir_obj.name + '\\dut_setup_files'
            self._call(["cmd.exe", "/c if exist C:\\dut_setup_files rmdir /Q /S C:\\dut_setup_files"])
            self._call(["cmd.exe", "/c if not exist C:\\dut_setup_files mkdir C:\\dut_setup_files"])

        # Get current working directory name
        source_path = os.getcwd()
        logging.info("Current path       : " + source_path)
        logging.info("USB Drive          : " + usb_path)
        usb_hobl_bin = usb_path + "\\dut_setup"
        logging.info("USB hobl_bin path  : " + usb_hobl_bin)

        # Delete dut_setup folder from usb drive if it exists
        if os.path.exists(usb_hobl_bin):
            shutil.rmtree(usb_hobl_bin)
            time.sleep(2)

        # Copy dotnet runtime
        self._check_and_download("windowsdesktop-runtime-8.0.23-win-x64.exe", source_path + "\\downloads\\setup\\assets", "https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/%RUNTIME_VERSION%/windowsdesktop-runtime-%RUNTIME_VERSION%-win-x64.exe".replace("%RUNTIME_VERSION%", "8.0.23"))
        self._check_and_download("windowsdesktop-runtime-8.0.23-win-arm64.exe", source_path + "\\downloads\\setup\\assets", "https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/%RUNTIME_VERSION%/windowsdesktop-runtime-%RUNTIME_VERSION%-win-arm64.exe".replace("%RUNTIME_VERSION%", "8.0.23"))
        dotnet_path = os.path.join(usb_hobl_bin, "dotnet")
        if not os.path.exists(dotnet_path):
            os.makedirs(dotnet_path)
        logging.debug("Source: " + source_path + "\\downloads\\setup\\assets\\windowsdesktop-runtime-8.0.23-win-arm64.exe")
        logging.debug("Dest  : " + dotnet_path)
        shutil.copy(source_path + "\\downloads\\setup\\assets\\windowsdesktop-runtime-8.0.23-win-arm64.exe" , dotnet_path)
        logging.debug("Source: " + source_path + "\\downloads\\setup\\assets\\windowsdesktop-runtime-8.0.23-win-x64.exe")
        logging.debug("Dest  : " + dotnet_path)
        shutil.copy(source_path + "\\downloads\\setup\\assets\\windowsdesktop-runtime-8.0.23-win-x64.exe" , dotnet_path)

        # Copy powershell
        self._check_and_download("PowerShell-7.5.4-win-x64.msi", source_path + "\\downloads\\setup\\assets", "https://github.com/PowerShell/PowerShell/releases/download/v%POWERSHELL_VERSION%/PowerShell-%POWERSHELL_VERSION%-win-x64.msi".replace("%POWERSHELL_VERSION%", "7.5.4"))
        self._check_and_download("PowerShell-7.5.4-win-arm64.msi", source_path + "\\downloads\\setup\\assets", "https://github.com/PowerShell/PowerShell/releases/download/v%POWERSHELL_VERSION%/PowerShell-%POWERSHELL_VERSION%-win-arm64.msi".replace("%POWERSHELL_VERSION%", "7.5.4"))
        pwsh_path = os.path.join(usb_hobl_bin, "pwsh")
        if not os.path.exists(pwsh_path):
            os.makedirs(pwsh_path)
        logging.debug("Source: " + source_path + "\\downloads\\setup\\assets\\PowerShell-7.5.4-win-arm64.msi")
        logging.debug("Dest  : " + pwsh_path)
        shutil.copy(source_path + "\\downloads\\setup\\assets\\PowerShell-7.5.4-win-arm64.msi" , pwsh_path)
        logging.debug("Source: " + source_path + "\\downloads\\setup\\assets\\PowerShell-7.5.4-win-x64.msi")
        logging.debug("Dest  : " + pwsh_path)
        shutil.copy(source_path + "\\downloads\\setup\\assets\\PowerShell-7.5.4-win-x64.msi" , pwsh_path)

        # Copy SimpleRemote files
        if not os.path.exists(usb_hobl_bin):
            os.makedirs(usb_hobl_bin)
        if self.local_setup != '1':
            src_files = ["\\SimpleRemoteServer_win-x64.zip", "\\SimpleRemoteServer_win-arm64.zip"]
            for src in src_files:
                dest_dir = usb_hobl_bin + "\\SimpleRemote"
                dest = dest_dir + src
                source = "\\setup_src\\src_dut_win" + src
                if not os.path.exists(dest_dir):
                    os.makedirs(dest_dir)
                logging.debug("Source: " + source_path + source)
                logging.debug("Dest  : " + dest)
                shutil.copy(source_path + source , dest)
                time.sleep(1)

        # Copy PolicyFileEditor folder contents to usb drive
        dest = usb_hobl_bin + "\\PolicyFileEditor"
        if not os.path.exists(dest):
            os.makedirs(dest)
        logging.debug("Source: " + source_path + "\\utilities\\third_party\\PolicyFileEditor")
        logging.debug("Dest  : " + dest)
        copy_tree(source_path + "\\utilities\\third_party\\PolicyFileEditor" , dest, verbose=0)

        # Copy DeskTopImages folder contents to usb drive
        dest = usb_hobl_bin + "\\DeskTopImages"
        if not os.path.exists(dest):
            os.makedirs(dest)
        logging.debug("Source: " + source_path + "\\utilities\\open_source\\DesktopImages")
        logging.debug("Dest  : " + dest)
        copy_tree(source_path + "\\utilities\\open_source\\DesktopImages" , dest, verbose=0)

        # Copy WindowsApplicationDriver folder contents to usb drive
        dest = usb_hobl_bin + "\\WindowsApplicationDriver"
        if not os.path.exists(dest):
            os.makedirs(dest)
        logging.debug("Source: " + source_path + "\\utilities\\proprietary\\WindowsApplicationDriver")
        logging.debug("Dest  : " + dest)
        copy_tree(source_path + "\\utilities\\proprietary\\WindowsApplicationDriver" , dest, verbose=0)

        # Copy vc_redist.x64.exe to usb drive
        self._check_and_download("vc_redist.x64.exe", source_path + "\\downloads\\setup\\assets", "https://aka.ms/vs/17/release/vc_redist.x64.exe")
        dest = usb_hobl_bin
        if not os.path.exists(dest):
            os.makedirs(dest)
        logging.debug("Source: " + source_path + "\\downloads\\setup\\assets\\vc_redist.x64.exe")
        logging.debug("Dest  : " + dest)
        shutil.copy(source_path + "\\downloads\\setup\\assets\\vc_redist.x64.exe", dest)

        src_files = ["\\InputInject_win-x64.zip", "\\InputInject_win-arm64.zip"]
        for src in src_files:
            dest_dir = usb_hobl_bin + "\\InputInject"
            dest = dest_dir + src
            source = "\\Utilities\\open_source\\InputInject\\Output" + src
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            logging.debug("Source: " + source_path + source)
            logging.debug("Dest  : " + dest)
            shutil.copy(source_path + source , dest)
            time.sleep(1)

        # Copy ScreenServer, both architectures, folder to usb drive
        dest = usb_hobl_bin + "\\ScreenServer"
        if not os.path.exists(dest):
            os.makedirs(dest)
        logging.debug("Source: " + source_path + '\\Utilities\\open_source\\ScreenServer\\Output')
        logging.debug("Dest  : " + dest)
        copy_tree(source_path + '\\Utilities\\open_source\\ScreenServer\\Output' , dest, verbose=0)

        # Copy RTCWakeCore Files to usb drive
        dest = usb_hobl_bin + "\\RTCWakeCore"
        if not os.path.exists(dest):
            os.makedirs(dest)
        logging.debug("Source: " + source_path + '\\utilities\\proprietary\\RTCWakeCore')
        logging.debug("Dest  : " + dest)
        copy_tree(source_path + '\\utilities\\proprietary\\RTCWakeCore' , dest, verbose=0)

        # Copy dut ini file to drive
        params_basename = ntpath.basename(params_file)
        logging.debug("Device Profile: " + params_file)
        logging.debug("Copying Device Profile " + params_file + " to " + usb_hobl_bin + "\\" + params_basename)
        shutil.copy(params_file, usb_hobl_bin + "\\" + params_basename)

        # Copy MonitorPowerEvents.exe to usb drive
        logging.debug("Source: " + source_path + "\\utilities\\proprietary\\MonitorPowerEvents\\MonitorPowerEvents.exe")
        logging.debug("Dest  : " + usb_hobl_bin + "\\MonitorPowerEvents.exe")
        shutil.copy(source_path + "\\utilities\\proprietary\\MonitorPowerEvents\\MonitorPowerEvents.exe", usb_hobl_bin + "\\MonitorPowerEvents.exe")

        # Copy charge_status.ps1 to usb drive
        logging.debug("Source: " + source_path + "\\utilities\\open_source\\charge_status.ps1")
        logging.debug("Dest  : " + usb_hobl_bin + "\\charge_status.ps1")
        shutil.copy(source_path + "\\utilities\\open_source\\charge_status.ps1", usb_hobl_bin + "\\charge_status.ps1")


        # Copy copy_wifi_task to usb drive
        logging.debug("Source: " + source_path + "\\utilities\\open_source\\connect_wifi_task.cmd")
        logging.debug("Dest  : " + usb_hobl_bin + "\\connect_wifi_task.cmd")
        
        shutil.copy(source_path + "\\utilities\\open_source\\connect_wifi_task.cmd", usb_hobl_bin + "\\connect_wifi_task.cmd")

        # web_replay related files
        self._web_replay_download("")

        if not os.path.exists(usb_hobl_bin + "\\web_replay"):
            os.makedirs(usb_hobl_bin + "\\web_replay")

        # Copy web_replay helper scripts to usb drive
        shutil.copy(f"C:\\web_replay\\{self.web_replay_version}\\set_args.ps1", usb_hobl_bin + "\\web_replay\\set_args.ps1")
        shutil.copy(f"C:\\web_replay\\{self.web_replay_version}\\remove_args.ps1", usb_hobl_bin + "\\web_replay\\remove_args.ps1")

        # Install web_replay certs
        shutil.copy(f"C:\\web_replay\\{self.web_replay_version}\\install_certs.ps1", usb_hobl_bin + "\\web_replay\\install_certs.ps1")
        shutil.copytree(f"C:\\web_replay\\{self.web_replay_version}\\certs", usb_hobl_bin + "\\web_replay\\certs")

        if not os.path.exists(usb_hobl_bin + "\\remote"):
            os.makedirs(usb_hobl_bin + "\\remote")

        shutil.copytree(f"{source_path}\\utilities\\third_party\\remote\\x64", f"{usb_hobl_bin}\\remote\\x64")
        shutil.copytree(f"{source_path}\\utilities\\third_party\\remote\\arm64", f"{usb_hobl_bin}\\remote\\arm64")
        shutil.copy(f"{source_path}\\utilities\\third_party\\remote\\wallpaper.png", f"{usb_hobl_bin}\\remote\\wallpaper.png")

        # Open connect_wifi_task.cmd file on drive and pre-pend variables
        f = open(source_path + "\\utilities\\open_source\\connect_wifi_task.cmd")
        f1 = open((usb_hobl_bin + "\\connect_wifi_task.cmd"), "w")

        f1.write("set \"msa_account=" + self.msa_account + "\"\n\r")
        f1.write("set \"dut_name=" + self.dut_name + "\"\n\r")
        f1.write("set \"dut_password=" + self.dut_password + "\"\n\r")
        f1.write("set \"dut_wifi_name=" + self.dut_wifi_name + "\"\n\r")
        f1.write(" " + "\n\r")
        for line in f.readlines():
            f1.write(line)
        f1.close()
        f.close()
        
        # Copy simple_remote_setup.ps1 to usb drive
        logging.debug("Source: " + source_path + "\\setup_src\\src_dut_win\\simple_remote_setup.ps1")
        logging.debug("Dest  : " + usb_hobl_bin + "\\simple_remote_setup.ps1")
        shutil.copy(source_path + "\\setup_src\\src_dut_win\\simple_remote_setup.ps1", usb_hobl_bin + "\\simple_remote_setup.ps1")

        # Copy rename.ps1 to usb drive
        logging.debug("Source: " + source_path + r"\setup_src\src_dut_win\rename.ps1")
        logging.debug("Dest  : " + usb_hobl_bin + r"\rename.ps1")
        shutil.copy(source_path + r"\setup_src\src_dut_win\rename.ps1", usb_hobl_bin + r"\rename.ps1")

        # Copy schedule_connect_wifi.ps1 to usb drive
        logging.debug("Source: " + source_path + r"\setup_src\src_dut_win\schedule_connect_wifi.ps1")
        logging.debug("Dest  : " + usb_hobl_bin + r"\schedule_connect_wifi.ps1")
        shutil.copy(source_path + r"\setup_src\src_dut_win\schedule_connect_wifi.ps1", usb_hobl_bin + r"\schedule_connect_wifi.ps1")

        # Copy tee.exe to usb drive
        shutil.copy(f"{source_path}\\utilities\\third_party\\tee\\tee.exe", f"{usb_hobl_bin}\\tee.exe")

        # Copy dut_setup.cmd to usb drive
        logging.debug("Source: " + source_path + "\\setup_src\\src_dut_win\\dut_setup.cmd")
        logging.debug("Dest  : " + usb_path + "\\dut_setup.cmd")

        # Open dut_setup.cmd file on drive and pre-pend variables
        f = open(source_path + "\\setup_src\\src_dut_win\\dut_setup.cmd")
        f1 = open((usb_path + "\\dut_setup.cmd"), "w")

        f1.write("set \"dut_name=" + self.dut_name + "\"\n\r")
        f1.write("set \"dut_password=" + self.dut_password + "\"\n\r")
        f1.write("set \"dut_wifi_name=" + self.dut_wifi_name + "\"\n\r")
        f1.write("set \"reboot_prompt=" + self.reboot_prompt + "\"\n\r")
        f1.write("set \"reboot=" + self.reboot + "\"\n\r")
        f1.write("set \"local_setup=" + self.local_setup + "\"\n\r")
        if self.local_setup == "0":
            self.install_simple_remote = "1"
        else:
            self.install_simple_remote = "0"
        f1.write("set \"install_simpleremote=" + self.install_simple_remote + "\"\n\r")
        f1.write("set \"test_signing=" + self.test_signing + "\"\n\r")
        f1.write(" " + "\n\r")
        for line in f.readlines():
            f1.write(line)
        f1.close()
        f.close()

        wifi_xml = '''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
	<name>WIFI_NAME</name>
	<SSIDConfig>
		<SSID>
			<hex>WIFI_HEX</hex>
			<name>WIFI_NAME</name>
		</SSID>
        <nonBroadcast>true</nonBroadcast>
	</SSIDConfig>
	<connectionType>ESS</connectionType>
	<connectionMode>manual</connectionMode>
	<MSM>
		<security>
			<authEncryption>
				<authentication>WIFI_AUTH</authentication>
				<encryption>AES</encryption>
				<useOneX>false</useOneX>
                <transitionMode xmlns="http://www.microsoft.com/networking/WLAN/profile/v4">true</transitionMode>
			</authEncryption>
			<sharedKey>
				<keyType>passPhrase</keyType>
				<protected>false</protected>
				<keyMaterial>WIFI_PASSWORD</keyMaterial>
			</sharedKey>
		</security>
	</MSM>
</WLANProfile>
'''
        wifi_xml = wifi_xml.replace("WIFI_HEX", self.dut_wifi_name.encode('utf-8').hex().upper())
        wifi_xml = wifi_xml.replace("WIFI_NAME", self.dut_wifi_name)
        wifi_xml = wifi_xml.replace("WIFI_PASSWORD", self.dut_wifi_password)
        wifi_xml = wifi_xml.replace("WIFI_AUTH", self.dut_wifi_authentication)

        with open(os.path.join(usb_hobl_bin, "wifi.xml"), "w") as text_file:
            text_file.write(wifi_xml)

        if self.upload_path != "":
            # print("Uploading from " + usb_hobl_bin)
            # print("to " + self.upload_path)
            # self._call(["robocopy.exe", usb_path + " " + self.upload_path + " /NDL /NC /BYTES /E /MT:4 /R:3 /W:5 /TBD /NOOFFLOAD /J /ETA /V /log:C:\\DUTSetupRobocopylog.txt"], timeout=1200, expected_exit_code="")
            # logging.debug("DUT Setup files copied")
            # time.sleep(240)
            rpc.upload(self.dut_ip, self.rpc_port, usb_path + "\\dut_setup.cmd", self.upload_path)
            rpc.upload(self.dut_ip, self.rpc_port, usb_hobl_bin + "\\simple_remote_setup.ps1", self.upload_path)
            rpc.upload(self.dut_ip, self.rpc_port, usb_hobl_bin + "\\schedule_connect_wifi.ps1", self.upload_path)
            rpc.upload(self.dut_ip, self.rpc_port, usb_hobl_bin + "\\rename.ps1", self.upload_path)
            rpc.upload(self.dut_ip, self.rpc_port, usb_hobl_bin, self.upload_path)


        if self.local_setup == "1":
            logging.info("Running dut_setup.cmd")
            self._call(["cmd.exe", "/c " + usb_path + "\\dut_setup.cmd"])
        elif self.run_cmd:
            self.run_dut_setup_cmd()

    def run_dut_setup_cmd(self):
        dut_setup_cmd = f"{self.upload_path}\\dut_setup.cmd"
        tee_exe = f"{self.upload_path}\\dut_setup\\tee.exe"

        logging.info("Running dut_setup.cmd")

        self._call(
            ["cmd.exe", f"/c start cmd.exe /c \"{dut_setup_cmd} 2>&1 | {tee_exe} c:\\hobl_bin\\dut_setup.log\""],
            blocking=False
        )

        logging.info("Sleeping for 60s")
        time.sleep(60)

        self._wait_for_dut_comm()

    def tearDown(self):
        # core.app_scenario.Scenario.tearDown(self)

        if self.upload_path == "" and self.local_setup == "0" and self.target_path == "":
            self.fail("Unsupported set of parameters")
            # app = QtWidgets.QApplication(sys.argv)
            # QtWidgets.QMessageBox.about(None, "dut_setup", "The flash drive for setting up DUT " + self.dut_name + " is ready.  Move it to the DUT and execute dut_setup.cmd with Admin privileges.")
        elif self.upload_path != "":
            self.tempdir_obj.cleanup()


    def kill(self):
        # Prevent base kill routine from running
        return 0
