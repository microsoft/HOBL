# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params


def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('prod_powerpoint_insertpicture', 'image_path', r'abl_docs\Manarola2.png', desc='Relative path of the image to insert', valOptions=[r'abl_docs\Manarola2.png'])
    return


def run_user_only():
    return