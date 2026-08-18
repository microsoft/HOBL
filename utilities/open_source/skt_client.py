# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

'''
This is a socket client for sending messages to a higher level framework.
Set the hobl callback parameters to call this script followed by the command you want to send.

Result contract (drives the process exit code so HOBL can detect failures):
  success -> reply "ok"  (or "OK" once a Get_Data download completes) -> exit 0
  failure -> reply "failed: <reason>" / "timeout" / "error: ..."      -> exit 1

Long-running commands (e.g. Calibrate_Device) keep a single connection open
while the server works and return one final status reply. The -timeout bounds
the wait so a lost or hung reply can't block forever.

Data_Ready is handled locally: the client obtains the completed DAQ run
manifest with List_Data, downloads each file with Get_Data, and writes the run
under the HOBL result directory supplied by the callback.
'''
from builtins import str
from builtins import *
import socket
import sys
import argparse
import json
import os

parser = argparse.ArgumentParser(description='This is a client for testing the callback server. Call this function followed by the command you want to send.')
parser.add_argument('-host', nargs='?', default='localhost', help="The host IP for the server to listen on. Defaults to localhost.")
parser.add_argument('-port', nargs='?', default=9999, help="The port number for the server to listen on. Defaults to 9999.")
parser.add_argument('-timeout', nargs='?', type=float, default=900.0, help="Max seconds to wait for the server's reply (bounds connect + reply). Long-running commands like Calibrate_Device may need the full window; quick commands reply immediately. Defaults to 900.")
parser.add_argument('message', metavar='Message', nargs=argparse.REMAINDER, help='This is the command that you would like to send.')

args = parser.parse_args()
host = args.host
port = int(args.port)
timeout_s = float(args.timeout)

send_msg = " ".join(args.message)
command = args.message[0] if args.message else ""

# Quick commands reply almost instantly, so cap them at a short timeout. This
# makes a misconfigured/unreachable DAQ (wrong IP, app down, firewall) fail in
# seconds instead of hanging for the full -timeout window. Long-running commands
# (Calibrate_Device) and data transfer keep the full -timeout.
QUICK_COMMAND_TIMEOUT = 15.0
QUICK_COMMANDS = {"DAQ_Start", "DAQ_Stop", "DAQ_Reset"}


class Unreachable(Exception):
    """The DAQ host could not be connected to (wrong IP, app down, firewall)."""


print("\nSending:")
print("\tHost:\t\t" + host)
print("\tPort:\t\t" + str(port))
print("\tCommand:\t" + str(send_msg) + "\n")


def _open_socket(target_host, target_port, timeout):
    """Open a TCP connection with a timeout so no call can block forever.
    Connection-phase failures (wrong IP, DAQ down, firewall) are classified as
    Unreachable so they report clearly instead of looking like a reply timeout."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((target_host, target_port))
    except (socket.timeout, ConnectionRefusedError, OSError) as exc:
        s.close()
        raise Unreachable("{}:{} ({})".format(target_host, target_port, type(exc).__name__))
    return s


def send_command(target_host, target_port, message, timeout):
    """Send one command and return the server's single decoded reply."""
    s = _open_socket(target_host, target_port, timeout)
    try:
        s.sendall(message.encode() + '\r\n'.encode())
        return s.recv(1024).decode().strip()
    finally:
        s.close()


def _read_response_header(s):
    header = bytearray()
    while not header.endswith(b"\n"):
        chunk = s.recv(1)
        if not chunk:
            raise ConnectionError("server closed the connection before sending a response header")
        header.extend(chunk)
        if len(header) > 65536:
            raise ValueError("response header is too large")

    header_text = header[:-1].decode("utf-8")
    if header_text.startswith("ERROR "):
        raise RuntimeError(header_text[6:])
    if not header_text.startswith("OK "):
        raise ValueError("invalid response header: {}".format(header_text))

    try:
        return int(header_text[3:])
    except ValueError:
        raise ValueError("invalid payload size in response header: {}".format(header_text))


def request_payload(target_host, target_port, message, timeout):
    """Send a request and return its framed payload."""
    s = _open_socket(target_host, target_port, timeout)
    try:
        s.sendall(message.encode() + '\r\n'.encode())
        payload_size = _read_response_header(s)
        payload = bytearray()
        while len(payload) < payload_size:
            chunk = s.recv(min(65536, payload_size - len(payload)))
            if not chunk:
                raise ConnectionError(
                    "incomplete response: expected {} bytes, received {}".format(
                        payload_size, len(payload)
                    )
                )
            payload.extend(chunk)
        return bytes(payload)
    finally:
        s.close()


def download_file(target_host, target_port, message, dest_path, expected_size, timeout):
    """Download one framed file response and atomically place it at dest_path."""
    s = _open_socket(target_host, target_port, timeout)
    temp_path = dest_path + ".part"
    try:
        s.sendall(message.encode() + '\r\n'.encode())
        payload_size = _read_response_header(s)
        if expected_size is not None and payload_size != expected_size:
            raise ValueError(
                "file size changed: manifest reported {}, server reported {}".format(
                    expected_size, payload_size
                )
            )

        parent_dir = os.path.dirname(dest_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        bytes_received = 0
        with open(temp_path, "wb") as f:
            while bytes_received < payload_size:
                chunk = s.recv(min(65536, payload_size - bytes_received))
                if not chunk:
                    raise ConnectionError(
                        "incomplete file: expected {} bytes, received {}".format(
                            payload_size, bytes_received
                        )
                    )
                f.write(chunk)
                bytes_received += len(chunk)
        os.replace(temp_path, dest_path)
    finally:
        s.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)


def receive_daq_run(target_host, target_port, result_dir, timeout):
    """Pull the latest completed DAQ run into the local HOBL result directory."""
    manifest = json.loads(
        request_payload(target_host, target_port, "List_Data", timeout).decode("utf-8")
    )
    run_name = manifest.get("run_name")
    files = manifest.get("files")
    if not run_name or not isinstance(files, list):
        raise ValueError("invalid DAQ data manifest")
    if run_name != os.path.basename(run_name) or "/" in run_name or "\\" in run_name:
        raise ValueError("invalid DAQ run name in manifest")

    daq_root = os.path.abspath(os.path.join(result_dir, "DAQ", run_name))
    for entry in files:
        relative_path = entry.get("path") if isinstance(entry, dict) else None
        expected_size = entry.get("size") if isinstance(entry, dict) else None
        if not relative_path or not isinstance(expected_size, int) or expected_size < 0:
            raise ValueError("invalid file entry in DAQ data manifest")

        relative_os_path = relative_path.replace("/", os.sep)
        if os.path.isabs(relative_os_path):
            raise ValueError("manifest contains an absolute file path")
        dest_path = os.path.abspath(os.path.join(daq_root, relative_os_path))
        if os.path.commonpath((daq_root, dest_path)) != daq_root:
            raise ValueError("manifest file path escapes the DAQ result directory")

        print("Downloading: {}".format(relative_path))
        download_file(
            target_host,
            target_port,
            "Get_Data {} {}".format(run_name, relative_path),
            dest_path,
            expected_size,
            timeout,
        )

    return "ok"


try:
    if command == "Data_Ready":
        if len(args.message) < 2:
            raise ValueError("Data_Ready requires the HOBL result directory")
        result_dir = " ".join(args.message[1:])
        if not os.path.isdir(result_dir):
            raise ValueError("HOBL result directory does not exist: {}".format(result_dir))
        rcvd_msg = receive_daq_run(host, port, result_dir, timeout_s)
    elif command == "Get_Data":
        if len(args.message) < 3:
            raise ValueError("Get_Data requires a run name and relative file path")
        relative_path = " ".join(args.message[2:])
        destination = os.path.basename(relative_path.replace("/", os.sep))
        download_file(host, port, send_msg, destination, None, timeout_s)
        rcvd_msg = "OK"
    else:
        # All other commands (including the long-running Calibrate_Device) send
        # one command and get back a single status reply. Quick commands use a
        # short timeout so an unreachable DAQ fails fast; Calibrate_Device keeps
        # the full -timeout window.
        cmd_timeout = QUICK_COMMAND_TIMEOUT if command in QUICK_COMMANDS else timeout_s
        rcvd_msg = send_command(host, port, send_msg, cmd_timeout)
except Unreachable as exc:
    rcvd_msg = "unreachable: {}".format(exc)
except socket.timeout:
    rcvd_msg = "timeout"
except Exception as exc:
    rcvd_msg = "failed: {}: {}".format(type(exc).__name__, exc)

print("Sent:     {}".format(send_msg))
print("Received: {}".format(rcvd_msg))
print("\n")

# Exit code drives HOBL success/failure detection (host_call checks for exit 0).
sys.exit(0 if rcvd_msg in ("ok", "OK") else 1)
