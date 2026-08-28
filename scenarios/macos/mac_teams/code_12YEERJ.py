# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import json
import requests
from core.parameters import Params
import time

def run(scenario):
    duration = Params.get("teams", "duration")
    number_of_bots = int(Params.get("teams", "number_of_bots"))
    scenario.bots_send_video = Params.get("teams", 'bots_send_video')
    scenario.bots_send_audio = Params.get("teams", 'bots_send_audio')
    scenario.bots_share_screen = Params.get("teams", 'bots_share_screen')
    scenario.meeting_time = Params.get("teams", 'meeting_time')
    scenario.meeting_url = Params.get("teams", 'meeting_url')
    scenario.access_key = Params.get("teams", 'access_key')
    scenario.bots_test_server = Params.get("teams", 'bots_test_server')
    scenario.join_meeting_uri = Params.get("teams", 'join_meeting_uri')
    scenario.bots_force_subscribe_resolution = Params.get("teams", 'bots_force_subscribe_resolution')
    scenario.bot_index = int(Params.get("teams", 'bot_index'))
    
    scenario.bot_uris = Params.get("teams", "bot_uris")
    # decode the JSON string to a Python object
    if isinstance(scenario.bot_uris, str):
        scenario.bot_uris = json.loads(scenario.bot_uris)

    logging.debug("Bot URIs: " + str(scenario.bot_uris))
    
    scenario.bot_names = Params.get("teams", "bot_names")
    # decode the JSON string to a Python object
    if isinstance(scenario.bot_names, str):
        scenario.bot_names = json.loads(scenario.bot_names)
    
    logging.debug("Bot Names: " + str(scenario.bot_names))

    # Select bots server instance
    if scenario.bots_test_server == '0':
        scenario.server_url = "https://teamsbotorchestrator.azurewebsites.net/api"
    else:
        scenario.server_url = "https://teamsbotorchestrator-testing.azurewebsites.net/api"

    # Let play for specified duration
    logging.info("Calling for " + str(duration) + " seconds")

    # TODO: Enable with parameters
    # period = 600
    period = 45
    loops = int(float(duration) / period)
    logging.info("Checking Loops: " + str(loops))

    logging.info("uris before loop: " + str(scenario.bot_uris))
    logging.info("First bot uri: " + str(scenario.bot_uris[0]))
    for i in range(loops):
        # Get participant list
        result = get_participant_list(scenario, scenario.bot_uris[0])
        # If list is empty, or any bot is missing
        if result is None or result == "[]" or not all(bot in result for bot in scenario.bot_names):
            if result is None:
                logging.error("Unable to get participant list from server.")
                scenario._sleep_by(period)
                continue
            if len(result) == 0:
                logging.warning("Participant list is empty")
                for bot in scenario.bot_names:
                    result = get_participant_list(scenario, scenario.bot_uris[scenario.bot_names.index(bot)])
                    if len(result) > 0:
                        logging.debug(f"Found participants in meeting with bot {bot}: {result}")
                        break
                if len(result) == 0:
                    logging.error("All bots are missing from the meeting")
            
            
            # get the missing bots
            missing = [bot for bot in scenario.bot_names if bot not in result]
            logging.warning(f"Bots missing from meeting: {missing}")
            # Re-Add the missing bots
            new_uris = add_bots_to_meeting(scenario, missing)

            # Update bot URIs
            for j, bot_name in enumerate(missing):
                index = scenario.bot_names.index(bot_name)
                scenario.bot_uris[index] = new_uris[j]
                logging.info(f"Updated bot URI for {bot_name}: {new_uris[j]}")

            if scenario.bots_force_subscribe_resolution != "0":
                    force_subscribe_bots(scenario)

        # sleep for period
        scenario._sleep_by(period)




def get_participant_list(scenario, uri):
    request_string = ""
    request_string += scenario.server_url # Add the URL to the request string
    request_string += ("/GetParticipants" + "?code=" + scenario.access_key)
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
                logging.error("Access key entered:" + scenario.access_key)
                return None

            logging.debug("Bad server response, re-sending request")
            time.sleep(30)
        except Exception as e:
            logging.error(f"Exception getting participant list: {e}")
            time.sleep(30)
    return None

def add_bots_to_meeting(scenario, bot_names):
    bot_data = []
    for bot_name in bot_names:
    
        # Determine if Video, Audio, and Screen Share needed
        if scenario.bots_send_video == "1":
            bot_video = True
        else:
            bot_video = False

        if scenario.bots_send_audio == "1" and bot_name == "Main":
            bot_audio = True
        else:
            bot_audio = False
        
        if scenario.bots_share_screen == "1" and bot_name == "Main":
            bot_screen = True
        else:
            bot_screen = False
        logging.debug(f"Adding bot {bot_name} to meeting with video: {bot_video}, audio: {bot_audio}, screen share: {bot_screen}")
    
        bot_instance = {"BotDisplayName" : bot_name, "StreamVideo" : bot_video, "StreamAudio" : bot_audio, "ScreenShare" : bot_screen}
        bot_data.append(bot_instance)

    bot_data = json.dumps(bot_data, sort_keys=True)

    # Debug
    logging.info("Bot Data to add: " + bot_data)

    request_string = ""
    request_string += scenario.server_url # Add the URL to the request string

    # Debugging info
    logging.debug("Adding new bots to meeting")
    logging.debug("Server URL: " + scenario.server_url)
    logging.debug("Code: " + scenario.access_key)
    logging.debug("Meeting Duration: " + scenario.meeting_time)
    logging.debug("Join Meeting URL: " + scenario.meeting_url)
    logging.debug("bot_data: " + bot_data)
    
    # Add bots to meeting
    request_string += ("/AddBotsToMeeting" + "?code=" + scenario.access_key + "&meetingDurationInMinutes=" + scenario.meeting_time + "&joinMeetingUrl=" + scenario.meeting_url)

    # Send Request to the bot server. Retry as needed.
    attempts = 1
    while attempts < 5:
        r = requests.post(request_string, data=bot_data)
        logging.debug(r.status_code)
        logging.debug(r.text)

        # Good Status return
        if r.status_code == 200:
            break

        elif r.status_code == 401:
            logging.error("Error. 401 Unauthorized. You are not authorized to access the Teams Bots server. Please confirm you have entered your access key correctly.")
            logging.error("Access key entered:" + scenario.access_key)
            break

        logging.debug("Bad server response, re-sending request")
        time.sleep(90)

        attempts += 1

    # End if bad meeting request return
    if r.status_code != 200:
        logging.error("Unable to Start Meeting! Server Error")


    
    # Get new meeting info
    return_data = json.loads(r.content)
    logging.debug(type(return_data))

    # Log bot names and uris for later
    logging.debug("Bot URIs Returned Type: " + str(type(return_data))) 
    logging.debug("Bot URIs Type: " + str(type(scenario.bot_uris)))
    
    return return_data["botUris"]


def force_subscribe_bots(scenario):
    # Force the bots to subscribe to DUT video stream

    # Create force subscribe request string
    subscribe_request = scenario.server_url + "/ForceSubscription" + "?code=" + scenario.access_key + "&resolution=" + scenario.bots_force_subscribe_resolution
    bot_data = json.dumps({"botUris" : scenario.bot_uris, "botNames" : scenario.bot_names}, sort_keys=True)

    logging.debug(bot_data)

    r = requests.post(subscribe_request, data=bot_data) 
    logging.debug(r.status_code)
    logging.debug(r.text)

    # Check and try again on bad response
    attempts = 1
    while (r.status_code != 200 and attempts < 5):
        logging.debug("Bad server response, re-sending request")
        scenario.time.sleep(90)
        attempts += 1
        r = requests.post(subscribe_request, data=bot_data) 
        logging.debug(r.status_code)
        logging.debug(r.text)

    # End if bad meeting request return
    if r.status_code != 200:
        logging.error("Unable to Force Video Subscribe! Server Side Error, See Logs for Details")