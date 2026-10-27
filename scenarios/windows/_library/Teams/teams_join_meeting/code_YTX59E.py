# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import requests
import json
from core.parameters import Params
import time
import cv2 as cv

def run(scenario):
    bots_force_subscribe_resolution = Params.get("teams", "bots_force_subscribe_resolution")
    send_screen = Params.get("teams", "send_screen")
    
    # Check the main bot in a video call to make sure it is sending video.
    # This is to work around a bug in the service that sometimes doesn't send video for bots that also send audio.
    scenario.bots_send_video = Params.get("teams", 'bots_send_video')
    scenario.bots_send_audio = Params.get("teams", 'bots_send_audio')
    scenario.bots_share_screen = Params.get("teams", 'bots_share_screen')
    scenario.server_url = Params.get("teams", "server_url")
    scenario.access_key = Params.get("teams", "access_key")
    scenario.bot_uris = Params.get("teams", "bot_uris")
    scenario.bot_names = Params.get("teams", "bot_names")
    scenario.meeting_url = Params.get("teams", "meeting_url")
    # Don't retrieve meeting_time from Params, as it is modified within the scenario object in the create meeting code.

    if scenario.bots_send_video == "1":
        logging.info("Checking if main bot is sending video.")
        for attempt in range(1, 11):
            if check_bot(scenario):
                logging.info("Bot successfully added and verified.")
                break
            elif attempt == 10:
                logging.error("Failed to add and verify bot after 10 attempts.")
                raise Exception("Failed to add and verify bot after 10 attempts.")
            else:
                remove_bot(scenario)
                add_bot(scenario)
                time.sleep(10)

    # Force subscription resolution based on bot count and screen sharing status
    scenario.bot_uris = Params.get("teams", "bot_uris") # Retrieve again, after updates
    # decode the JSON string to a Python object
    if isinstance(scenario.bot_uris, str):
        bot_uris = json.loads(scenario.bot_uris)
    
    scenario.bot_names = Params.get("teams", "bot_names")
    # decode the JSON string to a Python object
    if isinstance(scenario.bot_names, str):
        bot_names = json.loads(scenario.bot_names)

    # Get the count of bots
    bot_count = len(bot_uris)
    logging.debug(f"Number of bots: {bot_count}")

    # Determine the correct video resolution to subscribe at
    if bots_force_subscribe_resolution != "0":
        logging.debug(f"Force subscribe resolution set to: {bots_force_subscribe_resolution}")
    else:
        logging.debug(f"Auto-setting subscribe resolution based on bot count: {bot_count}")
        
        if bot_count > 16:
            bots_force_subscribe_resolution = "180"
            logging.debug(f"Auto-setting subscribe resolution to: {bots_force_subscribe_resolution}")
        elif bot_count > 4:
            bots_force_subscribe_resolution = "240"
            logging.debug(f"Auto-setting subscribe resolution to: {bots_force_subscribe_resolution}")
        elif bot_count > 1:
            if send_screen == "1":
                bots_force_subscribe_resolution = "180"
            else:
                bots_force_subscribe_resolution = "360"
            logging.debug(f"Auto-setting subscribe resolution to: {bots_force_subscribe_resolution}")
        else:
            if send_screen == "1":
                bots_force_subscribe_resolution = "180"
            else:
                bots_force_subscribe_resolution = "720"
            logging.debug(f"Auto-setting subscribe resolution to: {bots_force_subscribe_resolution}")


    # Build the request URL
    subscribe_request = scenario.server_url + "/ForceSubscription" + "?code=" + scenario.access_key + "&resolution=" + bots_force_subscribe_resolution    
    bot_data = json.dumps({"botUris" : bot_uris, "botNames" : bot_names}, sort_keys=True)

    logging.debug(bot_data)

    r = requests.post(subscribe_request, data=bot_data) 
    logging.debug(r.status_code)
    logging.debug(r.text)

    # Check and try again on bad response
    attempts = 1
    while (r.status_code != 200 and attempts < 10):
        logging.debug("Bad server response, re-sending request")
        time.sleep(30)
        attempts += 1
        r = requests.post(subscribe_request, data=bot_data) 
        logging.debug(r.status_code)
        logging.debug(r.text)

    # End if bad meeting request return
    if r.status_code != 200:
        logging.error("Unable to Force Video Subscribe! Server Side Error, See Logs for Details")
        # self.hangup()
        # self.tearDown()
        # raise Exception("Unable to Force Video Subscribe! Server Side Error, See Logs for Details")
    

def remove_bot(scenario):
    # Remove "main" bot from meeting.
    # decode the JSON string to a Python object
    if isinstance(scenario.bot_uris, str):
        bot_uris = json.loads(scenario.bot_uris)

    bot_names = Params.get("teams", "bot_names")
    # decode the JSON string to a Python object
    if isinstance(scenario.bot_names, str):
        bot_names = json.loads(scenario.bot_names)

    # find index in bot_names that corresponds to the "Main" bot
    main_bot_index = bot_names.index("Main") if "Main" in bot_names else 0

    # Build Stop request string
    logging.info(f"Removing main bot from meeting: {bot_uris[main_bot_index]}")
    bot_data = json.dumps({"botUris" : [bot_uris[main_bot_index]]}, sort_keys=True)
    stop_request = scenario.server_url + "/StopMeeting" + "?code=" + scenario.access_key

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
    # Check that good meeting was returned
    if r.status_code != 200:
        logging.error("Unable to remove main bot from meeting!")


def add_bot(scenario):
    missing = ["Main"] # Only support main bot for now
    bot_data = []
    for bot_name in missing:
    
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
        logging.info(f"Adding bot {bot_name} to meeting with video: {bot_video}, audio: {bot_audio}, screen share: {bot_screen}")
    
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

    if isinstance(scenario.bot_names, str):
        bot_names = json.loads(scenario.bot_names)
    if isinstance(scenario.bot_uris, str):
        bot_uris = json.loads(scenario.bot_uris)

    # Add new bot URIs to scenario
    if "botUris" in return_data:
        new_uris = return_data["botUris"]
        for j, bot_name in enumerate(missing):
            index = bot_names.index(bot_name)
            bot_uris[index] = new_uris[j]
            logging.info(f"Updated bot URI for {bot_name}: {new_uris[j]}")

    scenario.bot_names = json.dumps(bot_names)
    Params.setParam("teams", "bot_names", scenario.bot_names)
    scenario.bot_uris = json.dumps(bot_uris)
    Params.setParam("teams", "bot_uris", scenario.bot_uris)


def check_bot(scenario):
    screenshot = scenario._capture_screen(None, 0, 0, 1, 1)
    scenario.edge_detect = True
    scenario.edge_blur = True
    scenario.dialation = True
    point, confidence, fail_level = scenario._get_point_by_template("..\\_library\\Teams\\teams_join_meeting\\main_bot.png", screenshot, 0.7, cv.TM_SQDIFF_NORMED, [1.0], offsets=(1.1, -0.1), edge_detect_thresholds=[100, 200])
    logging.info(f"Point: {point}, Confidence: {confidence:.2f}, fail_level: {fail_level:.2f}")
    x = (point[0]) * scenario.dut_coord_scaler
    y = (point[1]) * scenario.dut_coord_scaler
    screen_width, screen_height = scenario._get_screen_size(scenario.current_screen)
    x = x / screen_width
    y = y / screen_height
    img = scenario._capture_screen(None, x, y-0.05, 0.05, 0.05)
    scenario._save_screen("main_bot.png", img)
    # determine average pixel value of img
    avg_pixel_value = img.mean()
    logging.info(f"Average pixel value of captured image: {avg_pixel_value}")

    # Restore values to default
    scenario.edge_detect = True
    scenario.edge_blur = True
    scenario.dialation = True

    if avg_pixel_value < 50 or avg_pixel_value > 200:  # Threshold for determining if the bot is visible
        logging.warning("Bot video not detected on screen.")
        return False
    return True


    
