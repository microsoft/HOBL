# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import base64
import socket
import json
import argparse
import tarfile
import os
import glob
import logging
import select
import time
import errno

import qoi
from PIL import Image


# Make a JSON RPC call to the specified method
# priority can be "Idle", "BelowNormal", "Normal", "AboveNormal", "High", or "RealTime"
def call_rpc(host, port, method, params, host_ip=None, rpc_callback_port=None, log = True, timeout = 1800, priority="Normal"):
    # Store details in dictionary
    if method == "StartJobWithNotification":
        params.insert(1, priority)
        params.insert(0, rpc_callback_port)
        params.insert(0, host_ip)

    payload = {
        "method": method,
        "params": params,
        "jsonrpc": "2.0",
        "id": "1",
    }

    ret = _call_rpc(host=host, port=port, payload=payload, log=log, timeout=timeout)
    if isinstance(ret, str):
        ret = ret.strip()
    return ret


def _call_rpc(host, port, payload, log = True, timeout = 1800): # 1800
    # TODO: timeout affects amount of data transferred, not jsut time.  We need to find a way to allow tons of data in a short time as well.
    
    # Make socket connection
    # print(datetime.datetime.now(), "call_rpc - timeout=",timeout)
    s = None
    for i in range(3):
        if s:
            s.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        connect_timeout = timeout
        if timeout > 5:
            connect_timeout = 5 * (i + 1)
        s.settimeout(connect_timeout)
        # s.connect((host, port))
        try:
            if log:
                logging.debug(f"Attempting RPC connection to {host}:{port}, try {i+1}/3")
                # print(f"Attempting RPC connection to {host}:{port}, try {i+1}/3")
            s.connect((host, port))
            break
        except socket.timeout as e:
            logging.debug("Socket timeout.")
            if i == 2:
                raise e
            time.sleep(2)
        except OSError as e:
            if e.errno == errno.EISCONN:
                if log:
                    logging.warning("Socket is already connected.")
                    # print("Socket is already connected.")
            elif e.errno == errno.EALREADY:
                if log:
                    logging.warning("Connection already in progress.")
                    # print("Connection already in progress.")
            else:
                if log:
                    logging.warning(f"RPC ERROR: {e} - {payload}")             
                    # print(f"RPC ERROR: {e} - {payload}")      
            if i == 2:
                raise e
            time.sleep(2)
        except socket.error as e:
            if log:
                logging.warning(f"Socket ERROR: {e} - {payload}")             
                # print(f"Socket ERROR: {e} - {payload}")      
            if i == 2:
                raise e
            time.sleep(2)
        except Exception as e:
            if log:
                logging.error(
                    f"RPC connection failed: {e}. payload {payload}",
                    exc_info=True,
                )
                # print(f"RPC connection failed. payload {payload}")
            raise

    # Convert to JSON and send
    request = json.dumps(payload)
    if log:
        logging.debug("sending RPC: " + str(request))
        # print("sending RPC: " + str(request))
    s.sendall(request.encode('utf-8') + b'\r\n')

    # Loop retrieving port number until nothing more can be pulled from buffer
    # Using "select" allows a 1 sec interval to check for ctrl-c interrupts

    # Callback after 30 minutes
    # x = 0
    start_time = time.time()
    result = ""
    # while x <= int(timeout):
    while True:
        r, _, _ = select.select([s], [], [], 1.0)
        if r:
            res = s.recv(1024).decode(errors="ignore")
            if res == "":
                break
            result += res
        if time.time() > (start_time + timeout):
            return "CALLBACK"

    # if x >= int(timeout):
    #     return "CALLBACK"

    # Decode JSON result
    # output = json.loads(result)
    # print output
    # return output["result"]
    return result


def upload(host, port, source, dest):

    if len(glob.glob(source)) == 0:
        logging.error("ERROR:  Source path: " + source + ", not found!")

    # Store details in dictionary
    payload = {
        "method": "Upload",
        "params": [dest, True],
        "jsonrpc": "2.0",
        "id": "1",
    }

    file_port = _call_rpc(host, port, payload)
    output = json.loads(file_port)
    file_port = output["result"]

    # Make socket connection to file port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, file_port))

    # closing the tar record doesn't close sockfile
    # it need to be done manually (so hold a ref to it)
    sockfile = s.makefile("rwb")
    tf = tarfile.open(mode = "w|", fileobj = sockfile)

    for f in glob.glob(source):
        directory = os.path.dirname(os.path.abspath(f))
        filename = os.path.abspath(f).replace(directory + os.path.sep, "")
        tf.add(f, filename)

    tf.close()
    # result = ""
    # while True:
    result = s.recv(1024)
    #     if res == "":
    #         break
    #     result += res
    # print "UPLOAD RESULT: ", result

    # since we already have it, use sockfile readline to read until EOL
    # result = sockfile.readline()
    sockfile.close()
    s.close() #closing sockfile doesn't close underlying socket
    # print "UPLOAD RESULT: ", result


def download(host, port, source, dest):
    # Store details in dictionary
    payload = {
        "method": "Download",
        "params": [source],
        "jsonrpc": "2.0",
        "id": "1",
    }

    file_port = _call_rpc(host, port, payload)
    output = json.loads(file_port)
    logging.debug("Download file: " + str(output))
    if "result" not in output:
        logging.error("Download failed: Error reading file from DUT")
        raise Exception(str(output["error"]))
    file_port = output["result"][0]

    # Make socket connection to file port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, file_port))

    tf = tarfile.open(mode="r|", fileobj=s.makefile('rb', None))
    tf.extractall(path = dest)

    tf.close()


def plugin_load(host, port, dll_id, dll_class, dll_path):
    # Store details in dictionary
    payload = {
        "method": "PluginLoad",
        "params": [dll_id, dll_class, dll_path],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload)
    return result


def plugin_call(host, port, dll_id, method, *arg):
    # Store details in dictionary
    payload = {
        "method":"PluginCallMethod",
        "params": [dll_id, method, *arg],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload)
    return result


def plugin_screenshot(host, port, dll_id, x=0.0, y=0.0, w=1.0, h=1.0, screenIndex=0):
    # Store details in dictionary
    payload = {
        "method":"PluginCallMethod",
        "params": [dll_id, "Screenshot", x, y, w, h, screenIndex],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload)
    # print("RESULT: " + result)
    result_dict = json.loads(result)
    if "result" in result_dict:
        data = result_dict["result"]
        img = base64.b64decode(data)
        return img
    else:
        print(" ERROR Unexpected response from plugin_screenshot()")
        print(result_dict)
        return ""


def plugin_continuous_screenshot(host, port, dll_id, x=0, y=0, w=10, h=10, outputDir="", screenIndex=0, time_ms=1000, framerate=60):
    # Store details in dictionary
    payload = {
        "method":"PluginCallMethod",
        "params": [dll_id, "ContinuousScreenshot", x, y, w, h, outputDir, screenIndex, time_ms, framerate],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload)
    if result == "CALLBACK":
        print("ERROR: Timeout occurred during RPC call in plugin_continuous_screenshot()")
        return ""
    # print("RESULT: " + result)
    result_dict = json.loads(result)
    if "result" in result_dict:
        data = result_dict["result"]
        return data
    else:
        print(" ERROR Unexpected response from plugin_continuous_screenshot()")
        print(result_dict)
        return ""


def plugin_write_captures_to_disk(host, port, dll_id, capture_dir):
    payload = {
        "method":"PluginCallMethod",
        "params": [dll_id, "WriteCapturesToDisk", capture_dir],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload)
    result_dict = json.loads(result)
    if "result" in result_dict:
        data = result_dict["result"]
        return data
    else:
        print(" ERROR Unexpected response from plugin_write_capture_to_disk()")
        print(result_dict)
        return ""


def plugin_stop_performance_capture(host, port, dll_id):
    payload = {
        "method":"PluginCallMethod",
        "params": [dll_id, "StopCapture"],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload)
    result_dict = json.loads(result)
    if "result" in result_dict:
        data = result_dict["result"]
        return data
    else:
        print(" ERROR Unexpected response from plugin_stop_performance_capture()")
        print(result_dict)
        return ""


def plugin_clear_captures(host, port, dll_id):
    payload = {
        "method":"PluginCallMethod",
        "params": [dll_id, "ClearCaptures"],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload)
    result_dict = json.loads(result)
    if "result" in result_dict:
        data = result_dict["result"]
        return data
    else:
        return ""


def plugin_screen_info(host, port, dll_id):
    # Store details in dictionary
    payload = {
        "method":"PluginCallMethod",
        "params": [dll_id, "GetScreenInfo"],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload)
    print("RESULT: " + result)
    result_dict = json.loads(result)
    data = result_dict["result"]
    # Expected format: "width,height,scale;" for each monitor
    displays = data.rstrip(',;').split(';')
    if len(displays) == 0:
        print("ERROR: No displays found in plugin_screen_info()")
        return []
    for display in displays:
        info = display.split(',')
        if len(info) != 3:
            print("ERROR: Invalid display info format in plugin_screen_info()")
            return []
        # Expected format: "width,height,scale"
        if not (info[0].isdigit() and info[1].isdigit() and info[2].replace('.', '', 1).isdigit()):
            print("ERROR: Non-numeric values found in plugin_screen_info()")
            return []
    # Return displays in a list of tuples
    return [(int(info.split(',')[0]), int(info.split(',')[1]), float(info.split(',')[2])) for info in displays]


def get_job_result(host, port, jobid, log=True):
    # Store details in dictionary
    payload = {
        "method": "GetJobResultEx",
        "params": [jobid],
        "jsonrpc": "2.0",
        "id": "1",
    }
    result = _call_rpc(host, port, payload, log=log)
    # output = json.loads(result)
    # file_port = output["result"]
    return result


if __name__ == "__main__":
    # Define command line arguments
    parser = argparse.ArgumentParser(description='This is a client for sending JSON RPC requests to a server.')
    parser.add_argument('-host', nargs='?', default='localhost', help="The host IP for the server to listen on. Defaults to localhost.")
    parser.add_argument('-port', nargs='?', default=8000, help="The port number for the server to listen on. Defaults to 8000.")
    parser.add_argument('-method', nargs='?', default="", help="The remote method to invoke.")
    parser.add_argument('params', metavar='Message', nargs=argparse.REMAINDER, help='The parameters to the method, separated by space.')
    args = parser.parse_args()

    output = call_rpc(args.host, int(args.port), args.method, args.params)
    print (output)