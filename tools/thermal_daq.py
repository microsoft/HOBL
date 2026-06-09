# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Template for creating a tool wrapper

from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import socket, select, json
import logging, threading, time
import sys

class DAQSocketClient:
    def __init__(self, host="127.0.0.1", port=5000, timeout=5):
        self.host = host
        self.port = port
        self.chunk_size = 1024  # 1 KB
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.timeout = timeout
        self.client_socket.settimeout(self.timeout)  # Set the timeout for the socket

    def __del__(self):
        self.close()

    def connect(self):
        """Connect to the server."""
        connected = False
        attempts = 0
        while not connected:
            attempts += 1
            try:
                self.client_socket.connect((self.host, self.port))
                connected = True
                print(f"Connected to server at {self.host}:{self.port}")
            except ConnectionRefusedError:
                print("Failed to connect to the server. Is it running?")
                # exit()
                time.sleep(2)  # Wait before retrying
                if attempts >= 5:
                    print("Max connection attempts reached. Exiting.")
                    break
        return connected

    def send_request(self, request_data):
        """Send a JSON request to the server and receive the response."""
        try:
            request_data_encoded = (json.dumps(request_data) + ('#EOM#')).encode("utf-8")  # Append a delimiter to indicate end of message
            self.client_socket.send(request_data_encoded)  # Send the request

            # Use select to check for available data
            response = b""
            while True:
                ready_to_read, _, _ = select.select([self.client_socket], [], [], 2.0)  # Increased timeout to 2 seconds
                if ready_to_read:
                    chunk = self.client_socket.recv(self.chunk_size)
                    if not chunk:  # Connection closed by server
                        break
                    response += chunk
                    if len(chunk) < self.chunk_size:  # Check if last chunk
                        try:
                            decoded = response.decode("utf-8")
                            if decoded.endswith('#EOM#'):
                                break
                        except UnicodeDecodeError:
                            print("Received undecodable response chunk.")
                            continue
                else:
                    print("Socket read timeout.")
                    break

            if not response:
                print("No response received from server.")
                return None

            response = response.decode("utf-8")
            if not response.endswith('#EOM#'):
                print("Incomplete response received.")
                print(f"Raw response: {response}")
                return None

            return json.loads(response[:-5])  # Remove the '#EOM#' delimiter before parsing

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Raw response: {response}")
            return None
        except Exception as e:
            print(f"Error during communication: {e}")
            try:
                print(f"Response data: {response}")
            except:
                pass
            return None

    def close(self):
        """Close the connection to the server."""
        self.client_socket.close()
        print("Connection closed.")

class Tool(Scenario):
    '''
    A tool for reading thermocouple data from a thermal DAQ server.
    '''
    module = __module__.split('.')[-1]
    # Set default parameters
    Params.setDefault(module, 'thermal_daq_host', '127.0.0.1')
    Params.setDefault(module, 'thermal_daq_port', '5000')
    Params.setDefault(module, 'polling_interval', '5')  # in seconds
    Params.setDefault(module, 'channels', None)  # e.g. "1:cpu 2:mem 3:disk"

    # Get parameters
    thermal_daq_host = Params.get(module, 'thermal_daq_host')
    thermal_daq_port = Params.get(module, 'thermal_daq_port')
    polling_interval = int(Params.get(module, 'polling_interval'))  # in seconds
    channel_input = Params.get(module, 'channels')

    output_filename = "thermal_daq_log.trace"
    

    def initCallback(self, scenario):
        # Initialization code
        # Keep a pointer to the scenario that this tools is being run with
        self.scenario = scenario
        logging.info("Thermal DAQ Tool - initializing, associated with scenario: " + self.scenario._module)

        if self.channel_input is None:
            logging.error("No channels specified for thermal DAQ tool.")
            raise ValueError("No channels specified for thermal DAQ tool.")

        # Parse channel input
        self.channels = {}
        self.channel_names = {}
        # bank:channel_number:name, e.g. "1:1:cpu 1:4:mem 2:1:disk"
        logging.debug(f"Channel input: {self.channel_input}")
        for channel in self.channel_input.split(" "):
            chan_info = channel.split(":")
            if len(chan_info) == 2:
                channel_bank = 1
                channel_num, channel_name = chan_info
            elif len(chan_info) == 3:
                channel_bank = chan_info[0]
                channel_num = chan_info[1]
                channel_name = chan_info[2]
            else:
                logging.error(f"Invalid channel format specified: {channel} Use format [bank:]channel_number:channel_name")
                raise ValueError(f"Invalid channel format specified: {channel}")
            

            if not channel_num.isdigit():
                logging.error(f"Invalid channel number specified: {channel_num}:{channel_name}")
                raise ValueError(f"Invalid channel number specified:  {channel_num}:{channel_name}")
            
            if channel_bank not in self.channels:
                self.channels[channel_bank] = []
                self.channel_names[channel_bank] = []

            self.channels[channel_bank].append(int(channel_num))
            self.channel_names[channel_bank].append(channel_name)

        self.record_thread = ThermalRecordThread(self)
        self.cleanup = self.testEndCallback  # Register cleanup function to ensure thread is stopped on exit
        return

    def testBeginCallback(self):
        # result_dir contains the full path to the results directory, and ends in <testname>_<iteration>
        # _module contains just the testname
        logging.info("Starting Thermal DAQ Recording")
        self.record_thread.start()
        return

    def testEndCallback(self):
        logging.info("Stopping Thermal DAQ Recording")
        self.record_thread.stop_event.set()
        self.record_thread.join()
        return

    def dataReadyCallback(self):
        # You can do any post processing of data here.
        # TODO: Implement any data processing/merging here
        logging.info("Merge Thermal Data")
        return
    
    def mergeThermalData(self):
        return

class ThermalRecordThread(threading.Thread):
    def __init__(self, tool):
        threading.Thread.__init__(self)
        self.tool = tool
        self.client = DAQSocketClient(host=tool.thermal_daq_host, port=int(tool.thermal_daq_port))
        self.client.connect()
        self.stop_event = threading.Event()
        self.data_log_file = f"{self.tool.scenario.result_dir}/{self.tool.output_filename}"

        # Set the channel names on the server
        self.set_channel_names(channels=self.tool.channels, channel_names=self.tool.channel_names)

        channel_names = []
        for bank in self.tool.channel_names:
            channel_names.extend(self.tool.channel_names[bank])
        
        # Write the header
        log_line = "Time," + ",".join(channel_names) + "\n"
        with open(self.data_log_file, "a") as f:
            f.write(log_line)

    def run(self):
        start_time = time.time()
        while not self.stop_event.is_set():
            try:
                data = self.get_latest_data(self.tool.channels)
                if data:
                    timestamp = int(time.time() - start_time)
                    log_line = f"{timestamp}," + ",".join(f"{value:.2f}" for value in data) + "\n"
                    # # Flatten the list of data values and format each value individually
                    # formatted_values = [f"{value:.2f}" for sublist in data for value in sublist]
                    
                    with open(self.data_log_file, "a") as f:
                        f.write(log_line)
                time.sleep(self.tool.polling_interval)
            except Exception as e:
                logging.error(f"Error in ThermalRecordThread: {e}")
                logging.warning("Attempting to reconnect to Thermal DAQ server...")
                self.client.close()
                if not self.client.connect():
                    logging.error("Reconnection failed. Stopping Thermal DAQ recording.")
                    break # Optionally break the loop on error if we want to stop recording

        self.client.close()

    def get_channel_names(self, channels):
        data_names = None
        for bank in channels:
            if not isinstance(channels[bank], list):
                channels[bank] = [channels[bank]]

            request = {
                "command": "get_channel_names",
                "channels": channels[bank],
                "bank": bank
                }
            
            response = self.client.send_request(request)
            if response and response.get("status") == "success":
                data = response.get("data", {})
                data_names.append(data.get("channel_names", []))
                
            else:
                logging.error("Failed to get channel names from thermal DAQ server!")
                logging.error(f"Response: {response}")
                raise RuntimeError("Failed to get channel names from thermal DAQ server!")
        return data_names
    
    def set_channel_names(self, channels, channel_names):
        for bank in channels:
            if not isinstance(channels[bank], list):
                channels[bank] = [channels[bank]]
            if not isinstance(channel_names[bank], list):
                channel_names[bank] = [channel_names[bank]]

            request = {
                "command": "set_channel_names",
                "index": channels[bank],
                "names": channel_names[bank],
                "bank": bank
                }
            
            response = self.client.send_request(request)
            if response and response.get("status") == "success":
                logging.info(f"Set channel names for bank {bank} successfully.")
            else:
                logging.error("Failed to set channel names on thermal DAQ server!")
                logging.error(f"Response: {response}")
                raise RuntimeError("Failed to set channel names on thermal DAQ server!")
            
        return True

    def get_latest_data(self, channels):
        data_names = []
        data_values = []
        for bank in channels:
            if not isinstance(channels[bank], list):
                channels[bank] = [channels[bank]]
            
            request = {
                "command": "get_temperature",
                "channels": channels[bank],
                "bank": bank
                }
            
            response = self.client.send_request(request)
            if response and response.get("status") == "success":
                data = response.get("data", {})
                data_names.extend(data.get("channel_names", []))
                data_values.extend(data.get("channel_data", []))

                
            else:
                logging.error("Failed to get data from thermal DAQ server!")
                logging.error(f"Response: {response}")
                # raise RuntimeError("Failed to get data from thermal DAQ server!")
                return None
        return data_values
