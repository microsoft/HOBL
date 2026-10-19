# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

# Check battery level and recharge when below specified threshold


from builtins import *
from core.parameters import Params
from core.app_scenario import Scenario
import logging
import os
import json
import csv

class Tool(Scenario):
    '''
    Reports number of bytes transferred over Wi-Fi vs Cellular.
    '''
    module = __module__.split('.')[-1]
    cmd = 'get-netadapterstatistics | select-object -property Name, ReceivedBytes, SentBytes | convertto-json'

    def initCallback(self, scenario):
        self.scenario = scenario
        self.collection_enabled = Params.get('global', 'collection_enabled')

    def testBeginCallback(self):
        if self.collection_enabled != "1":
            return
        result = self._call(["powershell.exe", self.cmd])
        self.data_start = json.loads(result)

    def testEndCallback(self):
        if self.collection_enabled != "1":
            return
        result = self._call(["powershell.exe", self.cmd])
        data = json.loads(result)
        if (type(self.data_start) is list):
            data_cleanup = {item['Name'] : (item['SentBytes'], item['ReceivedBytes']) for item in data}
        else:
            data_cleanup = {data['Name'] : (data['SentBytes'], data['ReceivedBytes'])}

        # Create dir for where results will be stored
        os.makedirs(os.path.join(self.scenario.result_dir, f"{self.module}"), exist_ok=True)
        csv_name = os.path.join(self.scenario.result_dir, f"{self.module}", "net_stats.csv")
        print("Writing CSV file: " + csv_name)
        with open(csv_name, 'w') as csvfile:
            csv_writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
            
            if (type(self.data_start) is list):
                for item in self.data_start:
                    name = item["Name"]
                    try:
                        sent_bytes  = data_cleanup[name][0] - item["SentBytes"]
                        received_bytes  = data_cleanup[name][1] - item["ReceivedBytes"]

                        row_sent = [name + ' SentBytes', sent_bytes]
                        row_recv = [name + ' ReceivedBytes', received_bytes]

                        csv_writer.writerow(row_sent)
                        csv_writer.writerow(row_recv)
                    except:
                        logging.debug(f"net_stat: Name '{name}' not found in ending capture.")
            else:
                name = self.data_start["Name"]
                sent_bytes  = data_cleanup[name][0] - self.data_start["SentBytes"]
                received_bytes  = data_cleanup[name][1] - self.data_start["ReceivedBytes"]

                row_sent = [name + ' SentBytes', sent_bytes]
                row_recv = [name + ' ReceivedBytes', received_bytes]

                csv_writer.writerow(row_sent)
                csv_writer.writerow(row_recv)
           

    def dataReadyCallback(self):
        return
