# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

import logging
import configparser
import collections
import re
import core.call_rpc as rpc
import json
from datetime import date
import socket
import subprocess
import winreg
import csv
import os

class Params(object):

    defaults = collections.OrderedDict()
    defaultsInfo = collections.OrderedDict()
    overrides = collections.OrderedDict()
    fileParams = collections.OrderedDict()
    calculated = collections.OrderedDict()
    resolved = collections.OrderedDict()
    associated_sections = collections.OrderedDict()
    params = configparser.RawConfigParser()
    recurse_level = 1

    def __init__(self, cfgfile):
        # Read config file
        # Params.params = configparser.RawConfigParser()
        Params.params.optionxform = str
        if cfgfile != "":
            Params.params.read(cfgfile)
        for section in Params.params.sections():
            # print(f"Reading ini section: {section}")
            for item in Params.params.items(section):
                key = item[0]
                val = item[1]
                if section not in Params.fileParams:
                    Params.fileParams[section] = collections.OrderedDict()
                Params.fileParams[section][key] = val

    @classmethod
    def setOverrides(cls, override_list):
        for tuple in override_list:
            try:
                (section_key, val) = tuple.split('=', 1)
            except Exception as e:
                print(" ERROR - Bad parameter format: " + tuple)
                raise e
            res = section_key.split(':', 1)
            if len(res) == 1:
                # If section not specified, find a match from defaults
                key = res[0]
                section = Params.getSectionForKey(key)
                # print(f" INFO - Got section {section} for key {key}")
            elif len(res) == 2:
                section = res[0]
                key = res[1]
            else:
                print(" ERROR - Bad parameter format: " + section_key)
                raise
            if section != "":
                Params.setOverride(section, key, val)


    @classmethod
    def setOverride(cls, section, key, val):
        val = val.strip('"')
        if section not in Params.overrides:
            Params.overrides[section] = collections.OrderedDict()
        base_val = Params.get_raw(section, key, False, recurse_init = True)
        if base_val == None:
            base_val = ""
        if len(val) > 0 and val[0] == "+" and key in ["tools", "prep_tools"]:
            new_val = " ".join(dict.fromkeys((base_val + " " + val[1:]).split()))
            Params.overrides[section][key] = new_val
        elif len(val) > 0 and val[0] == "-" and key in ["tools", "prep_tools"]:
            new_val = val[1:]
            # Split into individual tools, because they can be in any order
            base_val_ary = base_val.split()
            new_val_ary = new_val.split()
            final_val_ary = []
            for bv in base_val_ary:
                if bv not in new_val_ary:
                    final_val_ary.append(bv)
            Params.overrides[section][key] = " ".join(final_val_ary)
        else:
            Params.overrides[section][key] = val


    @classmethod
    def setParam(cls, section, key, val):
        val = val.strip('"')

        # If section is None, find an existing section from defaults, else set to module
        if section == None:
            section = Params.getSectionForKey(key)

        if section not in Params.fileParams:
            Params.fileParams[section] = collections.OrderedDict()
        base_val = Params.get_raw(section, key, False, recurse_init = True)
        if base_val == None:
            base_val = ""
        if len(val) > 0 and val[0] == "+" and key in ["tools", "prep_tools"]:
            new_val = " ".join(dict.fromkeys((base_val + " " + val[1:]).split()))
            Params.fileParams[section][key] = new_val
        elif len(val) > 0 and val[0] == "-" and key in ["tools", "prep_tools"]:
            new_val = val[1:]
            # Split into individual tools, because they can be in any order
            base_val_ary = base_val.split()
            new_val_ary = new_val.split()
            final_val_ary = []
            for bv in base_val_ary:
                if bv not in new_val_ary:
                    final_val_ary.append(bv)
            Params.fileParams[section][key] = " ".join(final_val_ary)
        else:
            Params.fileParams[section][key] = val


    @classmethod
    def getSectionForKey(cls, key):
        # First check global
        val = Params.getDefault("global", key)
        if val:
            return "global"
        
        # Then check module
        module = Params.get_raw("global", "module_name")
        val = Params.getDefault(module, key)
        if val:
            return module
        
        # Then check everything else
        for section in Params.defaults:
            val = Params.getDefault(section, key)
            if val:
                return section

        # If still not found, set to module or global when module is unknown
        return module or "global"


    @classmethod
    def deleteParam(cls, section, key):
        if section not in Params.fileParams:
            return
        if key not in Params.fileParams[section]:
            return
        del Params.fileParams[section][key]


    @classmethod
    def setDefault(cls, section, key, val, desc = "", valOptions = [], multiple = False):
        if section not in Params.defaults:
            Params.defaults[section] = collections.OrderedDict()
        Params.defaults[section][key] = val

        if section not in Params.defaultsInfo:
            Params.defaultsInfo[section] = collections.OrderedDict()
        Params.defaultsInfo[section][key] = {
            "desc": desc,
            "valOptions": valOptions,
            "multiple": multiple
        }


    @classmethod
    def setUserDefault(cls, section, key, val, desc = "", valOptions = [], multiple = False):
        if section is None:
            section = Params.getCalculated('scenario_section')

        if not section:
            return

        Params.setDefault(section, key, val, desc, valOptions, multiple)


    @classmethod
    def setCalculated(cls, key, val):
        Params.calculated[key] = val

    @classmethod
    def dump(cls):
        for section in Params.fileParams:
            for key in Params.fileParams[section]:
                # Check if in overrides
                if section in Params.overrides:
                    if key in Params.overrides[section]:
                        continue
                if 'password' in key.lower():
                    continue
                val = Params.fileParams[section][key]
                logging.debug("File - " + section + " : " + key + " = " + val)
        for section in Params.overrides:
            for key in Params.overrides[section]:
                if 'password' in key.lower():
                    continue
                val = Params.overrides[section][key]
                logging.debug("Override - " + section + " : " + key + " = " + val)

    @classmethod
    def dumpDefault(cls):
        for section in Params.defaults:
            for key in Params.defaults[section]:
                val = Params.defaults[section][key]
                print(section + ":" + key)

    @classmethod
    def dumpDefaultWithInfo(cls, print_json=True):
        for section in Params.defaultsInfo:
            for key in Params.defaultsInfo[section]:
                valOptions = Params.defaultsInfo[section][key]["valOptions"]

                if len(valOptions) == 1 and valOptions[0].startswith("@\\"):
                    d = os.path.join(os.getcwd(), valOptions[0][2:])

                    for root, dirs, files in os.walk(d):
                            valOptions.extend(files)

                    del valOptions[0]

                Params.defaultsInfo[section][key]["valOptions"] = valOptions

        if print_json:
            print(json.dumps(Params.defaultsInfo))

    @classmethod
    def dumpResolved(cls):
        section_list = []
        for section in Params.fileParams:
            section_list.append(section)
        for section in Params.overrides:
            if section not in section_list:
                section_list.append(section)
        for section in section_list:
            key_list = []
            if section in Params.fileParams:
                for key in Params.fileParams[section]:
                    key_list.append(key)
            if section in Params.overrides:
                for key in Params.overrides[section]:
                    if key not in key_list:
                        key_list.append(key)
            for key in key_list:
                val = Params.get(section, key, log=False)
                logging.debug("Resolved - " + str(section) + " : " + str(key) + " = " + str(val))

    @classmethod
    def getCalculated(cls, key):
        try:
            val = Params.calculated[key]
        except:
            val = ""
        return val


    @classmethod
    def get(cls, section, key, log = True, recurse_init = True):
        # print(f" INFO get - {section}:{key}, Recurse init: {recurse_init}")
        val = Params.get_raw(section, key, log, recurse_init = recurse_init)
        # print(f" INFO get - get_raw returned {val}")
        if key == "host_ip" and val == "":
            val = Params.resolveHostIp()
            if (val == None):
                return None
            # print("Setting override: " + section + " " + key + " " + val)
            Params.setOverride(section, key, val)
        return Params.resolveVars(val)


    @classmethod
    def get_raw(cls, section, key, log = True, recurse_init=False):
        if recurse_init:
            cls.recurse_level = 1
        else:
            cls.recurse_level += 1
        # print(f" INFO get_raw - {section}:{key}, Recurse level: {cls.recurse_level}")
        if cls.recurse_level >= 20:
            error_str = f"Circular reference found for parameter {key}"
            if log:
                logging.error(error_str)
            raise Exception(error_str)

        if section == None:
            # If section not specified, first see if scenario parameter exists
            scenario = Params.getCalculated('scenario_section')
            val = Params.get_raw(scenario, key, log, recurse_init)
            if val == None:
                # If not, try global parameter
                val = Params.get_raw('global', key, log, recurse_init)
                # print(f" INFO get_raw - global:{key} = {val}")
            if val:
                return val
            else:
                return None

        # First check specified section
        if section in Params.overrides:
            if key in Params.overrides[section]:
                val = Params.overrides[section][key]
                # print(f"Returning override {section} {key} {val}")
                return val
        if section in Params.fileParams:
            if key in Params.fileParams[section]:
                val = Params.fileParams[section][key]
                # print(f"Returning file {section} {key} {val}")
                return val
        # Else check defaults
        if section in Params.defaults:
            # print(f"Checking section {section}")
            if key in Params.defaults[section]:
                val = Params.defaults[section][key]               
                # print(f"Returning default {section} {key} {val}")
                return val
        return None

    @classmethod
    def getKeysForSection(cls, section):
        keys = []
        # Check defaults
        if section in Params.defaults:
            for key in Params.defaults[section]:
                keys.append(key)
        # Check params file
        if Params.params.has_section(section):
            for key in Params.fileParams[section]:
                if key not in keys:
                    keys.append(key)
        # Check command line overrides
        if section in Params.overrides:
            for key in Params.overrides[section]:
                if key not in keys:
                    keys.append(key)
        return keys

    @classmethod
    def getOverride(cls, section, key, log = True):
        # Check command line overrides
        val = None
        if section in Params.overrides:
            if key in Params.overrides[section]:
                val = Params.overrides[section][key]
        return Params.resolveVars(val)

    @classmethod
    def getDefault(cls, section, key):
        if section in Params.defaults:
            if key in Params.defaults[section]:
                val = Params.defaults[section][key]
                # print(f" INFO - getDefault returning {val} for {section}:{key}")
                return val
        return None

    @classmethod
    def getDefaults(cls, section):
        try:
            return Params.defaults[section]
        except:
            return dict()


    @classmethod
    def getFileParams(cls, section = None):
        if section == None:
            return Params.fileParams

        try:
            return Params.fileParams[section]
        except:
            return dict()


    @classmethod
    def getOverrides(cls, section = None):
        if section == None:
            return Params.overrides
            
        try:
            return Params.overrides[section]
        except:
            return dict()


    @classmethod
    def setAssociatedSections(cls, section, list):
        Params.associated_sections[section] = list

    @classmethod
    def getAssociatedSections(cls, section):
        if section in Params.associated_sections:
            return(Params.associated_sections[section])
        else:
            return([])


    @classmethod
    def clear(cls):
        Params.overrides.clear()
        Params.fileParams.clear()
        Params.defaults.clear()
        Params.defaultsInfo.clear()


    @classmethod
    def clearOverrides(cls):
        Params.overrides.clear()


    @classmethod
    def clearFileParams(cls):
        Params.fileParams.clear()


    ''' Checks if parameters are valid. Returns False if not '''
    @classmethod
    def checkParams(cls):
        for key,value in Params.overrides.items():
            if key in Params.defaults and value in Params.defaults[key]:
                continue
            return False
        for key,value in Params.fileParams.items():
            if key in Params.defaults and value in Params.defaults[key]:
                continue
            return False
        dut_name = Params.defaults['dut_name']
        if re.match("^[A-Za-z0-9_]+$", dut_name)== False:
            return False
        return True

    @classmethod
    def resolveHostIp(cls):
        # Get all host interface IP addresses
        interfaces = socket.gethostbyname_ex(socket.gethostname())[2]
        # If only one interface, return it
        # print (interfaces)
        if (interfaces == None or len(interfaces) == 0):
            # print("resolveHostIp: No interfaces found.")
            return ""
        if (len(interfaces) == 1):
            # print("resolveHostIp: Found only host_ip " + interfaces[0])
            return interfaces[0]
        # If multiple interfaces, find the first one that matches the domain of the dut_ip
        dut_ip = Params.get('global', 'dut_ip')
        # print("dut_ip: " + dut_ip)
        if (not dut_ip.replace('.', '').isnumeric()):
            # dut_ip is a name and we need to get its IP address
            # print("resolveHostIp: Resolving dut_ip name from " + dut_ip)
            response = host_call("ping " + dut_ip + " -4 -n 1")
            search_result = re.search(r'\[.+\]', response)
            if (search_result != None):
                dut_ip = search_result.group(0).strip('[]')
                # print("resolveHostIp: Resolving dut_ip name to " + dut_ip)
            else:
                print(" ERROR - resolveHostIp: Could not find device " + dut_ip + " on the netowork.")

        for host_ip in interfaces:
            if host_ip.split('.')[:2] == dut_ip.split('.')[:2]:
                # print("resolveHostIp: Found match " + host_ip)
                return host_ip


    @classmethod
    def resolveVars(cls, original):
        # Substitute any specified parameters into parameter, indicated by square brackets
        if original == None:
            return None
        search_results = re.findall(r'\[[\w:]+\]', original)
        for match in search_results:
            name = match.strip('[]')

            # Check if this name has already been resolved.  If so, so just use the cached value.
            if name in Params.resolved:
                val = Params.resolved[name]
                original = original.replace(match, val)
                # print("resolveVars() returning cached entry for ", match, val)
                continue

            if name == "DATE":
                val = date.isoformat(date.today())
                continue

            # print(f" INFO resolveVars - calling get_raw(None, {name})")
            val = Params.get_raw(None, name, log = False, recurse_init = False)

            if val == None: 
                # new key value
                val = find_val(name)
            else:
                # either 
                # print (f"Key Name: {name}")
                # print(f" INFO resolveVars2 - calling get(None, {name})")
                val_new = Params.get(None, name, log = False, recurse_init = False)
                if val_new != None:
                    reg_write(name, val_new)
                    val = val_new
                else:
                    val = val.strip('[]')
                    val = find_val(val)
                    reg_write(name, val)

            if val == None:
                print(" ERROR - parameter variable '" + name + "' could not be resolved.")
                val = "Undefined"
            original = original.replace(match, val)
            Params.resolved[name] = val
        return original

    @classmethod
    def expandStudyVars(cls):
        path = ""
        vars = Params.getKeysForSection("study_vars")
        for var in vars:
            val = Params.get("study_vars", var)
            path += "\\" + var + "-" + val
        return path

def find_val(name):
    val = "Undefined"
    if Params.getCalculated("dut_alive") == '0':
        val = reg_read(name)
        return val
    # print("Finding parameter: ", name)
    if name == "LKG":
        val = call(['cmd.exe', r'/C reg.exe QUERY "HKEY_LOCAL_MACHINE\Software\Microsoft\Surface\OSImage" /v ImageVersion'])
        if val==None:
            val = call(['cmd.exe', r'/C reg.exe QUERY "HKEY_LOCAL_MACHINE\Software\Microsoft\Surface\OSImage" /v ImageVersion /reg:64'])
        if val != None:
            val = val.split(' ')[-1]
    elif name == "DUT_NAME":
        # val = call(['powershell.exe', '(Get-WmiObject -Class Win32_ComputerSystem).name'])
        val = call(['cmd.exe', '/C hostname'])
        # if val != None:
        #     val = val.split('-')[-1]
    elif name == "DUT_ARCHITECTURE":
        val = call(['cmd.exe', r'/C reg.exe QUERY "HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment" /v Processor_Architecture'])
        if val != None:
            val = val.split(' ')[-1]
            val = val.lower()
            if val == "amd64" :
                val = "x64"
    # elif name == "PRODUCT_OEM":
    #     # Obsolete
    #     val = call(['cmd.exe', r'/C reg.exe QUERY HKEY_LOCAL_MACHINE\Software\Microsoft\Surface\OSImage /v "ImageProductName"'])
    #     if val != None:
    #         val = val.split(' ')[-1]
    #     else:
    #         val = "Undefined"
    #     print("PRODUCT_OEM: ", val)
    elif name == "PRODUCT":
        val = find_product_name()
        print("  PRODUCT: ", val)
    elif name == "WINDOWS_VERSION":
        # val = call(['cmd.exe', r'/C reg.exe QUERY HKEY_LOCAL_MACHINE\Software\Microsoft\Surface\OSImage /v "ImageName"'])
        # if val != None:
        #     val1 = val.split(' ')[-1].split('.')[1].split('_')
        #     if len(val1) == 3:
        #         val = val1[1] + "_" + val1[2]
        #     elif len(val1) == 2:
        #         val = val1[1]
        #     elif len(val1) == 5: # OEMVL.dev_21h2_noFW_SV2_vm.1.1045.0.wim
        #         val = val1[3    ] # SV2
        #     else:
        #         val = val1[0]
        val = call(['cmd.exe', r'/C reg.exe query "HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion" /v DisplayVersion'])
        if val != None:
            val = val.split(' ')[-1]
    elif name == "DISPLAY_RESOLUTION":
        val1 = call(['powershell.exe', '(Get-WmiObject -Class Win32_videocontroller).CurrentHorizontalResolution'])
        val2 = call(['powershell.exe', '(Get-WmiObject -Class Win32_videocontroller).CurrentVerticalResolution'])
        if val1!=None and val2!=None:
            val = val1 + 'x' + val2
    elif name == "screen":
        val = find_screen()
    elif name == "mobility":
        val = find_mobility()
    elif name == "gpu":
        val = call(['powershell.exe', "(Get-WmiObject Win32_PnPSignedDriver | % {if ($_.DeviceClass -like 'DISPLAY'){$_.Manufacturer}})"], timeout = 15)
        if val == None :
            val = call(['powershell.exe', '"(Get-WmiObject Win32_PnPSignedDriver | % {if ($_.DeviceClass -like \'DISPLAY\'){$_.Manufacturer}})"'], timeout = 15)
            if val == None:
                return val
        # if "Intel" in val or "Qualcomm" in val :
        if "nvidia" in val.lower():
            val = "dGPU"
        else:
            val = "iGPU"
    elif name == "NITS_MAP":
        val = find_goals_val(nits_map=True)
    elif name == "VOLUME":
        val = find_goals_val(volume=True)
    elif name == "WINDOWS_BUILD":
        val1 = call(['cmd.exe', r'/C reg.exe QUERY "HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion" /v "CurrentBuild"'])
        try:
            val = val1.split(' ')[-1]
        except:
            val = "Undefined"
    elif name == "WINDOWS_UBR":
        val1 = call(['cmd.exe', r'/C reg.exe QUERY "HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion" /v "UBR"'])
        try:
            val = val1.split(' ')[-1]
        except:
            val = "Undefined"
    elif name == "OS_BUILD":
        val1 = call(['cmd.exe', r'/C reg.exe QUERY "HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion" /v "CurrentBuild"'])
        val2 = call(['cmd.exe', r'/C reg.exe QUERY "HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion" /v "UBR"'])
        if val1!=None and val2!=None:
            val = val1.split(' ')[-1] + "." + val2.split(' ')[-1]
    elif name == "EDGE_CANARY_BUILD":
        val = call(['powershell.exe', r'[System.Diagnostics.FileVersionInfo]::GetVersionInfo("""$env:userprofile\appdata\local\microsoft\edge sxs\application\msedge.exe""").FileVersion'])
    elif name == "WEEK":
        today = date.today()
        val = today.strftime("%Y.%U")
    elif name == "RAIL_CAR_ID":
        val = call(['cmd.exe', r'/C reg.exe QUERY "HKEY_LOCAL_MACHINE\Software\Microsoft\Surface\OSImage" /v RailCarID'])
        if val != None:
            val = val.split(' ')[-1]
    elif name == "PLATFORM":
        dut_ip = Params.get('global', 'dut_ip')
        result = rpc.call_rpc(dut_ip, 8000, "RunWithResultAndExitCode", ["uname"], log = False)
        if result == "TIMEOUT":
            return val
        if "result" in json.loads(result):
            val = "MacOS"
        else:
            val = "Windows"
    else:
        # we should not hit this line
        print(" ERROR - [" + name + "] is not a supported variable name.")
        val = "Undefined"
    
    if val == None:
        val = "Undefined"
    reg_write(name,val)
    
    return val

def reg_read(sub_key):
    dut_name = Params.get('global', "dut_name", log = False)
    key = r"Software\Microsoft\HOBL\\" + dut_name
    if sub_key.islower():
        sub_key = "_" + sub_key
    try:
        aReg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        aKey = winreg.OpenKey(aReg, key, 0, winreg.KEY_READ)
        val = winreg.QueryValueEx(aKey, sub_key)[0]
        return val
    except:
        return "Undefined"

def reg_write(sub_key, val):
    dut_name = Params.get('global', "dut_name", log = False)
    key = "Software\\Microsoft\\HOBL\\" + dut_name
    if sub_key.islower():
        sub_key = "_" + sub_key
    try:   
        aReg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        aKey = winreg.CreateKeyEx(aReg, key, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(aKey, sub_key, 0, winreg.REG_SZ, val)
    except Exception as e:                                          
        print("Encountered problems writing into the Registry: " + key + ", " + sub_key + ", " + str(val))
        print(e)

def reg_clean(sub_key):
    dut_name = Params.get('global', "dut_name", log = False)
    key = "Software\\Microsoft\\HOBL\\" + dut_name
    if sub_key.islower():
        sub_key = "_" + sub_key
    try:
        aReg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        aKey = winreg.OpenKey(aReg, key, 0, winreg.KEY_WRITE)
        winreg.DeleteValue(aKey, sub_key)
        return True
    except:
        return False

def call(command, cwd = ".", timeout = 10):
    result = None
    print("  Calling: ", command)
    try:
        if Params.get_raw('global', "local_execution", log = False, recurse_init = True) == '1':
            cmd_str = " ".join(command)
            result = host_call(cmd_str)
            result = result.strip()
            if result == "":
                result = None
        else:
            dut_ip = Params.get('global', 'dut_ip')
            output = rpc.call_rpc(dut_ip, 8000, "RunWithResult", command, log = False, timeout = timeout)
            deserialized_output = json.loads(output)
            if "result" in deserialized_output:
                result = deserialized_output["result"].strip()
                print(result)
                if "Exception" in result or "ERROR" in result:
                    result = None
            else:
                result = None
    except:
        pass
    return result

def host_call(command, cwd = "."):
    p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell = True, cwd = cwd)
    out, err = p.communicate()
    # for line in out.split(b'\n'):
    #     logging.info(line.decode().rstrip())
    # for line in err.split(b'\n'):
    #     l = line.decode()
        # if l:
        #     logging.error(l.rstrip())
    # return(out.decode().rstrip())
    return(out.decode())

def find_goals_val(nits_map=False, volume=False):
    goals = Params.get('global', "goals", log = False)
    if goals == None:
        print(" ERROR - 'goals' parameter not specified.")
        return None
    module_name = (Params.get('global', 'module_name', log=False)).lower()
    # if module_name not in ["lvp", "cs_floor_local", "idle_desktop_nc_local", "abl", "abl_qgate"]:
    #     module_name = "default"
    
    if not os.path.isfile(goals):
        print(" ERROR - specified goals file not found: ", goals)
        return None
        # goals = Params.get_raw('global', "goals", log = False)
        # goals_dir = os.path.dirname(goals)
        # goals = goals_dir + "\\Rundown_OEMxx_goals.csv"
        
    with open(goals, "r") as file:
        f = csv.DictReader(file)
        func = lambda x : x if (x.isdigit()) else x[1::]
        for lines in f:
            if nits_map==True and lines["Metric"]=="Run Start Screen Brightness (%)":
                if "lvp" in lines:
                    nits100 = func(lines["lvp"])
                elif "default" in lines:
                    nits100 = func(lines["default"])
                else:
                    nits100 = "Undefined"
                if module_name in lines:
                    nits150 = func(lines[module_name])
                elif "default" in lines:
                    nits150 = func(lines["default"])
                else:
                    nits150 = "Undefined"
                return "100nits:" + nits100 + "% 150nits:" + nits150 + "%"
            if volume==True and lines["Metric"]=="Run Start Audio Volume (%)":
                if module_name in lines:
                    val = func(lines[module_name])
                    if val == "":
                        val = "Undefined"
                    return val
                elif "default" in lines:
                    val = func(lines["default"])
                    if val == "":
                        val = "Undefined"
                    return val
                else:
                    return "Undefined"
    return None

def find_product_name():

    # First try to get and return the OEMxx version from the Surface image
    product = call(['cmd.exe', r'/C reg.exe QUERY HKEY_LOCAL_MACHINE\Software\Microsoft\Surface\OSImage /v "ImageProductName"'])
    if product != None:
        product = product.split(' ')[-1]
    else:
        product = "Undefined"
    if "OEM" not in product.upper():
        # Otherwise, get Model specified in win32_ComputerSystem.  In a retail device, this should be
        # the full name, like "Surface Laptop 4".  In a pre-production device it might be like "OEMxx Product Name EV2".
        # If the latter, then we'll just grab the "OEMxx" part, else use the whole model name.
        product = call(['powershell.exe', r'(gwmi win32_ComputerSystem).Model'], timeout=10)
        print("  Model read from DUT is ", product)
        if product != None and "OEM" in product.upper():
            product = product.split(' ')[0]
            product = product.upper()
        elif product == None:
            product = "Undefined"
    else:
        product = product.upper()
        
    # Replace any spaces in the product name with '_'
    product = product.replace(' ', '_')

    # Then try to look up read model in Product_Names.csv to get mapped friendly name.
    # To do this we first need to use the goals parameter to get the path to the Product_Names.csv.
    # If goals parameter doesn't exist, then return the product we got from the DUT.
    goals = Params.get_raw('global', "goals", log = False, recurse_init = True)
    if goals==None:
        print("  'goals' parameter not specified.  Not able to look up product mapping in Product_Names.csv.")
        return product
    
    # We have a valid goals path, so see if the Product_Names.csv exists.  If not, then return the product we got from the DUT.
    goals_dir = os.path.dirname(goals)
    product_names = os.path.join(goals_dir, "Product_Names.csv")
    if not os.path.isfile(product_names):
        print("  'Product_Names.csv' file does not exist.  Not able to look up product mapping in Product_Names.csv.")
        return product

    # We have the Product_Names.csv file, so look up the product name from the DUT in the dictionary to get the mapped friendly name.
    # If no match, we will just return what we got from the DUT.
    with open(product_names, "r") as file:
        f = csv.DictReader(file)
        for lines in f:
            if lines["OEM"]==product:
                product = lines["PRODUCT"]
                break

    # Replace any spaces in the product name with '_'
    product = product.replace(' ', '_')

    # Use resolveVars() here so that product name definitions can contain other variables, such as screen resolution.
    return Params.resolveVars(product)
    
def find_screen():
    display_res = find_val("DISPLAY_RESOLUTION")

    if display_res == "2256x1504" or display_res == "3000x2000":
        return "13"
    elif display_res == "2496x1664" or display_res == "3240x2160":
        return "15"
    else:
        return None  

def find_mobility():
    val = call(['powershell.exe', r'Get-NetAdapter -Name  Cellular -ErrorAction SilentlyContinue'], timeout = 15)
    print("  Mobility read from DUT is ", val)
    if val == "":
        return "Wi-Fi"
    else:
        return "LTE"


