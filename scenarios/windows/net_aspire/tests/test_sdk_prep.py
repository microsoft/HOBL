# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""SDK preparation tests without installers, RPC, or shared toolchain changes."""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


SCENARIO_DIR = Path(__file__).resolve().parents[1]
WINDOWS_PREP = SCENARIO_DIR / 'net_aspire_resources' / 'net_aspire_prep.ps1'
MAC_PREP = SCENARIO_DIR.parents[1] / 'macos' / 'mac_net_aspire' / 'mac_net_aspire_resources' / 'mac_net_aspire_prep.sh'


class SdkPinTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='hobl-sdk-pin-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / 'global.json'
        self.original = {
            'sdk': {'version': '10.0.100-preview.5.25277.114', 'rollForward': 'major', 'allowPrerelease': True},
            'tools': {'dotnet': '10.0.100-preview.5.25277.114',
                      'runtimes': {'dotnet/arm64': ['8.0.0', '9.0.0']}},
            'msbuild-sdks': {'Microsoft.DotNet.Arcade.Sdk': '10.0.0-beta.25351.1'}
        }
        source = MAC_PREP.read_text(encoding='utf-8')
        self.mac_version = re.search(r'^DOTNET_SDK_VERSION="([^"]+)"$', source, re.MULTILINE).group(1)
        self.mac_program = re.search(r"<<'PYSDK'\n(.*?)\nPYSDK", source, re.DOTALL).group(1)
        self.wrapper = self.root / 'pin-sdk.ps1'
        self.wrapper.write_text(r'''
param([string]$PrepScript, [string]$GlobalJsonPath, [string]$InstallerArgsFile)
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($PrepScript, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$pin = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'setAspireSdkVersion'
}, $true)
$version = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and $node.Left.Extent.Text -eq '$dotnetSdkVersion'
}, $true)
$install = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and
        $node.GetCommandName() -eq 'winget' -and $node.Extent.Text.Contains('--version $dotnetSdkVersion')
}, $true)
function log { param([Parameter(ValueFromPipeline)]$msg) process { Write-Output $msg } }
function winget { ConvertTo-Json -InputObject @($args) -Compress | Set-Content -LiteralPath $InstallerArgsFile }
. ([scriptblock]::Create($pin.Extent.Text))
. ([scriptblock]::Create($version.Extent.Text))
& ([scriptblock]::Create($install.Extent.Text))
setAspireSdkVersion -globalJsonPath $GlobalJsonPath -sdkVersion $dotnetSdkVersion
''', encoding='utf-8')

    def configure(self, platform):
        if platform == 'macos':
            return subprocess.run([sys.executable, '-c', self.mac_program, str(self.path), self.mac_version],
                                  capture_output=True, text=True, timeout=30)
        return subprocess.run([shutil.which('pwsh'), '-NoProfile', '-NonInteractive', '-File', str(self.wrapper),
                               '-PrepScript', str(WINDOWS_PREP), '-GlobalJsonPath', str(self.path),
                               '-InstallerArgsFile', str(self.root / 'installer-args.json')],
                              capture_output=True, text=True, timeout=30)

    def platforms(self):
        return ['macos', 'windows'] if shutil.which('pwsh') else ['macos']

    def test_stable_sdk_pin_preserves_dependencies_and_is_idempotent(self):
        results = []
        for platform in self.platforms():
            with self.subTest(platform=platform):
                self.path.write_text(json.dumps(self.original), encoding='utf-8')
                for _ in range(2):
                    result = self.configure(platform)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                config = json.loads(self.path.read_text(encoding='utf-8-sig'))
                self.assertEqual(config['sdk']['version'], self.mac_version)
                self.assertEqual(config['tools']['dotnet'], config['sdk']['version'])
                self.assertFalse(config['sdk']['allowPrerelease'])
                self.assertEqual(config['sdk']['rollForward'], 'disable')
                self.assertEqual(config['tools']['runtimes'], self.original['tools']['runtimes'])
                self.assertEqual(config['msbuild-sdks'], self.original['msbuild-sdks'])
                if platform == 'windows':
                    args = json.loads((self.root / 'installer-args.json').read_text(encoding='utf-8-sig'))
                    self.assertEqual(args[args.index('--version') + 1], config['sdk']['version'])
                    self.assertEqual(args[args.index('--id') + 1],
                                     'Microsoft.DotNet.SDK.' + config['sdk']['version'].split('.')[0])
                results.append(config)
        self.assertTrue(all(config == results[0] for config in results))

    def test_invalid_json_fails_without_replacing_the_file(self):
        for platform in self.platforms():
            with self.subTest(platform=platform):
                self.path.write_text('invalid JSON', encoding='utf-8')
                result = self.configure(platform)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.path.read_text(encoding='utf-8'), 'invalid JSON')

    def test_missing_json_fails_without_creating_a_replacement(self):
        for platform in self.platforms():
            with self.subTest(platform=platform):
                result = self.configure(platform)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
