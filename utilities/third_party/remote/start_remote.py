# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# Start remote
##

from core.parameters import Params
import argparse

import core.call_rpc as rpc


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-profile', '-p')
    arg_parser.add_argument('-target', '-t') # 'aux' or 'dut'
    arg_parser.add_argument('overrides', nargs=argparse.REMAINDER)

    args = arg_parser.parse_args()

    if args.profile is None:
        print('Missing profile')
        return

    target = "dut"
    if args.target is not None:
        target = args.target.lower()

    print(f"Starting remote for target: {target}")

    # This prevents the Params parsing from contacting the DUT to resolve special parameters.
    Params.setCalculated("dut_alive", '0')

    Params(args.profile)
    Params.setOverrides(args.overrides)

    Params.setDefault('global', 'platform', 'Windows', desc="Operating system platform.", valOptions=["Windows", "Android", "W365", "MacOS"])
    Params.setDefault('global', 'remote_share_path', '')
    Params.setDefault('global', 'remote_share_username', '')
    Params.setDefault('global', 'remote_share_password', '')

    dut_ip   = Params.get('global', 'dut_ip')
    aux_ip   = Params.get('global', 'aux_host')
    platform = Params.get('global', 'platform')

    def call(cmd, method="Run"):
        if target == "dut":
            rpc.call_rpc(dut_ip, 8000, method, cmd)
        else:
            rpc.call_rpc(aux_ip, 8000, method, cmd)

    share_path     = Params.get('global', 'remote_share_path')
    share_username = Params.get('global', 'remote_share_username')
    share_password = Params.get('global', 'remote_share_password')

    if share_path != '' and target == "dut":
        # Only map drives on DUTs.  Aux hosts are expected to have their drives already configured.
        # Disconnect any existing mapping to drive Z: before creating a new one
        call(["cmd.exe", f"/C net use /del z:"])
        call(["cmd.exe", f"/C net use z: {share_path} {share_password} /user:{share_username}"])

    call(["cmd.exe", "/C taskkill /F /T /IM remote.exe"], "RunWithResultAndExitCode")

    args = ""

    if platform.lower() == "w365":
        args = "-topmostWindow"

    call(['C:\\hobl_bin\\remote\\remote.exe', args])


if __name__ == '__main__':
    main()
