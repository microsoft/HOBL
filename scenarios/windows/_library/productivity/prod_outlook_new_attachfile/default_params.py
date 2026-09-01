# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('prod_outlook_new_attachfile', 'file_source', 'Local', desc='Choose whether to attach the file from OneDrive or the local user profile', valOptions=['OneDrive', 'Local'])
    Params.setDefault('prod_outlook_new_attachfile', 'file_path', r'abl_docs\asample.pptx', desc='Relative path of the file to attach', valOptions=[r'abl_docs\asample.pptx', r'abl_docs\FamilyBudget.xlsx', r'abl_docs\test_long_doc.docx'])
    return

def run_user_only():
    return
