# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

from core.parameters import Params
from utilities.open_source.modules import import_run_user_only

def run():
    Params.setCalculated('scenario_section', __package__.split('.')[-1])
    run_user_only()
    Params.setDefault('web_run_minwin', 'load_only', '0', desc='', valOptions=['0', '1'])
    Params.setParam('web', 'tabs', '0')
    return

def run_user_only():
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\file_explorer_launch')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\snipping_tool')
    import_run_user_only('scenarios\\windows\\_library\\enterprise_collab\\type_to_search')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_close')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_excel_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_close')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_outlook_run_minwin')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_close')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_powerpoint_switchto')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_close')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_open')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_run')
    import_run_user_only('scenarios\\windows\\_library\\productivity\\prod_word_switchto')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_amazon_bsg')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_amazon_vacuum')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_google_images_apollo')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_google_images_london')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_google_search_belgium')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_google_search_super_bowl')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_instagram')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_reddit')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_the_verge')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_wikipedia')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_youtube_nasa')
    import_run_user_only('scenarios\\windows\\_library\\web\\site\\web_site_youtube_tos')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_clear_cache')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_new_tab')
    import_run_user_only('scenarios\\windows\\_library\\web\\web_switchto')
    Params.setUserDefault(None, 'web_workload', 'amazonbsg amazonvacuum googleimagesapollo googleimageslondon googlesearchbelgium googlesearchsuperbowl instagram reddit theverge wikipedia youtubenasa youtubetos', desc='Specific websites to run.', valOptions=['amazonbsg', 'amazonvacuum', 'googleimagesapollo', 'googleimageslondon', 'googlesearchbelgium', 'googlesearchsuperbowl', 'instagram', 'reddit', 'theverge', 'wikipedia', 'youtubenasa', 'youtubetos'], multiple=True)
    return
