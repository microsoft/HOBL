# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Combined display settings tool

from parameters import Params
from scenarios.app_scenario import Scenario
import base64
import logging
import re
import time


class Tool(Scenario):
    '''
    Combined display settings tool. Configures one or more display properties
    before a test. Initial values are saved to the DUT registry on first use
    and only restored when display_restore=1 is set.

    Only parameters that are explicitly provided are processed — empty parameters
    are ignored, so the tool can be called for any subset of operations.

    Parameters:
      als_adaptive_brightness       0/1 — adaptive brightness (ALS) on/off (Windows only)
      hdr                           0/1 — HDR on/off (Windows only)
      hdr_auto                      0/1 — Auto HDR on/off (Windows only)
      refresh_rate                  60/120/dynamic — display refresh rate (Windows only)
      content_adaptive_brightness   Off/Always/On battery only — CABC mode (Windows only)
      adaptive_color                0/1 — adaptive color management on/off (Windows only)
      brightness                    brightness value (e.g. 65, 65%, 150nits)
      nits_map                      nits-to-slider mapping (e.g. "100nits:50% 150nits:65%")
      display_restore               1 — restore all saved initial values after test
    '''
    module = __module__.split('.')[-1]

    # Parameters — empty defaults mean "don't change" unless explicitly provided
    Params.setDefault(module, 'als_adaptive_brightness', '', desc="Adaptive brightness (1=on, 0=off).", valOptions=["0", "1"])
    Params.setDefault(module, 'adaptive_color', '', desc="Adaptive color (1=on, 0=off).", valOptions=["0", "1"])
    Params.setDefault(module, 'content_adaptive_brightness', '', desc="CABC: Off, Always, or OnBatteryOnly.", valOptions=["Off", "Always", "OnBatteryOnly"])
    Params.setDefault(module, 'hdr', '', desc="HDR (1=on, 0=off).", valOptions=["0", "1"])
    Params.setDefault(module, 'hdr_auto', '', desc="Auto HDR (1=on, 0=off).", valOptions=["0", "1"])
    Params.setDefault(module, 'refresh_rate', '', desc="Refresh rate: 60, 120, or dynamic.", valOptions=["60", "120", "dynamic"])
    Params.setDefault(module, 'brightness', '150nits', desc="Brightness slider percentage or desired nits (e.g. 65, 65%, 150nits).  If you specify nits, the nits_map parameter will be used to determine the corresponding slider value.")
    Params.setDefault(module, 'nits_map', '100nits:50% 150nits:65%', desc="Nits-to-slider mapping.  Use luminance meter to determine for specific device.")
    Params.setDefault(module, 'display_restore', '', desc="Restore all display settings to saved initial values (1=restore).", valOptions=["0", "1"])

    # HOBL registry key for persisting initial state (lives on the DUT)
    REG_KEY_PATH = r"HKLM\SOFTWARE\HOBL"

    # CABC bidirectional mapping: name↔registry value
    CABC_MAP = {"off": "0", "always": "1", "onbatteryonly": "2",
                "0": "off", "1": "always", "2": "onbatteryonly"}

    # Registry paths — HDR
    MONITOR_DATA_STORE = r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers\MonitorDataStore"
    HDR_REG_PATH = r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\VideoSettings"
    HDR_REG_VALUE = "EnableHDRForPlayback"
    DIRECTX_USER_PREFS = r"HKCU\Software\Microsoft\DirectX\UserGpuPreferences"
    DIRECTX_GLOBAL_SETTINGS = "DirectXUserGlobalSettings"

    # Registry paths — CABC
    CABC_REG_PATH = r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
    CABC_REG_VALUE = "CABCOption"

    # Registry paths — ACM (Adaptive Color)
    DES_STATE_PATH = r"HKLM\SYSTEM\CurrentControlSet\Services\DisplayEnhancementService\State"
    SCHTASK_NAME = "HOBL_ACM_RegWrite"

    # =========================================================================
    # State persistence helpers — read/write/delete from HKLM\SOFTWARE\HOBL
    # =========================================================================

    def _save_state(self, name, value):
        """Save initial state to HOBL registry for later restoration."""
        self._call(["cmd.exe", f'/C reg add "{self.REG_KEY_PATH}" /v "{name}" /t REG_SZ /d "{value}" /f'], expected_exit_code="")

    def _read_state(self, name):
        """Read saved state from HOBL registry. Returns string or None."""
        result = self._call(["cmd.exe", f'/C reg query "{self.REG_KEY_PATH}" /v "{name}"'], expected_exit_code="")
        if result and name in result:
            try:
                return result.split("REG_SZ")[-1].strip().strip('"')
            except Exception:
                pass
        return None

    def _clear_state(self, name):
        """Delete saved state from HOBL registry."""
        self._call(["cmd.exe", f'/C reg delete "{self.REG_KEY_PATH}" /v "{name}" /f'], expected_exit_code="")

    # =========================================================================
    # ALS (Adaptive Brightness) — powercfg
    # =========================================================================

    def _init_als(self, desired):
        result = self._call(["cmd.exe", "/C powercfg -query scheme_current sub_video ADAPTBRIGHT"])
        if not result or "Current AC Power Setting Index" not in result:
            logging.warning("ADAPTBRIGHT not found in power scheme. Adaptive brightness may not be supported on this device.")
            return

        ac_value = "0"
        dc_value = "0"
        for line in result.splitlines():
            if "Current AC Power Setting Index" in line:
                ac_value = "1" if "0x00000001" in line else "0"
            elif "Current DC Power Setting Index" in line:
                dc_value = "1" if "0x00000001" in line else "0"
        logging.info("Current Adaptive Brightness - AC: %s, DC: %s", ac_value, dc_value)

        # Only save initial state if not already saved (first scenario captures the true original)
        if self._read_state("InitialAdaptBrightAC") is None:
            self._save_state("InitialAdaptBrightAC", ac_value)
            self._save_state("InitialAdaptBrightDC", dc_value)
            logging.info("Saved initial Adaptive Brightness - AC: %s, DC: %s", ac_value, dc_value)

        self._call(["cmd.exe", f"/C powercfg -setacvalueindex scheme_current sub_video ADAPTBRIGHT {desired}"])
        self._call(["cmd.exe", f"/C powercfg -setdcvalueindex scheme_current sub_video ADAPTBRIGHT {desired}"])
        self._call(["cmd.exe", "/C powercfg -setactive scheme_current"])
        logging.info("Adaptive Brightness set to: %s", desired)

    def _restore_als(self):
        ac_value = self._read_state("InitialAdaptBrightAC")
        dc_value = self._read_state("InitialAdaptBrightDC")

        if ac_value is not None and dc_value is not None:
            logging.info("Restoring Adaptive Brightness - AC: %s, DC: %s", ac_value, dc_value)
            self._call(["cmd.exe", f"/C powercfg -setacvalueindex scheme_current sub_video ADAPTBRIGHT {ac_value}"])
            self._call(["cmd.exe", f"/C powercfg -setdcvalueindex scheme_current sub_video ADAPTBRIGHT {dc_value}"])
            self._call(["cmd.exe", "/C powercfg -setactive scheme_current"])

        self._clear_state("InitialAdaptBrightAC")
        self._clear_state("InitialAdaptBrightDC")

    # =========================================================================
    # Brightness — powercfg
    # =========================================================================

    def _init_brightness(self, brightness_str, nits_map_str):
        platform = Params.get('global', 'platform')

        nits_table = {}
        if nits_map_str and nits_map_str != "Unknown":
            for t in nits_map_str.split(" "):
                nits_str, slider_str = t.split(":")
                nits = re.findall(r'\d+', nits_str)[0]
                try:
                    slider = re.findall(r'\d+', slider_str)[0]
                except Exception:
                    logging.error("Invalid slider value in nits_map: %s", nits_map_str)
                    raise Exception("Invalid slider value in nits_map:", nits_map_str)
                nits_table[nits] = slider

        brightness_val = re.findall(r'\d+', brightness_str)[0]
        if "nits" in brightness_str:
            if brightness_val in nits_table:
                brightness_val = nits_table[brightness_val]
            else:
                raise Exception(f"No slider mapping for {brightness_str}.")

        if platform and platform.lower() == "android":
            logging.warning("Brightness save/restore is not supported on Android.")
            self._host_call("adb -s " + self.dut_ip + ":5555 shell settings put system screen_brightness " + str(brightness_val), expected_exit_code="")
        elif platform and platform.lower() == "macos":
            logging.warning("Brightness save/restore is not supported on macOS.")
            self._call([self.dut_exec_path + "/brightness", str(int(brightness_val) / 100.0)])
        else:
            # Save initial brightness if not already saved
            if self._read_state("InitialBrightness") is None:
                result = self._call(["cmd.exe", "/C powercfg -query scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb"])
                if result and "Current AC Power Setting Index" in result:
                    for line in result.splitlines():
                        if "Current AC Power Setting Index" in line:
                            match = re.search(r'0x([0-9a-fA-F]+)', line)
                            if match:
                                current_val = str(int(match.group(1), 16))
                                self._save_state("InitialBrightness", current_val)
                                logging.info("Saved initial brightness: %s", current_val)
                            break

            self._call(["cmd.exe", "/c Powercfg.exe -SETDCVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb " + str(brightness_val)])
            self._call(["cmd.exe", "/c Powercfg.exe -SETACVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb " + str(brightness_val)])
            self._call(["cmd.exe", "/c Powercfg.exe -SETACTIVE scheme_balanced"])

        logging.info("Display brightness set to: %s", brightness_val)

    def _restore_brightness(self):
        """Restore brightness from previously saved value in DUT registry."""
        brightness_val = self._read_state("InitialBrightness")
        if brightness_val is not None:
            logging.info("Restoring brightness to: %s", brightness_val)
            self._call(["cmd.exe", "/c Powercfg.exe -SETDCVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb " + brightness_val])
            self._call(["cmd.exe", "/c Powercfg.exe -SETACVALUEINDEX scheme_balanced SUB_VIDEO aded5e82-b909-4619-9949-f5d71dac0bcb " + brightness_val])
            self._call(["cmd.exe", "/c Powercfg.exe -SETACTIVE scheme_balanced"])
        self._clear_state("InitialBrightness")

    # =========================================================================
    # CABC (Content Adaptive Brightness) — registry
    # =========================================================================

    def _read_cabc(self):
        result = self._call(["cmd.exe", f'/C reg query "{self.CABC_REG_PATH}" /v {self.CABC_REG_VALUE}'], expected_exit_code="")
        if not result or self.CABC_REG_VALUE not in result:
            return None
        match = re.search(r'CABCOption\s+REG_DWORD\s+(0x[0-9a-fA-F]+)', result)
        if match:
            return str(int(match.group(1), 16))
        return None

    def _write_cabc(self, value):
        self._call(["cmd.exe", f'/C reg add "{self.CABC_REG_PATH}" /v {self.CABC_REG_VALUE} /t REG_DWORD /d {value} /f'], expected_exit_code="")

    def _init_cabc(self, desired_str):
        desired = self.CABC_MAP.get(desired_str.lower())
        if desired is None:
            logging.error("Invalid content_adaptive_brightness value: '%s'. Use Off, Always, or OnBatteryOnly.", desired_str)
            return

        current = self._read_cabc()
        if current is None:
            logging.warning("CABCOption not found. CABC may not be supported on this device.")
            return

        logging.info("Current CABC: %s (%s), desired: %s (%s)",
                     current, self.CABC_MAP.get(current, "?"),
                     desired, self.CABC_MAP.get(desired, "?"))

        # Only save initial state if not already saved
        if self._read_state("InitialCABCOption") is None:
            self._save_state("InitialCABCOption", current)
            logging.info("Saved initial CABC: %s (%s)", current, self.CABC_MAP.get(current, "?"))

        if current == desired:
            logging.info("CABC already at desired state. No change needed.")
            return

        self._write_cabc(desired)
        logging.info("CABC set to %s (%s).", desired, self.CABC_MAP.get(desired, "?"))

    def _restore_cabc(self):
        initial = self._read_state("InitialCABCOption")
        if initial is None:
            return

        current = self._read_cabc()
        if current == initial:
            logging.info("CABC already at initial state (%s). No restore needed.", initial)
        else:
            logging.info("Restoring CABC to %s (%s).", initial, self.CABC_MAP.get(initial, "?"))
            self._write_cabc(initial)

        self._clear_state("InitialCABCOption")

    # =========================================================================
    # ACM (Adaptive Color) — scheduled task + reg + service restart
    # =========================================================================

    def _find_acm_display(self):
        """Find the first display with IsAdaptiveColorOn. Returns (display_id, value) or (None, None)."""
        result = self._call(["cmd.exe", f'/C reg query "{self.DES_STATE_PATH}" /s /v IsAdaptiveColorOn'], expected_exit_code="")
        if not result:
            return None, None
        current_key = None
        for line in result.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("HKEY_LOCAL_MACHINE") or stripped.upper().startswith("HKLM"):
                current_key = stripped
            elif "IsAdaptiveColorOn" in stripped and current_key:
                match = re.search(r'IsAdaptiveColorOn\s+REG_DWORD\s+(0x[0-9a-fA-F]+)', stripped)
                if match:
                    display_id = current_key.rsplit("\\", 1)[-1]
                    return display_id, int(match.group(1), 16)
                current_key = None
        return None, None

    def _read_acm(self, display_id):
        reg_path = f"{self.DES_STATE_PATH}\\{display_id}"
        result = self._call(["cmd.exe", f'/C reg query "{reg_path}" /v IsAdaptiveColorOn'], expected_exit_code="")
        if not result or "IsAdaptiveColorOn" not in result:
            return None
        match = re.search(r'IsAdaptiveColorOn\s+REG_DWORD\s+(0x[0-9a-fA-F]+)', result)
        if match:
            return int(match.group(1), 16)
        return None

    def _write_acm_as_system(self, display_id, value):
        """Write IsAdaptiveColorOn via a scheduled task running as SYSTEM."""
        reg_path = f"{self.DES_STATE_PATH}\\{display_id}"
        reg_cmd = f'reg.exe add {reg_path} /v IsAdaptiveColorOn /t REG_DWORD /d {value} /f'
        self._call(["cmd.exe", f'/C schtasks.exe /Create /TN "{self.SCHTASK_NAME}" /TR "{reg_cmd}" /SC ONCE /ST 00:00 /RU SYSTEM /F'], expected_exit_code="")
        # Allow task to run on battery (default is AC-only)
        self._call(["cmd.exe", "/C powershell.exe -Command \"$t = Get-ScheduledTask '%s'; $t.Settings.DisallowStartIfOnBatteries = $false; $t.Settings.StopIfGoingOnBatteries = $false; Set-ScheduledTask -InputObject $t | Out-Null\"" % self.SCHTASK_NAME], expected_exit_code="")
        self._call(["cmd.exe", f'/C schtasks.exe /Run /TN "{self.SCHTASK_NAME}"'], expected_exit_code="")
        time.sleep(2)
        self._call(["cmd.exe", f'/C schtasks.exe /Delete /TN "{self.SCHTASK_NAME}" /F'], expected_exit_code="")

    def _restart_display_service(self):
        """Restart DisplayEnhancementService to apply registry changes."""
        self._call(["cmd.exe", "/C net stop DisplayEnhancementService"], expected_exit_code="")
        time.sleep(1)
        self._call(["cmd.exe", "/C net start DisplayEnhancementService"], expected_exit_code="")
        time.sleep(2)

    def _set_acm(self, display_id, value):
        # Stop service first so it doesn't overwrite our registry change on restart
        self._call(["cmd.exe", "/C net stop DisplayEnhancementService"], expected_exit_code="")
        time.sleep(1)
        self._write_acm_as_system(display_id, value)
        self._call(["cmd.exe", "/C net start DisplayEnhancementService"], expected_exit_code="")
        time.sleep(2)

        actual = self._read_acm(display_id)
        if actual == value:
            logging.info("Adaptive color set to %d for display %s.", value, display_id)
            return

        # Retry once if verification failed
        logging.warning("Adaptive color verification failed (expected %d, got %s). Retrying...", value, actual)
        self._call(["cmd.exe", "/C net stop DisplayEnhancementService"], expected_exit_code="")
        time.sleep(1)
        self._write_acm_as_system(display_id, value)
        self._call(["cmd.exe", "/C net start DisplayEnhancementService"], expected_exit_code="")
        time.sleep(3)

        actual = self._read_acm(display_id)
        if actual == value:
            logging.info("Adaptive color set to %d for display %s (retry succeeded).", value, display_id)
        else:
            logging.warning("Adaptive color verification: expected %d but got %s for display %s.", value, actual, display_id)

    def _init_acm(self, desired_str):
        desired = int(desired_str)
        display_id, current = self._find_acm_display()
        if display_id is None:
            logging.warning("No display with adaptive color support found.")
            return

        logging.info("Found adaptive color display: %s, current state: %d", display_id, current)

        # Only save initial state if not already saved
        if self._read_state("InitialACMState") is None:
            self._save_state("InitialACMState", str(current))
            self._save_state("ACMDisplayID", display_id)
            logging.info("Saved initial ACM state: %d for display %s", current, display_id)

        if current == desired:
            logging.info("Adaptive color already at %d. No change needed.", desired)
            return

        self._set_acm(display_id, desired)

    def _restore_acm(self):
        display_id = self._read_state("ACMDisplayID")
        if not display_id:
            return

        initial_str = self._read_state("InitialACMState")
        if initial_str is None:
            return

        try:
            initial_state = int(initial_str)
        except Exception as e:
            logging.warning("Failed to parse initial ACM state: %s", e)
            return

        current = self._read_acm(display_id)
        if current == initial_state:
            logging.info("Adaptive color already at initial state (%d). No restore needed.", initial_state)
        else:
            logging.info("Restoring adaptive color to %d for display %s.", initial_state, display_id)
            self._set_acm(display_id, initial_state)

        self._clear_state("InitialACMState")
        self._clear_state("ACMDisplayID")

    # =========================================================================
    # HDR — MonitorDataStore + Win+Alt+B toggle / vHDR registry fallback
    # =========================================================================

    def _get_auto_hdr_state(self):
        """Read AutoHDREnable from DirectXUserGlobalSettings. Returns '1', '0', or None."""
        result = self._call(["cmd.exe", f'/C reg query "{self.DIRECTX_USER_PREFS}" /v "{self.DIRECTX_GLOBAL_SETTINGS}"'], expected_exit_code="")
        if not result or self.DIRECTX_GLOBAL_SETTINGS not in result:
            return None
        match = re.search(r'REG_SZ\s+(.+)', result)
        if not match:
            return None
        for pair in match.group(1).strip().split(";"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                if key.strip() == "AutoHDREnable":
                    return value.strip()
        return None

    def _set_auto_hdr_state(self, enabled):
        """Set AutoHDREnable in DirectXUserGlobalSettings, preserving other values."""
        desired_value = "1" if enabled else "0"
        result = self._call(["cmd.exe", f'/C reg query "{self.DIRECTX_USER_PREFS}" /v "{self.DIRECTX_GLOBAL_SETTINGS}"'], expected_exit_code="")

        if result and self.DIRECTX_GLOBAL_SETTINGS in result:
            match = re.search(r'REG_SZ\s+(.+)', result)
            if match:
                pairs = match.group(1).strip().split(";")
                found = False
                new_pairs = []
                for pair in pairs:
                    if "=" in pair:
                        key, _ = pair.split("=", 1)
                        if key.strip() == "AutoHDREnable":
                            new_pairs.append(f"AutoHDREnable={desired_value}")
                            found = True
                        else:
                            new_pairs.append(pair)
                    elif pair.strip():
                        new_pairs.append(pair)
                if not found:
                    new_pairs.append(f"AutoHDREnable={desired_value}")
                new_settings = ";".join(new_pairs)
            else:
                new_settings = f"AutoHDREnable={desired_value}"
        else:
            new_settings = f"AutoHDREnable={desired_value}"

        self._call(["cmd.exe", f'/C reg add "{self.DIRECTX_USER_PREFS}" /v "{self.DIRECTX_GLOBAL_SETTINGS}" /t REG_SZ /d "{new_settings}" /f'], expected_exit_code="")
        logging.info("Set AutoHDREnable to %s", desired_value)

    def _find_hdr_monitors(self):
        """Search MonitorDataStore for monitors with an HDREnabled key."""
        result = self._call(["cmd.exe", f'/C reg query "{self.MONITOR_DATA_STORE}" /s /v HDREnabled'], expected_exit_code="")
        monitors = []
        if not result:
            logging.warning("MonitorDataStore query returned no output. This may indicate a failed remote command rather than no HDR monitors.")
            return monitors
        logging.debug("MonitorDataStore raw output:\n%s", result)
        current_key = None
        for line in result.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("HKEY_LOCAL_MACHINE") or stripped.upper().startswith("HKLM"):
                current_key = stripped
            elif "HDREnabled" in stripped and current_key:
                match = re.search(r'HDREnabled\s+REG_DWORD\s+(0x[0-9a-fA-F]+)', stripped)
                if match:
                    monitors.append((current_key, int(match.group(1), 16)))
                    current_key = None
        return monitors

    def _get_full_hdr_state(self):
        """Return True if full HDR is enabled, False if disabled, None if unavailable."""
        monitors = self._find_hdr_monitors()
        if not monitors:
            return None
        return monitors[0][1] != 0

    def _send_win_alt_b(self):
        """Simulate Win+Alt+B key combination on the DUT to toggle HDR."""
        ps_script = (
            'Add-Type -TypeDefinition \'\n'
            'using System;\n'
            'using System.Runtime.InteropServices;\n'
            'public class KbdSim {\n'
            '    [DllImport("user32.dll")]\n'
            '    static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);\n'
            '    public static void SendWinAltB() {\n'
            '        keybd_event(0x5B, 0, 0, 0);\n'
            '        keybd_event(0x12, 0, 0, 0);\n'
            '        keybd_event(0x42, 0, 0, 0);\n'
            '        keybd_event(0x42, 0, 2, 0);\n'
            '        keybd_event(0x12, 0, 2, 0);\n'
            '        keybd_event(0x5B, 0, 2, 0);\n'
            '    }\n'
            '}\n'
            "'\n"
            '[KbdSim]::SendWinAltB()'
        )
        encoded = base64.b64encode(ps_script.encode('utf-16-le')).decode('ascii')
        self._call(["cmd.exe", f'/C powershell.exe -EncodedCommand {encoded}'], expected_exit_code="")

    def _toggle_full_hdr(self, desired_on, post_delay=7):
        """Toggle full HDR via Win+Alt+B. post_delay is wait time after toggle."""
        current_on = self._get_full_hdr_state()
        if current_on is None:
            return False

        if current_on == desired_on:
            logging.info("Full HDR already %s, no toggle needed.", "enabled" if desired_on else "disabled")
            return True

        logging.info("Toggling full HDR via Win+Alt+B...")
        self._send_win_alt_b()
        logging.info("Waiting %ds for HDR toast notification to disappear...", post_delay)
        time.sleep(post_delay)

        new_state = self._get_full_hdr_state()
        if new_state == desired_on:
            logging.info("Full HDR successfully set to %s.", "enabled" if desired_on else "disabled")
        else:
            logging.warning("Full HDR toggle verification: expected %s but got %s.", "enabled" if desired_on else "disabled", "enabled" if new_state else "disabled")
        return True

    def _apply_vhdr_state(self, state):
        value = 1 if str(state) == "1" else 0
        self._call(["cmd.exe", f'/C reg add "{self.HDR_REG_PATH}" /v "{self.HDR_REG_VALUE}" /t REG_DWORD /d {value} /f'], expected_exit_code="")

    def _init_hdr(self, hdr_param, auto_hdr_param):
        """Handle HDR and/or Auto HDR setup.
        hdr_param: '0', '1', or '' (don't change HDR toggle)
        auto_hdr_param: '0', '1', or '' (don't change Auto HDR)
        """
        monitors = self._find_hdr_monitors()
        if monitors:
            logging.info("Found %d HDR-capable monitor(s). Using full HDR mode.", len(monitors))
            current_hdr_on = monitors[0][1] != 0

            # Determine desired HDR state
            desired_hdr_on = (hdr_param == "1") if hdr_param else current_hdr_on

            # Determine desired Auto HDR state
            current_auto_hdr = self._get_auto_hdr_state() or "0"
            desired_auto_hdr = (auto_hdr_param == "1") if auto_hdr_param else (current_auto_hdr == "1")

            initial_state = "1" if current_hdr_on else "0"
            logging.info("Initial full HDR state: %s", initial_state)
            logging.info("Initial Auto HDR state: %s", current_auto_hdr)

            hdr_needs_change = current_hdr_on != desired_hdr_on
            auto_hdr_needs_change = desired_hdr_on and current_auto_hdr != ("1" if desired_auto_hdr else "0")

            # Only save initial state if not already saved
            if self._read_state("InitialHDRState") is None:
                self._save_state("InitialHDRState", initial_state)
                self._save_state("HDRMode", "full")
                self._save_state("InitialAutoHDRState", current_auto_hdr)
                logging.info("Saved initial HDR state: %s, Auto HDR: %s", initial_state, current_auto_hdr)

            if hdr_needs_change or auto_hdr_needs_change:
                self._set_auto_hdr_state(desired_auto_hdr)

                if hdr_needs_change:
                    # 7s delay during init for toast notification to disappear
                    if not self._toggle_full_hdr(desired_hdr_on, post_delay=7):
                        logging.warning("Failed to toggle HDR. Monitor may have become unavailable.")
                else:
                    # Double-toggle to apply Auto HDR change
                    logging.info("Double-toggling HDR to apply Auto HDR change...")
                    self._send_win_alt_b()
                    logging.info("Waiting 7s for HDR toast notification to disappear...")
                    time.sleep(7)
                    self._send_win_alt_b()
                    logging.info("Waiting 7s for HDR toast notification to disappear...")
                    time.sleep(7)
            else:
                logging.info("HDR and Auto HDR already in desired state.")

            logging.info("HDR=%s, Auto HDR=%s", "1" if desired_hdr_on else "0", "1" if desired_auto_hdr else "0")
            return

        # vHDR fallback — only if hdr_param was explicitly provided
        if auto_hdr_param:
            logging.warning("Auto HDR is not supported in vHDR mode. Ignoring hdr_auto setting.")
        if not hdr_param:
            logging.warning("No HDR-capable monitors found and no HDR parameter provided. Skipping.")
            return

        logging.info("No HDR-capable monitors found. Falling back to vHDR mode.")
        result = self._call(["cmd.exe", f'/C reg query "{self.HDR_REG_PATH}" /v "{self.HDR_REG_VALUE}"'], expected_exit_code="")

        if not result or self.HDR_REG_VALUE not in result:
            initial_on = False
        else:
            initial_on = "0x0" not in result.lower()

        initial_state = "1" if initial_on else "0"
        logging.info("Current vHDR state: %s", initial_state)

        # Only save initial state if not already saved
        if self._read_state("InitialHDRState") is None:
            self._save_state("InitialHDRState", initial_state)
            self._save_state("HDRMode", "vhdr")
            logging.info("Saved initial vHDR state: %s", initial_state)

        if initial_state != hdr_param:
            self._apply_vhdr_state(hdr_param)
            logging.info("vHDR state set to: %s", hdr_param)
        else:
            logging.info("vHDR already at desired state: %s", hdr_param)

    def _restore_hdr(self):
        mode = self._read_state("HDRMode")
        if not mode:
            return

        use_full_hdr = mode.lower() == "full"

        initial_auto_hdr = None
        if use_full_hdr:
            initial_auto_hdr = self._read_state("InitialAutoHDRState")

        initial_state = self._read_state("InitialHDRState")
        if not initial_state:
            self._clear_state("InitialHDRState")
            self._clear_state("HDRMode")
            self._clear_state("InitialAutoHDRState")
            return

        try:
            initial_state = initial_state.lower()
            logging.info("Restoring HDR state to: %s (mode: %s)", initial_state, mode)

            if use_full_hdr:
                desired_hdr_on = initial_state == "1"

                auto_hdr_changed = False
                if initial_auto_hdr is not None:
                    current_auto_hdr = self._get_auto_hdr_state()
                    auto_hdr_changed = current_auto_hdr != initial_auto_hdr
                    self._set_auto_hdr_state(initial_auto_hdr == "1")

                current_hdr_on = self._get_full_hdr_state()
                if current_hdr_on != desired_hdr_on:
                    if not self._toggle_full_hdr(desired_hdr_on):
                        logging.warning("Failed to restore HDR toggle. Monitor may have become unavailable.")
                elif auto_hdr_changed and desired_hdr_on:
                    logging.info("Double-toggling HDR to restore Auto HDR state...")
                    self._send_win_alt_b()
                    logging.info("Waiting 7s for HDR toast notification to disappear...")
                    time.sleep(7)
                    self._send_win_alt_b()
                    logging.info("Waiting 7s for HDR toast notification to disappear...")
                    time.sleep(7)
            else:
                self._apply_vhdr_state(initial_state)
        except Exception as e:
            logging.warning("Failed to restore HDR state: %s", e)

        self._clear_state("InitialHDRState")
        self._clear_state("HDRMode")
        self._clear_state("InitialAutoHDRState")

    # =========================================================================
    # Refresh Rate — WinAppDriver UI automation
    # =========================================================================

    def _start_driver(self):
        """Start WinAppDriver and connect with Root desktop session."""
        self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port + " /forcequit")], blocking=False)
        time.sleep(2)
        driver = self._launchApp({"app": "Root"})
        driver.implicitly_wait(10)
        return driver

    def _stop_driver(self, driver):
        """Close driver and kill WinAppDriver + SystemSettings."""
        try:
            driver.close()
        except Exception:
            pass
        self._kill("SystemSettings.exe")
        self._kill("WinAppDriver")

    def _navigate_to_advanced_display(self, driver):
        """Open Settings to Display page, then navigate to Advanced Display."""
        self._call(["cmd.exe", '/C start ms-settings:display'])
        time.sleep(2)

        ps_script = (
            "Add-Type -Name Win -Namespace Native -MemberDefinition @'\n"
            '[DllImport("user32.dll")] public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);\n'
            '[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);\n'
            "'@\n"
            "$h = [Native.Win]::FindWindow('ApplicationFrameWindow', 'Settings')\n"
            "if ($h -ne [IntPtr]::Zero) { [Native.Win]::ShowWindow($h, 3) }"
        )
        encoded = base64.b64encode(ps_script.encode('utf-16-le')).decode('ascii')
        self._call(["cmd.exe", f'/C powershell.exe -EncodedCommand {encoded}'], expected_exit_code="")
        time.sleep(1)

        driver.find_element_by_name("Advanced display").click()
        time.sleep(1)

    def _find_rr_combo(self, driver):
        """Find the refresh rate ComboBox element."""
        try:
            return driver.find_element_by_xpath("//ComboBox[contains(@Name, 'refresh rate') or contains(@Name, 'Refresh rate')]")
        except Exception:
            return driver.find_element_by_name("Refresh rate")

    def _find_drr_toggle(self, driver):
        """Scroll down and find the DRR toggle element."""
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        ActionChains(driver).send_keys(Keys.PAGE_DOWN).perform()
        time.sleep(1)
        try:
            return driver.find_element_by_xpath("//Button[contains(@Name, 'Dynamic refresh rate')]")
        except Exception:
            return driver.find_element_by_name("Dynamic refresh rate")

    @staticmethod
    def _read_toggle_state(toggle):
        """Read a WinAppDriver toggle button state. Returns '1' or '0'."""
        state = toggle.get_attribute("Toggle.ToggleState")
        if state is not None:
            return "1" if state == "1" else "0"
        return "1" if toggle.is_selected() else "0"

    def _get_refresh_rate(self, driver):
        """Read current refresh rate from the ComboBox. Returns Hz string or None."""
        rr_combo = self._find_rr_combo(driver)

        current_name = rr_combo.text
        if current_name:
            match = re.search(r'(\d+)', current_name)
            if match:
                return match.group(1)
        return None

    def _set_refresh_rate(self, driver, hz):
        """Set refresh rate via dropdown. Returns previous Hz string or None if unchanged."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        rr_combo = self._find_rr_combo(driver)
        current_name = rr_combo.text
        logging.info("Current refresh rate dropdown value: %s", current_name)

        previous_hz = None
        if current_name:
            match = re.search(r'(\d+)', current_name)
            if match:
                previous_hz = match.group(1)

        if previous_hz == str(hz):
            logging.info("Refresh rate already at %s Hz, no change needed.", hz)
            return None

        rr_combo.click()
        time.sleep(1)

        try:
            target_rate = driver.find_element_by_name(f"{hz} Hz")
        except Exception:
            target_rate = driver.find_element_by_xpath(f"//*[contains(@Name, '{hz}') and contains(@Name, 'Hz')]")
        time.sleep(1)

        target_rate.click()
        time.sleep(1)

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "Keep changes"))).click()

        time.sleep(2)
        logging.info("Refresh rate set to %s Hz.", hz)
        return previous_hz

    def _get_drr_state(self, driver):
        """Read DRR toggle state. Returns '1', '0', or None."""
        drr_toggle = self._find_drr_toggle(driver)
        return self._read_toggle_state(drr_toggle)

    def _set_drr(self, driver, enabled):
        """Set DRR toggle. Returns previous state as '1'/'0', or None on failure."""
        drr_toggle = self._find_drr_toggle(driver)
        previous = self._read_toggle_state(drr_toggle)
        logging.info("Current DRR state: %s", "on" if previous == "1" else "off")

        if not drr_toggle.is_enabled():
            logging.warning("DRR toggle is grayed out. A higher refresh rate may need to be selected first.")
            return previous

        desired_state = "1" if enabled else "0"
        if previous != desired_state:
            drr_toggle.click()
            time.sleep(1)
            new_val = self._read_toggle_state(drr_toggle)
            logging.info("DRR toggled to: %s", "on" if new_val == "1" else "off")
        else:
            logging.info("DRR already %s, no change needed.", "on" if enabled else "off")

        return previous

    def _init_refresh_rate(self, desired):
        want_dynamic = desired == "dynamic"
        target_hz = "120" if want_dynamic else desired

        logging.info("Requested refresh rate: %s (target_hz=%s, DRR=%s)",
                     desired, target_hz, "on" if want_dynamic else "off")
        logging.info("Starting WinAppDriver for refresh rate settings...")
        driver = self._start_driver()

        try:
            self._navigate_to_advanced_display(driver)

            current_hz = self._get_refresh_rate(driver)
            logging.info("Current refresh rate: %s Hz", current_hz)

            if current_hz and current_hz != str(target_hz):
                # Only save initial state if not already saved
                if self._read_state("InitialRefreshRate") is None:
                    self._save_state("InitialRefreshRate", current_hz)
                    logging.info("Saved initial refresh rate: %s Hz", current_hz)

                logging.info("Changing refresh rate: %s Hz -> %s Hz", current_hz, target_hz)
                self._set_refresh_rate(driver, target_hz)

                time.sleep(1)
                verify_hz = self._get_refresh_rate(driver)
                if verify_hz == str(target_hz):
                    logging.info("Verified refresh rate is now %s Hz.", verify_hz)
                else:
                    logging.warning("Refresh rate verification failed: expected %s Hz, got %s Hz.", target_hz, verify_hz)
            else:
                logging.info("Refresh rate already at %s Hz, no change needed.", target_hz)

            # Handle DRR: enable for dynamic, disable for 120, skip for 60 (grayed out)
            if want_dynamic or str(target_hz) == "120":
                # Only save initial DRR state if not already saved
                if self._read_state("InitialDRRState") is None:
                    current_drr = self._get_drr_state(driver)
                    if current_drr is not None:
                        self._save_state("InitialDRRState", current_drr)
                        logging.info("Saved initial DRR state: %s", "on" if current_drr == "1" else "off")

                previous_drr = self._set_drr(driver, want_dynamic)

                verify_drr = self._get_drr_state(driver)
                expected_drr = "1" if want_dynamic else "0"
                if verify_drr == expected_drr:
                    logging.info("Verified DRR is now %s.", "on" if want_dynamic else "off")
                else:
                    logging.warning("DRR verification: expected %s, got %s.", expected_drr, verify_drr)

        except Exception as e:
            logging.warning("Refresh rate setup failed: %s", e)

        finally:
            self._stop_driver(driver)

    def _restore_refresh_rate(self):
        drr_saved = self._read_state("InitialDRRState")
        rr_saved = self._read_state("InitialRefreshRate")

        if not drr_saved and not rr_saved:
            return

        logging.info("Starting WinAppDriver to restore refresh rate settings...")
        driver = self._start_driver()

        try:
            self._navigate_to_advanced_display(driver)

            # Restore DRR first (before changing rate, in case DRR needs the current high rate)
            if drr_saved:
                logging.info("Restoring DRR to: %s", "on" if drr_saved == "1" else "off")
                self._set_drr(driver, drr_saved == "1")
                self._clear_state("InitialDRRState")

            # Restore refresh rate
            if rr_saved:
                logging.info("Restoring refresh rate to: %s Hz", rr_saved)
                self._set_refresh_rate(driver, rr_saved)
                self._clear_state("InitialRefreshRate")

        except Exception as e:
            logging.warning("Failed to restore refresh rate settings: %s", e)

        finally:
            self._stop_driver(driver)

    # =========================================================================
    # Callbacks
    # =========================================================================

    def initCallback(self, scenario):
        self.scenario = scenario
        platform = Params.get('global', 'platform')
        is_windows = not platform or platform.lower() in ["windows", "w365"]

        # Read all parameters
        als = Params.get(self.module, 'als_adaptive_brightness').strip()
        hdr = Params.get(self.module, 'hdr').strip()
        auto_hdr = Params.get(self.module, 'hdr_auto').strip()
        rr = Params.get(self.module, 'refresh_rate').strip().lower()
        cabc = Params.get(self.module, 'content_adaptive_brightness').strip()
        acm = Params.get(self.module, 'adaptive_color').strip()
        brightness = Params.get(self.module, 'brightness').strip()
        nits_map = Params.get(self.module, 'nits_map').strip()

        # Brightness (cross-platform)
        if brightness or nits_map:
            self._init_brightness(brightness, nits_map)

        # Windows-only features
        if als:
            if is_windows:
                self._init_als(als)
            else:
                logging.warning("Adaptive brightness (ALS) is only supported on Windows.")
        if cabc:
            if is_windows:
                self._init_cabc(cabc)
            else:
                logging.warning("CABC is only supported on Windows.")
        if acm:
            if is_windows:
                self._init_acm(acm)
            else:
                logging.warning("Adaptive color (ACM) is only supported on Windows.")
        if hdr or auto_hdr:
            if is_windows:
                self._init_hdr(hdr, auto_hdr)
            else:
                logging.warning("HDR is only supported on Windows.")
        if rr:
            if is_windows:
                self._init_refresh_rate(rr)
            else:
                logging.warning("Refresh rate setting is only supported on Windows.")

    def testBeginCallback(self):
        return

    def testEndCallback(self):
        display_restore = Params.get(self.module, 'display_restore').strip()
        if display_restore != '1':
            return

        # Check if any init keys exist before logging
        has_state = any(self._read_state(key) is not None for key in [
            "InitialAdaptBrightAC", "InitialCABCOption", "InitialACMState",
            "InitialHDRState", "InitialDRRState", "InitialRefreshRate", "InitialBrightness"
        ])
        if not has_state:
            return

        logging.info("display_restore=1: Restoring all saved display settings.")
        # Restore in reverse order of init
        self._restore_refresh_rate()
        self._restore_hdr()
        self._restore_acm()
        self._restore_cabc()
        self._restore_als()
        self._restore_brightness()

    def dataReadyCallback(self):
        return

    def cleanup(self):
        logging.debug("Cleanup")
        self.testEndCallback()
