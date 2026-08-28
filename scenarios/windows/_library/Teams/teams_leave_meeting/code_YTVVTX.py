# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import json
import requests
import time
from core.parameters import Params

def run(scenario):

    bot_uris = Params.get("teams", "bot_uris")
    # decode the JSON string to a Python object
    if isinstance(bot_uris, str):
        bot_uris = json.loads(bot_uris)
    
    server_url = Params.get("teams", "server_url")
    access_key = Params.get("teams", "access_key")
    number_of_bots = int(Params.get("teams", "number_of_bots"))

    # Log final parameters
    logging.info("FINAL PARAMETERS:")
    logging.info("==========================================")
    logging.info("server_url: " + server_url)
    logging.info("access_key: " + access_key)
    logging.info("bot_uris: " + json.dumps(bot_uris, sort_keys=True))
    logging.info("==========================================")


    # # Checking if bots + DUT was in call by getting the count of participants and making sure it adds up to # of bots + 1
    # result = get_participant_list(scenario, scenario.bot_uris[0])
    # if len(result) - 1 == number_of_bots:
    #     logging.info("All bots and DUT are in the call.")
    # else:
    #     logging.error("Didn't detect all bots and DUT in the call.")
    #     scenario.fail("Didn't detect all bots and DUT in the call.")


    # Build Stop request string
    bot_data = json.dumps({"botUris" : bot_uris}, sort_keys=True)
    stop_request = server_url + "/StopMeeting" + "?code=" + access_key

    r = requests.post(stop_request, data=bot_data) 
    logging.info(r.status_code)

    # Check and try again on bad response
    attempts = 1
    while (r.status_code != 200 and attempts < 5):
        logging.info("Bad server response, re-sending request")
        time.sleep(90)
        attempts += 1
        r = requests.post(stop_request, data=bot_data) 
        logging.info(r.status_code)
        logging.info(r.text)

    # Advance time counter to current time
    scenario._sleep_to_now()

    # Check that good meeting was returned
    if r.status_code != 200:
        logging.error("Unable to Stop Meeting! Server Side Error")
        raise Exception("Unable to Stop Meeting! Server Side Error")

def get_participant_list(server_url, access_key, uri):
    request_string = ""
    request_string += server_url # Add the URL to the request string
    request_string += ("/GetParticipants" + "?code=" + access_key)
    request_data = json.dumps({"botUris" : [uri]}, sort_keys=True)
    logging.debug("Getting participant list for bot URI: " + uri)

    attempts = 1
    while attempts < 5:
        try:
            attempts += 1
            r = requests.post(request_string, data=request_data)
            logging.debug(r.status_code)
            logging.debug(r.text)

            # Good Status return
            if r.status_code == 200:
                return json.loads(r.content)

            elif r.status_code == 401:
                logging.error("Error. 401 Unauthorized. You are not authorized to access the Teams Bots server. Please confirm you have entered your access key correctly.")
                logging.error("Access key entered:" + access_key)
                return None

            logging.debug("Bad server response, re-sending request")
            time.sleep(30)
        except Exception as e:
            logging.error(f"Exception getting participant list: {e}")
            time.sleep(30)
    return None