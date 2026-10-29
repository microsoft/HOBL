# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Record video from the host computer's camera, intended to be a USB-attached web cam

from builtins import str
from builtins import *
from core.parameters import Params
import logging
import sys
import os
import time
import datetime
import threading
import core.call_rpc as rpc
import numpy as np
import cv2
import core.app_scenario
from PIL import Image
import subprocess

class VideoRecordThread(threading.Thread):
    def __init__(self, scenario, cap, out, fps, rotation, show):
        threading.Thread.__init__(self)
        self.scenario = scenario
        self.event = threading.Event()
        self.cap = cap
        self.out = out
        self.fps = fps
        self.rotation = rotation
        self.show = show
        self.setDaemon(True)
        
    def run(self):
        # print("Target FPS = " + str(self.cap.get(cv2.CAP_PROP_FPS)))
        prev = 0
        self.framecount = 0
        start_time = datetime.datetime.now()
        frame_time = (1./self.cap.get(cv2.CAP_PROP_FPS))
        loop = 0
        delta = 0
        # ret, frame = self.cap.read()
        prev = datetime.datetime.now()          
        while not self.event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                return
            
            
            # self.out.write(frame)

            self.framecount = self.framecount + 1
                
            if self.rotation == 180:
                frame = cv2.flip(frame, 0)
                frame = cv2.flip(frame, 1)

            frame_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(frame_out)
            im.save(self.out.stdin, 'JPEG')

            if self.show == "1": 
                cv2.imshow('DUT Camera', frame)
            
            # delay = max(int((frame_time - (datetime.datetime.now() - prev).total_seconds()) * 1000) - 5, 1)
            delay = max(float((frame_time - (datetime.datetime.now() - prev).total_seconds())) - 0.005, 0.001)

            # cv2.waitKey(delay)
            time.sleep(delay)

            prev = datetime.datetime.now()

        duration = (datetime.datetime.now() - start_time).total_seconds()
        
        # print "Last Delta: ", delta
        # print "Last Waitkey: ", ((after - before).total_seconds() * 1000)
        # print "Target Frame Time: " + str(frame_time)
        # print("Frames: " + str(self.framecount) + " Duration: " + str(duration))
        # print("Target FPS: " + str(self.cap.get(cv2.CAP_PROP_FPS)))
        # print("Actual FPS: " + str(self.framecount / duration))


class Tool(core.app_scenario.Scenario):
    '''
    Record a video of the scenario using a camera attached to the Host USB, or an RTSP stream.
    '''
    module = __module__.split('.')[-1]
    Params.setDefault(module, 'camera_num', '0')
    Params.setDefault(module, 'rtsp_url', '')
    Params.setDefault(module, 'camera_name', '')
    Params.setDefault(module, 'fps', '5')
    Params.setDefault(module, 'xres', '1920')
    Params.setDefault(module, 'yres', '1080')
    Params.setDefault(module, 'quality', '25')
    Params.setDefault(module, 'rotation', '0')
    Params.setDefault(module, 'show', "0")

    camera_num = int(Params.get(module, 'camera_num'))
    rtsp_url = Params.get(module, 'rtsp_url')
    camera_name = Params.get(module, 'camera_name')
    fps = Params.get(module, 'fps')
    xres = Params.get(module, 'xres')
    yres = Params.get(module, 'yres')
    quality = Params.get(module, 'quality')
    rotation = int(Params.get(module, 'rotation'))
    show = Params.get(module, 'show')

    already_started = False
    thread = None

    # testBeginEarly allows a scenario to init and begin the tool before the normal start time for tools and power recording.
    #   Example is idle_apps, where we want to record video of the launching of the apps, but the test doesn't really begin until
    #   everything is opened.
    def testBeginEarlyCallback(self, scenario):
        self.initCallback(scenario)
        self.testBeginCallback()
        self.already_started = True

    def initCallback(self, scenario):
        if self.already_started:
            return
        # Can't start video here because it will get started on Kill() routine and won't be able to mark dir _fail if needed.
        self.scenario = scenario
        self.conn_timeout = False
        self.stop_file = self.scenario.result_dir + "\\command_wrapper_stop.txt"
        self.dut_output_path = os.path.join(self.scenario.result_dir, self.module)
        os.makedirs(self.dut_output_path, exist_ok=True)


    def testBeginCallback(self):
        if self.already_started:
            return

        if self.rtsp_url == '':
            # We are using a locally attached USB camera

            self.cap = cv2.VideoCapture(self.camera_num, cv2.CAP_DSHOW)
            
            # Define the codec and create VideoWriter object
            # fourcc = cv2.VideoWriter_fourcc(*'XVID')
            # fourcc = cv2.VideoWriter_fourcc(*'X264')
            fourcc = cv2.VideoWriter_fourcc(*'avc1') # Uses h264 encoding, but without error messages.  Requires openh264-1.8.0-win32.dll in root (hobl) folder.
            # fourcc = cv2.VideoWriter_fourcc(*'VP90')
            # fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            # fourcc = cv2.VideoWriter_fourcc(*'MJPG')

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.xres))
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.yres))
            self.cap.set(cv2.CAP_PROP_FPS, float(self.fps))

            read_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if read_fps != float(self.fps):
                logging.error("Unsupported camera for video_record")
                logging.error(f"Target fps = {self.fps}, camera fps = {read_fps}")
                self.fail()
            
            # self.out = cv2.VideoWriter(self.scenario.result_dir + '\\video_recording.avi', fourcc, self.cap.get(cv2.CAP_PROP_FPS), (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))
            # self.out = cv2.VideoWriter(self.scenario.result_dir + '\\video_recording_' + self.scenario.testname + '.mp4', fourcc, self.cap.get(cv2.CAP_PROP_FPS), (int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))))

            # ffmpeg setup
            self.scenario.ffmpeg_launched = True
            self.out = subprocess.Popen(['downloads\\ffmpeg_win64\\bin\\ffmpeg.exe', '-loglevel', 'quiet', '-y', '-f', 'image2pipe', '-vcodec', 'mjpeg', '-r', self.fps, '-i', '-', '-vcodec', 'h264', '-crf', self.quality, '-r', self.fps, self.dut_output_path + '\\video_recording_' + self.scenario.testname + '.mp4'], stdin=subprocess.PIPE)

            self.thread = VideoRecordThread(self.scenario, self.cap, self.out, self.cap.get(cv2.CAP_PROP_FPS), self.rotation, self.show)

            # Sarting Capture Here
            logging.info("Starting video recording")
            self.thread.start()

            # ~~~ This Code Can Check Max framerate of Camera ~~~
            # num_frames = 1000; # Number of frames to capture
            # print "Capturing " + str(num_frames) + " frames"
            # start = time.time()# Start time
            # # Grab a few frames
            # for i in xrange(0, num_frames) :
            #     ret, frame = self.cap.read()
            # end = time.time() # End time
            # seconds = end - start # Time elapsed
            # print "Time taken : {0} seconds".format(seconds)
            # # Calculate frames per second
            # fps  = num_frames / seconds;
            # print "Estimated frames per second : {0}".format(fps);

        else:
            # We are using an RTSP streaming camera

            if "rtsp" not in self.rtsp_url:
                self.fail("Invalid rtsp_url parameter.  Should be of the form, 'rtsp://[ip]:[port]/[path]'")
            self.scenario.ffmpeg_launched = True
            output_file = self.dut_output_path + '\\video_recording_' + self.scenario.testname + '.mp4'
            cmd = "downloads\\ffmpeg_win64\\bin\\ffmpeg.exe"
            args = "-y -i " + self.rtsp_url + " -acodec copy -vcodec h264 -loglevel quiet -force_key_frames source_no_drop " + output_file
            stop_key = "q"
            self._host_call("powershell.exe utilities\\open_source\\command_wrapper.ps1" + " \"" + cmd + " \'" + args + "\' " + self.stop_file + " " + stop_key + "\"", blocking=False)
            logging.info("RTSP Recording started.")
            time.sleep(0.5)
        self.scenario.video_startTime = time.time()

    def testEndCallback(self):
        return
        
    def dataReadyCallback(self):
        if self.rtsp_url == '':
            try:
                logging.debug("Trying self.thread")
                self.thread
            except NameError:
                logging.debug("Setting thread to None")
                self.thread = None

            if self.thread is not None:
                logging.info("Stopping video recording")
                self.thread.event.set()
                # logging.info("Thread stopped")
                time.sleep(1) # Necessary delay between stopping thread and closing input to prevent EOI issue and program crash
                self.out.stdin.close()
                # logging.debug("Stdin closed")
                self.out.wait()
                # logging.debug("Wait done")
                self.cap.release()
                # logging.debug("Release done")
                # cv2.destroyAllWindows()
                # logging.debug("Windows destroyed")
        else:
            try:
                self._host_call("cmd.exe /C echo q > " + self.stop_file)
                logging.info("RTSP Recording stopped.")
            except:
                pass
        time.sleep(5)

    def testScenarioFailed(self):
        logging.debug("Test failed, cleaning up.")
        self.dataReadyCallback()

    def testTimeoutCallback(self):
        self.dataReadyCallback()
        self.conn_timeout = True

    def cleanup(self):
        logging.debug("Cleanup")
        self.dataReadyCallback()

