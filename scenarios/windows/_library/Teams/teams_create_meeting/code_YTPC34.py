# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import json
import requests
import time
from core.parameters import Params


def run(scenario):
    logging.debug('Executing code block: code_YTPC34.py')

    access_key = Params.get("teams", 'access_key')
    number_of_bots = int(Params.get("teams", 'number_of_bots'))
    bots_send_video = Params.get("teams", 'bots_send_video')
    bots_send_audio = Params.get("teams", 'bots_send_audio')
    bots_share_screen = Params.get("teams", 'bots_share_screen')
    meeting_time = Params.get('teams', 'meeting_time')
    bots_test_server = Params.get('teams', 'bots_test_server')
    duration = Params.get('teams', 'duration')

    # Log all parameters
    # logging.info("FINAL PARAMETERS:")
    # logging.info("==========================================")
    # logging.info("access_key: " + access_key)
    # logging.info("number_of_bots: " + str(number_of_bots))
    # logging.info("bots_send_video: " + bots_send_video)
    # logging.info("bots_send_audio: " + bots_send_audio)
    # logging.info("bots_share_screen: " + bots_share_screen)
    # logging.info("meeting_time: " + meeting_time)
    # logging.info("bots_test_server: " + bots_test_server)
    # logging.info("==========================================")

    max_duration = 43200

    # Validation of test params
    if access_key == "-1" and number_of_bots > 0:
        logging.error("No valid Teams Bots access key provided! Check that profile contains a Teams Bots Access key, or request one from HOBL Support (HOBLsupport@microsoft.com).")
        raise Exception("No Teams Bots Key Provided.")
    if float(duration) > max_duration:
        logging.error("Requested call duration exceeds the limit of " + str(max_duration) + "s.  Attempting to exceed these limits can result in permanent loss of access to bot services for your organization.")
        raise Exception("Requested call duration exceeds the limit of " + str(max_duration) + "s.  Attempting to exceed these limits can result in permanent loss of access to bot services for your organization.")

    if number_of_bots > 0:
        request_string = ""

        # Setting Bot Options
        if bots_send_video == "1":
            bot_video = True
        else:
            bot_video = False
        if bots_send_audio == "1":
            bot_audio = True
        else:
            bot_audio = False
        if bots_share_screen == "1":
            bot_screen = True
        else:
            bot_screen = False

        # Building request object
        bot_list = []
        bot_uris = []
        bot_index = 0
        for x in range(number_of_bots):
            name = "Bot" + str(bot_index)
            if bot_index == 0:
                name = "Main"
            bot_instance = {"BotDisplayName" : name, "StreamVideo" : bot_video, "StreamAudio" : bot_audio, "ScreenShare" : bot_screen}
            bot_index += 1
            
            bot_list.append(bot_instance)
            bot_audio = False   # Set only first bot to send audio, prevents crowded mess
            bot_screen = False  # Set only first bot to screen share
        logging.info(json.dumps(bot_list, sort_keys=True))

        # Select bots server instance
        if bots_test_server == '0':
            server_url = "https://teamsbotorchestrator.azurewebsites.net/api"
        else:
            server_url = "https://teamsbotorchestrator-testing.azurewebsites.net/api"

        # Store the server URL in parameters
        Params.setParam("teams", "server_url", server_url)

        request_string += server_url # Add the URL to the request string


        if meeting_time == "" or meeting_time == "0":
            meeting_time = str(int((float(duration) / 60) + 15)) # Default meeting time is test duration + 15 minutes, to ensure meeting doesn't end before test does. Meeting time is in minutes, duration is in seconds.

        bot_data = json.dumps(bot_list, sort_keys=True)
        logging.debug("Starting new bots meeting for duration: " + str(duration) + " seconds with meeting time of: " + str(meeting_time) + " minutes")
        request_string += ("/StartMeeting" + "?code=" + access_key + "&meetingDurationInMinutes=" + meeting_time)


        # Send Request to the bot server. Retry as needed.
        attempts = 1
        while attempts < 10:
            logging.info("Attempting to start meeting. Attempt #" + str(attempts))
            logging.debug("Request String: " + request_string.replace("code=", "[REDACTED]"))
            logging.debug("Bot Data: " + bot_data)
            # break
            # Send the request to the server
            r = requests.post(request_string, data=bot_data)
            logging.info(r.status_code)
            logging.debug(r.text)

            # Good Status return
            if r.status_code == 200:
                break

            elif r.status_code == 401:
                logging.error("Error. 401 Unauthorized. You are not authorized to access the Teams Bots server. Please confirm you have entered your access key correctly.")
                logging.error("Access key entered:" + access_key)
                break

            logging.info("Bad server response, re-sending request")
            time.sleep(30)
            attempts += 1

        # End if bad meeting request return
        if r.status_code != 200:
            logging.error("Unable to Start Meeting! Server Error")
            # hangup()
            # tearDown()
            raise Exception("Unable to Start Meeting! Server Error")

        
        # Get new meeting info
        return_data = json.loads(r.content)
        logging.info(type(return_data))


        # Log bot names and uris for later 
        bot_uris = return_data["botUris"]
        # json stringify the bot uris for storage
        bot_uris_json = json.dumps(bot_uris, sort_keys=True)
        Params.setParam("teams", "bot_uris", bot_uris_json)
        logging.info(bot_uris_json)

        try:
            bot_names = return_data["botNames"]
            # json stringify the bot names for storage
            bot_names_json = json.dumps(bot_names, sort_keys=True)
            Params.setParam("teams", "bot_names", bot_names_json)
            logging.info(bot_names_json)
        except:
            pass

        # Get the Meeting URL
        meeting_url = return_data["meetingJoinUri"]
        Params.setParam("teams", "meeting_url", meeting_url)
        logging.info(f"Meeting URL: {meeting_url}")
        
        # Log Meeting URL
        JoinMeetingURI = r"msteams:/l/meetup-join/19:" + str(meeting_url.split("meetup-join/19%3a")[-1])
        logging.info(f"JoinMeetingURI: {JoinMeetingURI}")
        Params.setParam("teams", "join_meeting_uri", JoinMeetingURI)
        

        # Log Bot Index
        Params.setParam("teams", "bot_index", str(bot_index))
        # scenario.bot_index = bot_index