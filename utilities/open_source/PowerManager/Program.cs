// Copyright (c) Microsoft. All rights reserved.
// Licensed under the MIT license. See LICENSE file in the project root for full license information.

using System.Runtime.InteropServices;

namespace PowerManager
{
    public class Program
    {
        static void Main(string[] args)
        {
            var app = new Application();

            Console.WriteLine($"GetBatteryPercentage: {app.GetBatteryPercentage()}%");
            Console.WriteLine($"GetUseUserConfiguredPowerMode: {app.GetUseUserConfiguredPowerMode()}");

            app.SetPowerModeBestPerformance("AC");
            Console.WriteLine($"SetPowerModeBestPerformance(AC)");

            app.SetPowerModeBalanced("DC");
            Console.WriteLine($"SetPowerModeBalanced(DC)");

            Console.WriteLine($"GetPowerMode(AC): {app.GetPowerMode("AC")}");
            Console.WriteLine($"GetPowerMode(DC): {app.GetPowerMode("DC")}");

            app.SetPowerModeBestPerformance("BOTH");
            Console.WriteLine($"SetPowerModeBestPerformance(BOTH)");

            Console.WriteLine($"GetPowerMode(AC): {app.GetPowerMode("AC")}");
            Console.WriteLine($"GetPowerMode(DC): {app.GetPowerMode("DC")}");

            app.SetEnergySaverPercentage(30, "AC");
            Console.WriteLine($"SetEnergySaverPercentage(30, AC)");

            app.SetEnergySaverPercentage(25, "DC");
            Console.WriteLine($"SetEnergySaverPercentage(25, DC)");

            Console.WriteLine($"GetEnergySaverPercentage(AC): {app.GetEnergySaverPercentage("AC")}%");
            Console.WriteLine($"GetEnergySaverPercentage(DC): {app.GetEnergySaverPercentage("DC")}%");

            app.SetEnergySaverPercentage(20, "BOTH");
            Console.WriteLine($"SetEnergySaverPercentage(20, BOTH)");

            Console.WriteLine($"GetEnergySaverPercentage(AC): {app.GetEnergySaverPercentage("AC")}%");
            Console.WriteLine($"GetEnergySaverPercentage(DC): {app.GetEnergySaverPercentage("DC")}%");
        }
    }

    public class Application
    {
        private readonly bool _useUserConfiguredPowerMode;

        private static readonly Guid GUID_POWER_MODE_BEST_POWER_EFFICIENCY = new Guid("961cc777-2547-4f9d-8174-7d86181b8a7a");
        private static readonly Guid GUID_POWER_MODE_BALANCED              = Guid.Empty;
        private static readonly Guid GUID_POWER_MODE_BETTER                = new Guid("3af9b8d9-7c97-431d-ad78-34a8bfea439f");
        private static readonly Guid GUID_POWER_MODE_BEST_PERFORMANCE      = new Guid("ded574b5-45a0-4f42-8737-46345c09c238");

        private static readonly Guid GUID_SUBGROUP_ENERGY_SAVER          = new Guid("de830923-a562-41af-a086-e3a2c6bad2da");
        private static readonly Guid GUID_ENERGY_SAVER_BATTERY_THRESHOLD = new Guid("e69653ca-cf7f-4f05-aa73-cb833fa90ad4");

        public Application()
        {
            _useUserConfiguredPowerMode = HasUserConfiguredPowerModeApis();
        }

        public bool GetUseUserConfiguredPowerMode()
        {
            return _useUserConfiguredPowerMode;
        }

        public int GetBatteryPercentage()
        {
            if (!GetSystemPowerStatus(out SYSTEM_POWER_STATUS status))
                throw new Exception("Failed to get system power status");

            if (status.BatteryLifePercent == 255)
                throw new Exception("Battery life percent is unknown");

            return status.BatteryLifePercent;
        }

        public void SetPowerModeBestPowerEfficiency(string powerSource)
        {
            SetPowerModeGuid(GUID_POWER_MODE_BEST_POWER_EFFICIENCY, powerSource);
        }

        public void SetPowerModeBalanced(string powerSource)
        {
            SetPowerModeGuid(GUID_POWER_MODE_BALANCED, powerSource);
        }

        public void SetPowerModeBetter(string powerSource)
        {
            SetPowerModeGuid(GUID_POWER_MODE_BETTER, powerSource);
        }

        public void SetPowerModeBestPerformance(string powerSource)
        {
            SetPowerModeGuid(GUID_POWER_MODE_BEST_PERFORMANCE, powerSource);
        }

        public void SetPowerMode(string mode, string powerSource)
        {
            if (string.IsNullOrWhiteSpace(mode))
                throw new Exception("Invalid power mode argument provided");

            if (!Guid.TryParse(mode, out Guid modeGuid))
                throw new Exception($"Failed to parse provided power mode to GUID: {mode}");

            SetPowerModeGuid(modeGuid, powerSource);
        }

        public void SetPowerModeGuid(Guid mode, string powerSource)
        {
            if (string.IsNullOrWhiteSpace(powerSource))
                throw new Exception("Invalid power source argument provided");

            var isBOTH = powerSource.Equals("BOTH", StringComparison.OrdinalIgnoreCase);
            var isAC   = powerSource.Equals("AC",   StringComparison.OrdinalIgnoreCase) || isBOTH;
            var isDC   = powerSource.Equals("DC",   StringComparison.OrdinalIgnoreCase) || isBOTH;

            if (!isAC && !isDC)
                throw new Exception($"Invalid power source argument provided: {powerSource}");

            if (_useUserConfiguredPowerMode)
            {
                if (isAC && PowerSetUserConfiguredACPowerMode(ref mode) != 0)
                    throw new Exception("Failed to set user configured AC power mode");

                if (isDC && PowerSetUserConfiguredDCPowerMode(ref mode) != 0)
                    throw new Exception("Failed to set user configured DC power mode");

                return;
            }

            // Windows 10 / legacy overlay path
            if (PowerSetActiveOverlayScheme(ref mode) != 0)
                throw new Exception("Failed to set overlay power mode");
        }

        public string GetPowerMode(string powerSource)
        {
            if (string.IsNullOrWhiteSpace(powerSource))
                throw new Exception("Invalid power source argument provided");

            var isAC = powerSource.Equals("AC", StringComparison.OrdinalIgnoreCase);
            var isDC = powerSource.Equals("DC", StringComparison.OrdinalIgnoreCase);

            if (!isAC && !isDC)
                throw new Exception($"Invalid power source argument provided: {powerSource}");

            Guid mode;

            if (_useUserConfiguredPowerMode)
            {
                if (isAC)
                {
                    if (PowerGetUserConfiguredACPowerMode(out mode) != 0)
                        throw new Exception("Failed to get user configured AC power mode");
                }
                else
                {
                    if (PowerGetUserConfiguredDCPowerMode(out mode) != 0)
                        throw new Exception("Failed to get user configured DC power mode");
                }

                return mode.ToString();
            }

            // Windows 10 / legacy overlay path
            if (PowerGetEffectiveOverlayScheme(out mode) != 0)
                throw new Exception("Failed to get overlay power mode");

            return mode.ToString();
        }

        public void SetEnergySaverPercentage(int percentage, string powerSource)
        {
            if (percentage < 0 || percentage > 100)
                throw new Exception("Energy Saver percentage must be between 0 and 100");

            if (string.IsNullOrWhiteSpace(powerSource))
                throw new Exception("Invalid power source argument provided");

            var isBOTH = powerSource.Equals("BOTH", StringComparison.OrdinalIgnoreCase);
            var isAC   = powerSource.Equals("AC",   StringComparison.OrdinalIgnoreCase) || isBOTH;
            var isDC   = powerSource.Equals("DC",   StringComparison.OrdinalIgnoreCase) || isBOTH;

            if (!isAC && !isDC)
                throw new Exception($"Invalid power source argument provided: {powerSource}");

            var schemeGuid = GetActivePowerSchemeGuid();

            var subgroupGuid = GUID_SUBGROUP_ENERGY_SAVER;
            var settingGuid  = GUID_ENERGY_SAVER_BATTERY_THRESHOLD;

            var value = (uint)percentage;

            if (isAC)
            {
                uint result = PowerWriteACValueIndex(
                    IntPtr.Zero,
                    ref schemeGuid,
                    ref subgroupGuid,
                    ref settingGuid,
                    value);

                if (result != 0)
                    throw new Exception(
                        $"Failed to set Energy Saver percentage for AC. Error: {result}");
            }

            if (isDC)
            {
                uint result = PowerWriteDCValueIndex(
                    IntPtr.Zero,
                    ref schemeGuid,
                    ref subgroupGuid,
                    ref settingGuid,
                    value);

                if (result != 0)
                    throw new Exception(
                        $"Failed to set Energy Saver percentage for DC. Error: {result}");
            }

            var applyResult = PowerSetActiveScheme(IntPtr.Zero, ref schemeGuid);

            if (applyResult != 0)
                throw new Exception(
                    $"Failed to apply Energy Saver percentage. Error: {applyResult}");
        }

        public int GetEnergySaverPercentage(string powerSource)
        {
            if (string.IsNullOrWhiteSpace(powerSource))
                throw new Exception("Invalid power source argument provided");

            var isAC = powerSource.Equals("AC", StringComparison.OrdinalIgnoreCase);
            var isDC = powerSource.Equals("DC", StringComparison.OrdinalIgnoreCase);

            if (!isAC && !isDC)
                throw new Exception($"Invalid power source argument provided: {powerSource}");

            var schemeGuid = GetActivePowerSchemeGuid();

            var subgroupGuid = GUID_SUBGROUP_ENERGY_SAVER;
            var settingGuid  = GUID_ENERGY_SAVER_BATTERY_THRESHOLD;

            uint percentage;
            uint result;

            if (isAC)
            {
                result = PowerReadACValueIndex(
                    IntPtr.Zero,
                    ref schemeGuid,
                    ref subgroupGuid,
                    ref settingGuid,
                    out percentage);
            }
            else
            {
                result = PowerReadDCValueIndex(
                    IntPtr.Zero,
                    ref schemeGuid,
                    ref subgroupGuid,
                    ref settingGuid,
                    out percentage);
            }

            if (result != 0)
                throw new Exception(
                    $"Failed to get Energy Saver percentage for {powerSource}. Error: {result}");

            return checked((int)percentage);
        }

        private static bool HasUserConfiguredPowerModeApis()
        {
            if (!NativeLibrary.TryLoad("PowrProf.dll", out IntPtr handle))
                return false;

            try
            {
                var hasAC = NativeLibrary.TryGetExport(
                    handle,
                    "PowerSetUserConfiguredACPowerMode",
                    out _);

                var hasDC = NativeLibrary.TryGetExport(
                    handle,
                    "PowerSetUserConfiguredDCPowerMode",
                    out _);

                return hasAC && hasDC;
            }
            finally
            {
                NativeLibrary.Free(handle);
            }
        }

        private static Guid GetActivePowerSchemeGuid()
        {
            IntPtr schemeGuidPtr = IntPtr.Zero;

            uint result = PowerGetActiveScheme(IntPtr.Zero, out schemeGuidPtr);

            if (result != 0)
                throw new Exception(
                    $"Failed to get active power scheme. Error: {result}");

            try
            {
                return Marshal.PtrToStructure<Guid>(schemeGuidPtr);
            }
            finally
            {
                if (schemeGuidPtr != IntPtr.Zero)
                    LocalFree(schemeGuidPtr);
            }
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool GetSystemPowerStatus(out SYSTEM_POWER_STATUS lpSystemPowerStatus);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerSetUserConfiguredACPowerMode(ref Guid powerModeGuid);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerGetUserConfiguredACPowerMode(out Guid powerModeGuid);


        [DllImport("PowrProf.dll")]
        private static extern uint PowerSetUserConfiguredDCPowerMode(ref Guid powerModeGuid);


        [DllImport("PowrProf.dll")]
        private static extern uint PowerGetUserConfiguredDCPowerMode(out Guid powerModeGuid);


        [DllImport("PowrProf.dll")]
        private static extern uint PowerSetActiveOverlayScheme(ref Guid overlaySchemeGuid);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerGetEffectiveOverlayScheme(out Guid overlaySchemeGuid);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerReadACValueIndex(IntPtr rootPowerKey, ref Guid schemeGuid, ref Guid subGroupOfPowerSettingsGuid,
                                                         ref Guid powerSettingGuid, out uint acValueIndex);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerReadDCValueIndex(IntPtr rootPowerKey, ref Guid schemeGuid, ref Guid subGroupOfPowerSettingsGuid,
                                                         ref Guid powerSettingGuid, out uint dcValueIndex);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerWriteACValueIndex(IntPtr rootPowerKey, ref Guid schemeGuid, ref Guid subGroupOfPowerSettingsGuid,
                                                          ref Guid powerSettingGuid, uint acValueIndex);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerWriteDCValueIndex(IntPtr rootPowerKey, ref Guid schemeGuid, ref Guid subGroupOfPowerSettingsGuid,
                                                          ref Guid powerSettingGuid, uint dcValueIndex);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerGetActiveScheme(IntPtr userRootPowerKey, out IntPtr activePolicyGuid);

        [DllImport("PowrProf.dll")]
        private static extern uint PowerSetActiveScheme(IntPtr userRootPowerKey, ref Guid schemeGuid);

        [DllImport("kernel32.dll")]
        private static extern IntPtr LocalFree(IntPtr hMem);

        [StructLayout(LayoutKind.Sequential)]
        private struct SYSTEM_POWER_STATUS
        {
            public byte ACLineStatus;
            public byte BatteryFlag;
            public byte BatteryLifePercent;
            public byte Reserved1;
            public int  BatteryLifeTime;
            public int  BatteryFullLifeTime;
        }
    }
}
