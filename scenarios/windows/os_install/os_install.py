# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

#PREP STEP:

# 1. Copy the lkg dev image contents from release server for the specific project from the \image\[Project] folder. (Do not copy the IMAGE folder itself, just all the contents inside the folder to the LKG folder)
# 2. Profile should include these line to properly execute os_install.py:

    # [os_install]
    # ; Sets the path and user information to the root share *if needed comment out if this is not needed
    # share_path: \\"server"\prelaunch
    # install_path_password: "domain password"
    # install_path_username: "domain account"
    # ; Sets the path for the WIM image
    # image_path: \\"server"\prelaunch\Images\[product]\[lkg]

# 4. Plug the DUT into a wired ethernet conncetion on scenarios and make sure the profile is pointing the that ip address.
# 5. You are now ready to run the automation.

#RUNNING THE AUTOMATION: 

# 6. On the Host, open PowerShell as an admin. OS_Install.py can be run directly or in the hobl dashboard. It is also included as the first step in the hobl_prep.ps1 (comented by default)
# 7. At the end of the process you should be booted into the new OS and SimpleRemote should start automatically (The device will reboot multiple times during the installation process.)
# 8. Or if you chose the whole prep then at the end you should be able to run hobl straight away (Be sure all prep and training scenarios were completed successfully before starting hobl)

###NOTES and known issues: ####

#1. Ignore any windows that pop-up when the drives are being partitioned and formated. Windows is automatically triggers this when it discovers new drives. We can ignore this since it does not interfere with automation.
#2. Occationally, if SurfaceBlockCopyTool.exe runs into failure while installing the OS it it possible that the device will not boot post-reboot. This error occurs outside the control of this automation and there is not way to get a status from the tool. If the device gets into this state you can fix it by doing a USB Key based OS install like we did in the past for manual installs. 
#3. This automation is for DEV images ONLY. We do not support Selfhost images or PLE images as of now since those builds don't have WinPE image.

import logging
import os
import time
from core.parameters import Params
import core.app_scenario
import scenarios.windows.dut_setup as dut_setup
import core.call_rpc as rpc
import scenarios.windows.recharge as recharge
import tempfile


class OsInstall(core.app_scenario.Scenario):
    module = __module__.split('.')[-1]
    original_dut_ip = Params.get('global', 'dut_ip')

    # Set default parameters
    Params.setDefault(module, 'share_path', '')
    Params.setDefault(module, 'image_path', '')
    Params.setDefault(module, 'install_path_username', '')
    Params.setDefault(module, 'install_path_password', '')
    Params.setDefault(module, 'install_wifi_name', '')
    Params.setDefault(module, 'install_wifi_password', '')
    Params.setDefault(module, 'install_dut_ip', original_dut_ip)
    Params.setDefault(module, 'post_deploy_delay', '120', desc="Time to wait (in seconds) after imaging for PostDeploy scripts to complete.")
    Params.setDefault(module, 'verify_only', '0', desc="When 1, skip boot image copy + imaging and run post-install verification/support steps only.")
    Params.setDefault(module, 'post_install_cleanup', '1', desc="When 1, remove install partitions (TOAST/BOOTME) and expand C: after successful install.")
 
    # Override collection of config data, traces, and execution of callbacks 
    # Importing dut_setup sets local_execution to 1.  We need to set it back to 0 communicate with DUT.
    Params.setOverride("global", "local_execution", "0")
    # Params.setOverride("global", "collection_enabled", "0")
    Params.setOverride("global", "prep_tools", "")
    Params.setOverride("global", "attempts", "1")
    Params.setOverride("dut_setup", "reboot_prompt", "0")
    Params.setOverride("dut_setup", "reboot", "0")
    Params.setOverride("dut_setup", "upload_path", "U:\\dut_setup_files\\")
    Params.setOverride('global', 'dut_ip', Params.get(module, 'install_dut_ip'))


    # Get default parameters from ini file for setup dut (share_path, install_path_username, install_path_password)
    share_path = Params.get(module, 'share_path')
    image_path = Params.get(module, 'image_path')
    install_path_username = Params.get(module, 'install_path_username')
    install_path_password = Params.get(module, 'install_path_password')
    install_wifi_name = Params.get(module, 'install_wifi_name')
    install_wifi_password = Params.get(module, 'install_wifi_password')
    dut_name = Params.get('global', 'dut_name')
    post_deploy_delay = int(Params.get(module, 'post_deploy_delay'))
    verify_only = Params.get(module, 'verify_only') == '1'
    post_install_cleanup = Params.get(module, 'post_install_cleanup') == '1'

    is_prep = True


    def setUp(self):
        # Don't call base setUp so that we don't interact with DUT.
        return


    def runTest(self):
        if not self.verify_only and self.image_path == '':
            logging.info("Image path not specified... skipping.")
            return

        if not self.verify_only:
            # # Delete pagefile.sys and reboot DUT.
            # if self._check_remote_file_exists("C:\\pagefile.sys"):
            #     self._call(["powershell.exe", "wmic computersystem set AutomaticManagedPagefile=False"])
            #     self._call(["powershell.exe", "wmic pagefileset delete"])
            #     self._call(["shutdown.exe", "/r /f /t 5"])
            #     time.sleep(15)
            #     self._wait_for_dut_comm()
            #     self._call(["shutdown.exe", "/r /f /t 5"])
            #     time.sleep(15)
            #     self._wait_for_dut_comm()
            # else:
            #     pass

            rc = recharge.Recharge()
            rc.setResumeThreshold('40')
            rc.setMonitorOnly('1')  # Do not turn on charger, just monitor battery level
            rc.runTest()
            time.sleep(2)

            if self.install_wifi_name != '':
                self.switch_to_intall_network()
                time.sleep(10)

            # Ensure volume shrink is not blocked by System Protection / restore points.
            self.disable_system_protection_and_restore_points()

            delete_image = self.dut_exec_path + "\\os_install_resources\\DeleteImage.ps1"
            os_install_automation = self.dut_exec_path + "\\os_install_resources\\SBCT"

            # Disable Bitlocker on C:
            if self.getStatus() == "FullyDecrypted":
                logging.info("Drive already decrypted.")
            else:
                # Decrypt
                logging.info("Disabling drive encryption.")
                self._call(["powershell.exe", 'Disable-bitlocker -MountPoint "C:"'])
                # Wait until fully decrypted
                while(True):
                    progress = self.getPercentage()
                    logging.info(f"Encryption percentage: {progress}%")
                    if progress == "0":
                        break
                    else:
                        time.sleep(10)
                status = self.getStatus()
                logging.info(f"Drive status: {status}")
                if status != "FullyDecrypted":
                    logging.error("Drive decryption failed")
                    self.fail("Drive decryption failed.")

            # Copy over resources
            self._upload("scenarios\\windows\\os_install\\os_install_resources", self.dut_exec_path)

            # Remove previous or failed WinPE drive setup
            self._call(["powershell.exe", "-ExecutionPolicy Unrestricted " + delete_image])

            # Setup access to shared drive
            # TO_DO: make path and password paramters
            logging.info("Mounting image path")
            # self._call(["cmd.exe", "/c net use " + self.share_path + " " + self.install_path_password + " /user:" + self.install_path_username], expected_exit_code="")
            self._call(["cmd.exe", f'/c net use "{self.share_path}" "{self.install_path_password}" /user:"{self.install_path_username}"'], expected_exit_code="")

            # Execute InstallWinPE.ps1 to initiate copying of WinPE and image. True = AutoReboot  False = manual reboot
            logging.info("Copying boot image...")
            try:
                # self._call(["cmd.exe", f'/c {os_install_automation}\\SetupODE.cmd -buildLink {self.image_path} -username {self.install_path_username} -password "{self.install_path_password}" -unattend "NoRollBack,nolocaladmin" -WiFi_Install True'], timeout=7200, expected_exit_code="")
                self._call(["powershell", f'-command "& {{ Set-Location -Path """{os_install_automation}""" ; {os_install_automation}\\SetupODE.ps1 -buildLink {self.image_path} -username {self.install_path_username} -password """{self.install_path_password}""" -unattend """NoRollBack,nolocaladmin""" -WiFi_Install True ; exit $LASTEXITCODE }}"'], timeout=9000, expected_exit_code="")
            except Exception as ex:
                if "timeout" in str(ex).lower():
                    logging.error("Copying boot image timed out after 9000 seconds")
                    self.fail("Copying boot image timed out after 9000 seconds")
                else:
                    pass
            logging.info("Boot image copied")
            time.sleep(2)

            # Generate dut_setup files, including SimpleRemote, by directly calling the dut_setup module.
            # This will automatically upload the files to the proper directory (specified in the device profile), and reboot
            logging.info("Copying files for DUT setup")
            ds = dut_setup.DutSetup()
            ds.runTest()
            time.sleep(2)

            logging.info("Imaging...")

            self._call(["shutdown.exe", "/r /f /t 5"])
            Params.setOverride('global', 'dut_ip', self.original_dut_ip)
            time.sleep(20)

            # Poll for simple remote to determine is DUT setup is complete
            self._wait_for_dut_comm()

            # At this point dut_setup has been run, but the image's PostDeploy script is running after
            # and may do a reboot, so wait and check for dut comm again.
            logging.info(f"Waiting {self.post_deploy_delay}s for any PostDeploy script to complete...")
            time.sleep(self.post_deploy_delay)
            self._wait_for_dut_comm()

            # Wait for first run items to complete
            logging.info("Waiting 60s for any first-run items to complete...")
            time.sleep(60)

            # Create hobl_data folder, if it doesn't already exist
            self._remote_make_dir(self.dut_data_path, False)

            # # Restart to prevent IO blue screen
            logging.info("Restarting to clear out any first-run items left open...")
            self._call(["shutdown.exe", "/r /f /t 5"])

            # Poll for simple remote to determine is DUT setup is complete
            time.sleep(15)
            self._wait_for_dut_comm()
            logging.info("Delaying to allow for RPC Connection")
            time.sleep(120)
        else:
            logging.info("verify_only=1, skipping boot image copy/imaging flow and running post-install steps only.")
            self._wait_for_dut_comm()

        # Uploading OS Install Resources to hobl_bin
        self._upload("scenarios\\windows\\os_install\\os_install_resources", self.dut_exec_path)

        # Upload VerifyVersions package. Prefer proprietary utilities path when present,
        # otherwise use the copy bundled with os_install_resources.
        verify_versions_source = "utilities\\proprietary\\VerifyVersions"
        if not os.path.isdir(verify_versions_source):
            verify_versions_source = "scenarios\\windows\\os_install\\os_install_resources\\VerifyVersions"

        if not os.path.isdir(verify_versions_source):
            logging.error("VerifyVersions source not found on host in expected locations.")
            self.fail("VerifyVersions source not found on host. Expected utilities\\proprietary\\VerifyVersions or scenarios\\windows\\os_install\\os_install_resources\\VerifyVersions.")

        self._upload(verify_versions_source, self.dut_exec_path)
        verify_versions_path = self.dut_exec_path + "\\VerifyVersions"

        if not self._check_remote_file_exists(verify_versions_path):
            self.fail("VerifyVersions package was not found on DUT after upload.")

        # copy d:\bin\postdeploy\drivers folder to support folder if c:\support doesn't already exist
        if not self._check_remote_file_exists(r"c:\support"):
            if self._check_remote_file_exists(r"d:\bin\postdeploy\drivers"):
                logging.debug(r"Copying d:\bin\postdeploy\drivers folder to c:\support folder.")
                self._call(["cmd.exe", r"/c robocopy /E d:\bin\postdeploy\drivers c:\support\drivers /np /nfl /ndl"], expected_exit_code="")
            elif self._check_remote_file_exists(r"d:\support"):
                logging.debug(r"Copying d:\support folder to c:\support folder.")
                self._call(["cmd.exe", r"/c robocopy /E d:\support c:\support /np /nfl /ndl"], expected_exit_code="")
            else:
                logging.info("Can't find drivers folder on D:\ for version verification.")

        # Rename BOOTME partition to TOAST
        bootme_letter = self._call(["powershell.exe", '(get-volume -FriendlyName """BOOTME""" -erroraction ignore | Where-Object {$_.DriveType -eq """Fixed"""}).DriveLetter'], expected_exit_code="")
        if bootme_letter != "" and bootme_letter != None:
            logging.info("Found BOOTME with drive letter: " + bootme_letter + ", renaming to TOAST")
            self._call(["powershell.exe", 'label ' + bootme_letter + ': TOAST'], expected_exit_code="")
        else:
            logging.info("BOOTME drive not found")

        # Build support folder and run VerifyOemDrivers from updated VerifyVersions.
        logging.info("Preparing support folder for verification...")
        if not self._check_remote_file_exists(verify_versions_path + "\\Create-SupportFolder.ps1"):
            self.fail("Create-SupportFolder.ps1 is missing on DUT at " + verify_versions_path)
        create_support_cmd = (
            f'-NoProfile -ExecutionPolicy RemoteSigned -Command "& \'{verify_versions_path}\\Create-SupportFolder.ps1\'"'
        )
        self._call([
            "powershell.exe",
            create_support_cmd
        ], expected_exit_code="")

        logging.info("Verifying drivers...")
        self._call(["cmd.exe", "/c " + verify_versions_path + "\\VerifyOemDrivers.cmd"], expected_exit_code="")
        exit_code = Params.getCalculated('last_call_exit_code')
        logging.debug("Driver verify got exit code " + str(exit_code))
        # Copy results back to host
        rpc.download(self.dut_ip, self.rpc_port, verify_versions_path + "\\*.html", self.result_dir)
        rpc.download(self.dut_ip, self.rpc_port, verify_versions_path + "\\*.xml", self.result_dir)

        if exit_code == "1":
            logging.error ("Verification of drivers failed, check results_drivers1.html")
            self.fail("Verification of drivers failed. Check results_drivers1.html.")
        else:
            logging.info ("Verification of drivers PASSed")

        if self.post_install_cleanup and not self.verify_only:
            self.cleanup_drive_after_successful_install()
        elif self.post_install_cleanup and self.verify_only:
            logging.info("Skipping post-install cleanup because verify_only=1.")


    def cleanup_drive_after_successful_install(self):
        logging.info("Running post-install drive cleanup (preserve TOAST/BOOTME, remove other extra partitions, expand C:)...")
        cleanup_cmd = (
            "$labels=@('TOAST','BOOTME','SHIFU_SCOTT'); "
            "$os=Get-Partition -DriveLetter C -ErrorAction SilentlyContinue; "
            "if(-not $os){ Write-Host 'C: partition not found; skipping cleanup.'; exit 0 }; "
            "$disk=$os.DiskNumber; $osPartNum=$os.PartitionNumber; "
            "$toastPartNum=$null; "
            "$toastVol=Get-Volume -ErrorAction SilentlyContinue | Where-Object {$_.DriveType -eq 'Fixed' -and $_.FileSystemLabel -in $labels -and $_.DriveLetter} | Select-Object -First 1; "
            "if($toastVol){ $tp=Get-Partition -DriveLetter $toastVol.DriveLetter -ErrorAction SilentlyContinue; if($tp -and $tp.DiskNumber -eq $disk){ $toastPartNum=$tp.PartitionNumber; Write-Host ('Preserving TOAST partition #' + $toastPartNum + ' (' + $toastVol.FileSystemLabel + ')') }}; "
            "$keepGpt=@('{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}','{e3c9e316-0b5c-4db8-817d-f92df00215ae}'); "
            "$parts=Get-Partition -DiskNumber $disk -ErrorAction SilentlyContinue; "
            "foreach($p in $parts){ "
            "  $keep=($p.PartitionNumber -eq $osPartNum) -or ($toastPartNum -and $p.PartitionNumber -eq $toastPartNum) -or ($p.GptType -in $keepGpt); "
            "  if(-not $keep){ "
            "    Write-Host ('Removing extra partition #' + $p.PartitionNumber + ' size=' + $p.Size + ' gpt=' + $p.GptType); "
            "    Remove-Partition -DiskNumber $disk -PartitionNumber $p.PartitionNumber -Confirm:$false -ErrorAction SilentlyContinue "
            "  } "
            "}; "
            "$osNow=Get-Partition -DriveLetter C -ErrorAction SilentlyContinue; "
            "$supported=Get-PartitionSupportedSize -DriveLetter C -ErrorAction SilentlyContinue; "
            "if($osNow -and $supported -and $supported.SizeMax -gt $osNow.Size){ "
            "  Write-Host ('Expanding C: to ' + $supported.SizeMax); "
            "  Resize-Partition -DriveLetter C -Size $supported.SizeMax -ErrorAction SilentlyContinue "
            "} else { "
            "  Write-Host 'C: cannot be expanded further (likely blocked by preserved TOAST position).'; "
            "}"
        )
        self._call([
            "powershell.exe",
            f'-NoProfile -ExecutionPolicy Bypass -Command "{cleanup_cmd}"'
        ], expected_exit_code="")


    def disable_system_protection_and_restore_points(self):
        logging.info("Disabling System Protection on all fixed drives and removing restore points/shadow copies...")

        # Disable System Protection for all fixed drives so new restore points are not created.
        fixed_drives = self._call([
            "powershell.exe",
            '-NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_LogicalDisk | Where-Object {$_.DriveType -eq 3 -and $_.DeviceID} | Select-Object -ExpandProperty DeviceID"'
        ], expected_exit_code="").strip()

        if fixed_drives:
            drive_list = [drive.strip() for drive in fixed_drives.splitlines() if drive.strip()]
            logging.info(f"Fixed drives detected for System Protection disable: {drive_list}")
            for drive in drive_list:
                self._call([
                    "powershell.exe",
                    '-NoProfile -ExecutionPolicy Bypass -Command "Disable-ComputerRestore -Drive ' + drive + '\\ -ErrorAction SilentlyContinue"'
                ], expected_exit_code="")
        else:
            logging.warning("No fixed drives were detected while disabling System Protection.")

        # Remove restore point snapshots (shadow copies) that can block volume shrink.
        self._call([
            "powershell.exe",
            '-NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance -ClassName Win32_ShadowCopy -ErrorAction SilentlyContinue | Remove-CimInstance -ErrorAction SilentlyContinue"'
        ], expected_exit_code="")

        remaining_shadow_copies = self._call([
            "powershell.exe",
            '-NoProfile -ExecutionPolicy Bypass -Command "(@(Get-CimInstance -ClassName Win32_ShadowCopy -ErrorAction SilentlyContinue)).Count"'
        ], expected_exit_code="").strip()

        if remaining_shadow_copies not in ("", "0"):
            logging.error(f"Failed to clear shadow copies. Remaining count: {remaining_shadow_copies}")
            self.fail(f"Failed to clear shadow copies. Remaining count: {remaining_shadow_copies}")

        logging.info("System Protection disabled and restore point snapshots cleared.")


    def switch_to_intall_network(self):
        install_wifi_xml = '''<?xml version="1.0"?>
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
				<authentication>WPA2PSK</authentication>
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
        install_wifi_xml = install_wifi_xml.replace("WIFI_HEX", self.install_wifi_name.encode('utf-8').hex().upper())
        install_wifi_xml = install_wifi_xml.replace("WIFI_NAME", self.install_wifi_name)
        install_wifi_xml = install_wifi_xml.replace("WIFI_PASSWORD", self.install_wifi_password)

        xml_filename = f"wifi_{self.dut_name}.xml"
        source_path = os.path.join(tempfile.gettempdir(), xml_filename)

        with open(source_path, "w") as text_file:
            text_file.write(install_wifi_xml)

        rpc.upload(self.dut_ip, self.rpc_port, source_path, self.dut_exec_path)
        os.remove(source_path)

        # Connect to install wifi profile
        self._call(["cmd.exe", "/c netsh wlan add profile filename= " +  os.path.join(self.dut_exec_path, xml_filename) ])
        time.sleep(2)
        for i in range(20):
            # It an take a few tries to connect
            try:
                logging.info("Trying to connect to " + self.install_wifi_name)
                self._call(["cmd.exe", "/c netsh wlan connect name=" + self.install_wifi_name + " interface=Wi-Fi" ], timeout=10)
                break
            except:
                time.sleep(1)
                continue
        if i >= 19:
            logging.error("Time out trying to connect to install network: " + self.install_wifi_name)
            self.fail("Timeout trying to connect to install network: " + self.install_wifi_name)

        self._call(["cmd.exe", "/c netsh wlan set profileparameter name=" + self.install_wifi_name + " connectionmode=auto nonBroadcast=yes" ])

        time.sleep(10)
        # Log which SSID we are now conected to
        result = self._call(["cmd.exe", '/c netsh wlan show interface name="Wi-Fi"' ])
        lines = result.split('\n')
        for line in lines:
            if " SSID" in line:
                logging.info("Switched to" + line)

    def getStatus(self):
        result = self._call(["powershell.exe", '(Get-BitLockerVolume -MountPoint "C:").VolumeStatus'])
        return result

    def getPercentage(self):
        result = self._call(["powershell.exe", '(Get-BitLockerVolume -MountPoint "C:").EncryptionPercentage'])
        return result

    def tearDown(self):
        # Don't call base tearDown so that we don't interact with DUT.
        return


    def kill(self):
        # Prevent base kill routine from running
        return 0
