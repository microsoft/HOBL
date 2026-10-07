# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

##
# all task for copilot.
#
##

import logging
import core.app_scenario
from core.parameters import Params
import time, os
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import core.action_list



class Copilot(core.app_scenario.Scenario):
    '''
    Nonfunctional.  Needs to be updated for new architecture.
    '''
    module = __module__.split('.')[-1]
    # # Set default parameters
    Params.setDefault(module, 'loops', '1')
    Params.setDefault(module, 'sections', "all") # Choices: short, long, idle, background, multitask
    Params.setDefault(module, 'training_module', 'copilot')
    Params.setDefault(module, 'duration', '300')

    
    # Get parameters
    training_mode = Params.get('global', 'training_mode')
    training_module = Params.get(module, 'training_module')
    typing_delay = Params.get('global', 'typing_delay')
    browser = Params.get('global', 'browser')
    loops = Params.get(module, 'loops')
    sections = Params.get(module, 'sections')
    mica = Params.get('copilot_mica', 'mica')
    duration = Params.get(module, 'duration')
    msa_account = Params.get('global', 'msa_account')
    dut_password = Params.get('global', 'dut_password')
    new_copilot = False


    # Local parameters
    prep_scenarios = []
    enable_strategic_screenshot = '0'


    def setUp(self):
        self._upload("scenarios\\windows\\copilot\\usa.txt", self.dut_exec_path)
        
        if self.training_mode == "0":
            training_root, self.training_folder = self._find_latest_training_folder(self.training_module)
            if self.training_folder == "":
                self._assert("copilot_training folder is missing on the Host.\n")
            local_training = training_root + os.sep + self.training_folder
            self._upload_json(local_training, self.dut_exec_path)
        else:
            logging.info("Training mode enabled")
            self.loops = '1'
            self._call([(self.dut_exec_path + "\\WindowsApplicationDriver\\WinAppDriver.exe"), (self.dut_resolved_ip + " " + self.app_port + " /forcequit")], blocking=False)
            time.sleep(1)
            # Connect to desktop to be able to launch apps with Start menu
            desired_caps = {}
            desired_caps["app"] = "Root"
            self.desktop = self._launchApp(desired_caps)
            self.desktop.implicitly_wait(0)

        core.app_scenario.Scenario.setUp(self)
        if self.mica == "enable" or self.mica == "disable":
            logging.info("Detected mica feature enabled/disabled. Setting browser to edgecanary")
            Params.setOverride("global", "browser", "edgecanary")
            self.browser = Params.get('global', "browser")

    def runTest(self):
        valid_options = {
            "short": self.short,
            "long": self.long,
            "idle": self.idle,
            "noteidle": self.notepadIdle,
            "background": self.background,
            "multitask": self.multitask
            #"skills": self.skills
        }

        for loop in range(int(self.loops)):
            try:
                if "all" in self.sections.lower():
                    self.launch_copilot()
                    self.short()
                    self.long()
                    self.idle()
                    self.background()
                    self.multitask()
                    #self.skills()
                    self.close_copilot()
                else:
                    # splitting sections 
                    options = self.sections.lower().split(" ")
                    # Making sure all options are valid then running each one
                    if all(option in valid_options for option in options):
                        self.launch_copilot()
                        for option in options:
                           valid_options[option]()
                        self.close_copilot()
                    else:
                        logging.error(self.sections + " is not a valid section list.")
                        self.fail(self.sections + " is not a valid section list.")
                if self.training_mode == "1":
                    self.createPrepStatusControlFile()



            except Exception as e :
                logging.info("Unhandled exception - Taking screenshot.")
                try:
                    self._page_source(self.desktop)
                except:
                    pass
                try:
                    self._screenshot()
                except:
                    pass
                raise e
            
            if self.enable_screenshot == '1':
                time.sleep(2)
                self._screenshot(name="end_screen.png")



    def launch_copilot(self):
        if self.training_mode == "0":
            logging.info("Launching copilot")
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "launch_copilot.json")])
        else:
            apps_elem = self._get_app_tray(self.desktop)
            try:
                apps_elem.find_element_by_xpath('//Button[contains(@Name,"Copilot")]')
            except:
                ActionChains(self.desktop).key_down(Keys.META).key_up(Keys.META).perform()
                time.sleep(1)
                ActionChains(self.desktop).send_keys("Copilot").perform()
                time.sleep(1)
                ActionChains(self.desktop).key_down(Keys.ENTER).key_up(Keys.ENTER).perform()
                time.sleep(5)

                copilot_icon = apps_elem.find_element_by_xpath('//Button[contains(@Name,"Copilot")]')
                ActionChains(self.desktop).context_click(copilot_icon).perform()
                time.sleep(1)
                pinbutton = self.desktop.find_element_by_name("Pin to taskbar")
                pinbutton.click()
                time.sleep(1)
                self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))
                self.copilot_driver.find_element_by_name("Close").click()


            logging.info("Launching copilot")
            alist = action_list.ActionList(os.path.join(self.result_dir, "launch_copilot.json"))
            # Open copilot and look for copilot_driver
            self.launchOrSwitchApp(alist, "Copilot")
            #alist.recordTyping(self.desktop, Keys.META + "c", "open copilot with shortkey", type_now=False ,delay = self.typing_delay, perf="1")
            #ActionChains(self.desktop).key_down(Keys.META).send_keys("c").key_up(Keys.META).perform()
            alist.recordSleep(10, "sleep", perf="1")

            self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))
            time.sleep(3)
            alist.recordTypingElem(self.copilot_driver, Keys.ALT + Keys.SPACE + "x", "Hit ALT + SPACE", int(self.typing_delay), perf="1")
            time.sleep(1)
            try:
                maximize = self.copilot_driver.find_element_by_name("Maximize")
                maximize.click()
                logging.info("Maximized copilot window")
                time.sleep(3)
            except:
                pass
            
            try:
                logging.info("Checking for signed in")
                self.copilot_driver.find_element_by_name("Sign In").click()
                time.sleep(2)
                self.copilot_driver.find_element_by_name("Sign In").click()
                time.sleep(5)
                email = WebDriverWait(self.copilot_driver, 10).until(EC.presence_of_element_located((By.NAME, 'Email, phone, or Skype')))
                # self._page_source(self.desktop)
                email.click()
                email.send_keys(self.msa_account)
                self.copilot_driver.find_element_by_name("Next").click()
                time.sleep(5)
                # password = self.desktop.find_element_by_xpath('//*[contains(@Name,"' + "Enter the password" + '")]')
                # Check for password field
                WebDriverWait(self.desktop, 10).until(EC.presence_of_element_located((By.XPATH, '//*[contains(@Name,"' + "Enter the password" + '")]')))
                # password = WebDriverWait(self.desktop, 10).until(EC.presence_of_element_located((By.XPATH, '//*[contains(@Name, "Enter the password")]')))
                # password.click()
                # password.send_keys(self.dut_password)
                # self.desktop.send_keys(self.dut_password)
                ActionChains(self.desktop).send_keys(self.dut_password).perform()
                ActionChains(self.desktop).send_keys(Keys.ENTER).perform()
                time.sleep(5)
                try:
                    logging.info("checking if pop up for signing into different apps appears")
                    self.desktop.find_element_by_name("Microsoft apps only").click()
                except:
                    pass
            except:
                logging.info("Already Signed in")

            alist.saveRecording("launch_copilot.json")

    def close_copilot(self):
        if self.training_mode == "0":
            logging.info("closing copilot")
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "close_copilot.json")])
        else:
            logging.info("closing copilot")
            alist = action_list.ActionList(os.path.join(self.result_dir, "close_copilot.json"))
            self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))
            #self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[@ClassName="SidePaneRootContainer"]')))
            close_button = self.copilot_driver.find_element_by_name("Close")
            alist.recordClick(self.copilot_driver, close_button, "click close button", perf="1")
            alist.recordSleep(5, "sleep so copilot can close")
            alist.saveRecording("close_copilot.json")

    def short(self):
        if self.training_mode == "0":
            logging.info("Starting copilot short task")
            sub_start_time = time.time()
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "copilot_short.json")])
            self._record_phase_time('phase1: short', sub_start_time, (time.time() - sub_start_time))
        else:
            logging.info("Starting copilot training for short")
            passed_check = False
            for x in range(3):
                try:
                    logging.info("Attempt: " + str(x+1))
                    alist = action_list.ActionList(os.path.join(self.result_dir, "copilot_short.json"))

                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))

                    # Clicking the dialogue box
                    logging.info("Looking for the dialogue box")
                    dialogue_box = self.copilot_driver.find_element_by_accessibility_id("InputTextBox")
                    
                    # Click dialogue box and type 1st question
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    logging.info("Asking the first question")
                    text = "How to make a veggie pizza?"
                    alist.recordTypingElem(dialogue_box, text, "Type first question", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(20, "Sleep", perf="1")
                    
                    # Click dialogue box and type 2nd question
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    logging.info("Asking the second question")
                    text = "rewrite \"me and him went to the store\" with proper grammar"
                    alist.recordTypingElem(dialogue_box, text, "Type second question", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(15, "Sleep", perf="1")

                    # Click dialogue box and type 3rd question
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    logging.info("Asking the third question")
                    text = "Summarize Microsofts last earnings results."
                    alist.recordTypingElem(dialogue_box, text, "Type third question", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(20, "Sleep", perf="1")

                    # Ask 4th question
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    logging.info("Asking the fourth question")
                    text = "Which franchises have the most Super Bowls?"
                    alist.recordTypingElem(dialogue_box, text, "Type fourth question", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(20, "Sleep", perf="1")

                    # Ask 4th question
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    logging.info("Asking the fifth question")
                    text = "Recommend me 3 documentaries about surfing."
                    alist.recordTypingElem(dialogue_box, text, "Type fifth question", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(25, "Sleep", perf="1")

                    
                    alist.recordSleep(5, "sleeping for a little before next phase", perf="1")
                    passed_check = True
                    alist.saveRecording("copilot_short")
                    break
                
                except:
                    logging.exception('')
                    try:
                        logging.debug("Killing copilot")
                        self._kill("msedge.exe")
                        time.sleep(5)
                        apps_elem = self._get_app_tray(self.desktop)
                        apps_elem.find_element_by_xpath('//Button[contains(@Name,"Copilot")]').click()
                        self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))
                        self.copilot_driver.find_element_by_name("Maximize").click()
                        logging.info("Maximized copilot window")
                        time.sleep(3)
                    except:
                        pass
                    time.sleep(10)
            if not passed_check:
                raise Exception("Didn't pass case short")

    def long(self):
        if self.training_mode == "0":
            logging.info("Starting copilot long task")
            sub_start_time = time.time()
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "copilot_long.json")])
            self._record_phase_time('phase1: long', sub_start_time, (time.time() - sub_start_time))
        else:
            logging.info("Starting copilot training for long")
            passed_check = False
            for x in range(3):
                try:
                    logging.info("Attempt: " + str(x+1))
                    alist = action_list.ActionList(os.path.join(self.result_dir, "copilot_long.json"))
                    
                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))

                    # Clicking the dialogue box
                    logging.info("Looking for the dialogue box")
                    dialogue_box = self.copilot_driver.find_element_by_accessibility_id("InputTextBox")


                    # Click dialogue box and type 1st question
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    logging.info("Asking the first question")
                    text = "I want to start a neighborhood lemonade stand. Can you tell me what factors to consider for pricing? What could I do to make my lemonade stand out from any potential competition?"\
                    " Do I need any specific permits to sell lemonade? And finally, how can I advertise my lemonade stand in the neighborhood?"  
                    alist.recordTypingElem(dialogue_box, text, "Type third question", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(50, "Sleep", perf="1")

                    # Click dialogue box and type 2nd question
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    logging.info("Asking the second question")
                    text = "Summarize achievements of the first 10 US presidents." 
                    alist.recordTypingElem(dialogue_box, text, "Type third question", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(50, "Sleep", perf="1")


                    # Click dialogue box and type 3rd question
                    logging.info("Asking the third question")
                    text = "Create an image of a jackalope" 
                    alist.recordTypingElem(dialogue_box, text, "Type fourth question", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(30, "Sleep", perf="1")

                    alist.recordSleep(5, "sleeping for end of phase", perf="1")

                    passed_check = True
                    alist.saveRecording("copilot_long")
                    break
                except:
                    logging.exception('')
                    try:
                        logging.debug("Killing copilot")
                        self._kill("msedge.exe")
                        time.sleep(5)
                        apps_elem = self._get_app_tray(self.desktop)
                        apps_elem.find_element_by_xpath('//Button[contains(@Name,"Copilot")]').click()
                        self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))
                        self.copilot_driver.find_element_by_name("Maximize").click()
                        logging.info("Maximized copilot window")
                    except:
                        pass
                    time.sleep(10)
            if not passed_check:
                raise Exception("Didn't pass case long")

    def idle(self):
        if self.training_mode == "0":
            logging.info("Starting copilot idle")
            sub_start_time = time.time()
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "copilot_idle.json")])
            self._record_phase_time('phase1: idle', sub_start_time, (time.time() - sub_start_time))
        else:
            logging.info("Starting copilot training for idle")
            passed_check = False
            for x in range(3):
                try:
                    logging.info("Attempt: " + str(x+1))
                    alist = action_list.ActionList(os.path.join(self.result_dir, "copilot_idle.json"))
                    
                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))

                    # sleep for set duration in seconds
                    alist.recordSleep(int(self.duration), "sleep", perf="1", sleep_now=False)
                    time.sleep(5)

                    alist.recordSleep(5, "sleeping for end of phase", perf="1")

                    passed_check = True
                    alist.saveRecording("copilot_idle")
                    break

                except:
                    logging.exception('')
                    try:
                        logging.debug("Killing copilot")
                        self._kill("msedge.exe")
                        time.sleep(5)
                        apps_elem = self._get_app_tray(self.desktop)
                        apps_elem.find_element_by_xpath('//Button[contains(@Name,"Copilot")]').click()
                    except:
                        pass
                    time.sleep(10)
            if not passed_check:
                raise Exception("Didn't pass case idle")

    def notepadIdle(self):
        if self.training_mode == "0":
            logging.info("Starting copilot idle with notepad")
            sub_start_time = time.time()
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "copilot_noteidle.json")])
            self._record_phase_time('phase1: noteIdle', sub_start_time, (time.time() - sub_start_time))
        else:
            logging.info("Starting copilot training for notepad idle")
            passed_check = False
            for x in range(3):
                try:
                    logging.info("Attempt: " + str(x+1))
                    alist = action_list.ActionList(os.path.join(self.result_dir, "copilot_noteidle.json"))
                    
                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))

                    try:                        
                        refresh_button = self.copilot_driver.find_element_by_name("Refresh")
                        alist.recordClick(refresh_button, refresh_button, "click refresh", perf="1")
                        alist.recordSleep(5, "Sleep", perf="1")
                    except:
                        try:
                            logging.info("Couldn't find refresh button. Looking for it in other options.")
                            # Click additional options to clear the chat by clicking refresh
                            additional_option_button = self.copilot_driver.find_element_by_name("More options")
                            alist.recordClick(self.copilot_driver, additional_option_button, "click more options", perf="1")
                            alist.recordSleep(2, "Sleep", perf="1")
                            refresh_button = self.desktop.find_element_by_name("Refresh")
                            alist.recordClick(self.desktop, refresh_button, "click refresh", perf="1")
                        except:
                            raise Exception("Couldn't find refresh button.")

                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[@ClassName="SidePaneRootContainer"]')))

                    # Look for "More Balanced" button
                    logging.info("Looking for click \"More Balanced\" button (notepad idle)")
                    more_balanced_button = WebDriverWait(self.desktop, 30).until(EC.presence_of_element_located((By.NAME,"More Balanced")))
                    alist.recordClick(self.copilot_driver, more_balanced_button, "clicking more balanced button", perf="1")
                    time.sleep(10)

                    logging.info("launching start menu")
                    self.launchOrSwitchApp(alist, "Start")
                    alist.recordSleep(3, "sleep for 3 seconds", perf="1")
                    start_menu_driver = self.getDriverFromWin(WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[@Name="Start"]'))))
                    text = "Notepad"
                    alist.recordTyping(start_menu_driver, text, "Type notepad", int(self.typing_delay), perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTyping(start_menu_driver, Keys.ENTER, "Type enter", int(self.typing_delay), perf="1")

                    #idle for set duration of seconds
                    alist.recordSleep(int(self.duration), "sleep", perf="1", sleep_now=False)
                    time.sleep(5)

                    #closing notepad
                    logging.info("closing notepad")
                    notepad_driver = self.getDriverFromWin(WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[(@ClassName="Notepad")]'))))
                    alist.recordTyping(notepad_driver, Keys.CONTROL + "w", "Close Notepad", delay = self.typing_delay, perf="1")

                    alist.recordSleep(5, "sleeping for end of phase", perf="1")

                    passed_check = True
                    alist.saveRecording("copilot_noteidle")
                    break

                except:
                    logging.exception('')
                    try:
                        logging.debug("Killing copilot")
                        self._kill("msedge.exe")
                        time.sleep(5)
                        apps_elem = self._get_app_tray(self.desktop)
                        apps_elem.find_element_by_xpath('//Button[contains(@Name,"Copilot")]').click()
                    except:
                        pass
                    time.sleep(10)
            if not passed_check:
                raise Exception("Didn't pass case notepad idle")

    def background(self):
        if self.training_mode == "0":
            logging.info("Starting copilot background task")
            sub_start_time = time.time()
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "copilot_background.json")])
            self._record_phase_time('phase1: background', sub_start_time, (time.time() - sub_start_time))
        else:
            passed_check = False
            logging.info("Starting copilot training for background")
            for x in range(3):
                try:
                    logging.info("Attempt: " + str(x+1))
                    alist = action_list.ActionList(os.path.join(self.result_dir, "copilot_background.json"))
                    
                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))

                    # Close the chat
                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))
                    close_button = self.copilot_driver.find_element_by_name("Close")
                    alist.recordClick(self.copilot_driver, close_button, "click close button", perf="1")

                    # Wait since were testing for copilot in the background and wait for 300 seconds. 
                    alist.recordSleep(int(self.duration), "sleep", perf="1", sleep_now=False)
                    time.sleep(10)
                    self.launchOrSwitchApp(alist, "Copilot")
                    alist.recordSleep(5, "sleep")
                    alist.recordTypingElem(self.copilot_driver, Keys.ALT + Keys.SPACE + "x", "Hit ALT + SPACE", int(self.typing_delay), perf="1")


                    alist.recordSleep(5, "Sleep for end of phase")

                    passed_check = True
                    alist.saveRecording("copilot_background")
                    break
                except:
                    logging.exception('')
                    try:
                        logging.debug("Killing copilot")
                        self._kill("msedge.exe")
                        time.sleep(5)
                        apps_elem = self._get_app_tray(self.desktop)
                        apps_elem.find_element_by_xpath('//Button[contains(@Name,"Copilot")]').click()
                        self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))
                        self.copilot_driver.find_element_by_name("Maximize").click()
                        logging.info("Maximized copilot window")
                        time.sleep(3)
                    except:
                        pass
                    time.sleep(10)
            if not passed_check:
                    raise Exception("Didn't pass case background")

    def multitask(self):
        if self.training_mode == "0":
            logging.info("Starting copilot multitask task")
            sub_start_time = time.time()
            self._call(["cmd.exe", "/C " + os.path.join(self.dut_exec_path, "usa.txt")], blocking=False, expected_exit_code="")
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "copilot_multitask.json")])
            self._record_phase_time('phase1: multi', sub_start_time, (time.time() - sub_start_time))
        else:
            passed_check = False
            for x in range(3):
                try:
                    logging.info("Starting copilot training for multitask")
                    logging.info("Attempt: " + str(x+1))
                    alist = action_list.ActionList(os.path.join(self.result_dir, "copilot_multitask.json"))

                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))

                    logging.info("Moving usa.txt to DUT")
                    self._upload("scenarios\\windows\\copilot\\usa.txt", self.dut_exec_path, check_modified=False)
                    logging.info("Launching notepad")
                    self._call(["cmd.exe", "/C " + os.path.join(self.dut_exec_path, "usa.txt")], blocking=False, expected_exit_code="")
                    alist.recordSleep(5, "wait for notepad to launch")

                    self.launchOrSwitchApp(alist, "Notepad")
                    notepad_driver = self.getDriverFromWin(WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[(@ClassName="Notepad")]'))))

                    alist.recordTyping(notepad_driver, Keys.CONTROL + "a", "Copy all text", delay = self.typing_delay, perf="1")
                    alist.recordTyping(notepad_driver, Keys.CONTROL + "c", "Copy all text", delay = self.typing_delay, perf="1")

                    alist.recordSleep(2, "sleep")
                    alist.recordTyping(notepad_driver, Keys.CONTROL + "w", "Close Notepad", delay = self.typing_delay, perf="1")

                    self.launchOrSwitchApp(alist, "Copilot")

                    
                    logging.info("Looking for the dialogue box")
                    dialogue_box = self.copilot_driver.find_element_by_accessibility_id("InputTextBox")

                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    logging.info("Ask to summarize text document")
                    text = "Summarize "
                    alist.recordTypingElem(dialogue_box, text , "ask to summarize", int(self.typing_delay), perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.CONTROL + "v", "paste text", int(self.typing_delay), perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(2, "sleep")

                    alist.recordSleep(60, "sleep")

                    passed_check = True
                    alist.saveRecording("copilot_multitask")
                    break
                except:
                    logging.exception('')
                    try:
                        logging.debug("Killing copilot")
                        self._kill("msedge.exe")
                        time.sleep(5)
                        apps_elem = self._get_app_tray(self.desktop)
                        apps_elem.find_element_by_xpath('//Button[contains(@Name,"Copilot")]').click()
                        self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//Window[contains(@Name, "Copilot")]')))
                        self.copilot_driver.find_element_by_name("Maximize").click()
                        logging.info("Maximized copilot window")
                        time.sleep(3)
                    except:
                        pass
                    time.sleep(10)
            if not passed_check:
                raise Exception("Didn't pass case multitask")


    def skills(self):
        if self.training_mode == "0":
            logging.info("Starting copilot skills task")
            sub_start_time = time.time()
            self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), os.path.join(self.dut_exec_path, self.training_folder, "copilot_skills.json")])
            self._record_phase_time('phase2: skills', sub_start_time, (time.time() - sub_start_time))
        else:
            logging.info("Starting copilot training for skills")
            passed_check = False
            for x in range(3):
                try:
                    #ssc_region = []
                    logging.info("Attempt: " + str(x+1))
                    alist = action_list.ActionList(os.path.join(self.result_dir, "copilot_skills.json"))
                    alist.recordSleep(10, "sleep", perf="1")
                    
                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[@ClassName="SidePaneRootContainer"]')))

                    try:                        
                        refresh_button = self.copilot_driver.find_element_by_name("Refresh")
                        alist.recordClick(refresh_button, refresh_button, "click refresh", perf="1")
                        alist.recordSleep(5, "Sleep", perf="1")
                    except:
                        try:
                            logging.info("Couldn't find refresh button. Looking for it in other options.")
                            # Click additional options to clear the chat by clicking refresh
                            additional_option_button = self.copilot_driver.find_element_by_name("More options")
                            alist.recordClick(self.copilot_driver, additional_option_button, "click more options", perf="1")
                            alist.recordSleep(2, "Sleep", perf="1")
                            refresh_button = self.desktop.find_element_by_name("Refresh")
                            alist.recordClick(self.desktop, refresh_button, "click refresh", perf="1")
                        except:
                            raise Exception("Couldn't find refresh button.")

                    self.copilot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[@ClassName="SidePaneRootContainer"]')))

                    # Look for "More Balanced" button
                    logging.info("Looking for click \"More Balanced\" button (skills)")
                    more_balanced_button = WebDriverWait(self.desktop, 30).until(EC.presence_of_element_located((By.NAME,"More Balanced")))
                    alist.recordClick(self.copilot_driver, more_balanced_button, "clicking more balanced button", perf="1")

                    # Clicking the dialogue box
                    logging.info("Looking for the dialogue box")
                    dialogue_box = self.copilot_driver.find_element_by_name("Ask me anything...")
                    
                    # Launching settings app
                    logging.info("Launching the settings app")
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    text = "Launch settings app"
                    alist.recordTypingElem(dialogue_box, text, "Open settings", int(self.typing_delay), type_now=True, perf="1")
                    #alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(20, "Sleep", perf="1")

                    #tabs * 12
                    logging.info("Pressing yes")
                    alist.recordTypingElem(dialogue_box, (Keys.SHIFT + Keys.TAB)*12 + Keys.ENTER, "pressing tabs", delay=100, type_now = False)
                    test = Keys.SHIFT + Keys.TAB*12 + Keys.SHIFT + Keys.ENTER
                    dialogue_box.send_keys(test)
                    #self._call([os.path.join(self.dut_exec_path, "InputInject", "InputInject.exe"), r"""[{'cmd':'type','delay':['150'],'keys':'\ue008\ue004\ue008\ue004'}]"""])
                    alist.recordSleep(10, "Sleep", perf="1")

                    # making sure settings is maximized.
                    logging.info("Attempting to maximize settings")
                    try:
                        WebDriverWait(self.desktop, 10).until(EC.presence_of_element_located((By.XPATH,'//*[@Name="Maximize Settings"]'))).click()
                        logging.info("Maximized settings")
                    except:
                        logging.info("Already maximized or couldn't find settings")
                        pass
                    
                    logging.info("Launching the troubleshooter")
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    text = "My camera isn't working. Can you launch troublershooter"
                    alist.recordTypingElem(dialogue_box, text, "Open trouble shooter", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(20, "Sleep", perf="1")

                    # Pressing yes button
                    alist.recordTypingElem(dialogue_box, (Keys.SHIFT + Keys.TAB)*12 + Keys.ENTER, "pressing tabs", delay=100, type_now = False)
                    test = Keys.SHIFT + Keys.TAB*12 + Keys.SHIFT + Keys.ENTER
                    dialogue_box.send_keys(test)
                    alist.recordSleep(10, "Sleep", perf="1")

                    # making sure troubleshooter is maximized.
                    logging.info("Attempting to maximize troubleshooter")
                    self._page_source(self.desktop)
                    try:
                        WebDriverWait(self.desktop, 10).until(EC.presence_of_element_located((By.XPATH,'//*[@Name="Maximize Get Help"]'))).click()
                        logging.info("Maximized troubleshooter")
                    except:
                        logging.info("Already maximized or couldn't find troubleshooter")
                        pass

                    # Taking screenshot 
                    logging.info("Attempting to take screenshot")
                    alist.recordClick(self.copilot_driver, dialogue_box, "click text chat", perf="1")
                    text = "Take a screenshot"
                    alist.recordTypingElem(dialogue_box, text, "asking copilot to take screenshot", int(self.typing_delay), type_now=True, perf="1")
                    alist.recordSleep(1, "Sleep", perf="1")
                    alist.recordTypingElem(dialogue_box, Keys.ENTER, "Hit Enter", int(self.typing_delay), perf="1")
                    alist.recordSleep(10, "Sleep", perf="1")

                    #self._page_source(self.desktop)
                    try:
                        fullscreen_sc = WebDriverWait(self.desktop, 30).until(EC.presence_of_element_located((By.XPATH,'//*[@Name="Fullscreen mode"]')))
                        #self.desktop.find_element_by_class_name("Fullscreen mode")
                        alist.recordClick(self.desktop, fullscreen_sc, "Taking a screenshot", perf="1")
                    except:
                        try:
                            logging.info("trying to find dropdown menu for full screen")
                            dropdown = WebDriverWait(self.desktop, 30).until(EC.presence_of_element_located((By.XPATH,'//*[contains(@Name,"Snipping Mode")]')))
                            alist.recordClick(self.desktop, dropdown, "opening dropdown menu", perf="1")
                            alist.recordSleep(2)
                            #self._page_source(self.desktop)
                            fullscreen_sc = WebDriverWait(self.desktop, 30).until(EC.presence_of_element_located((By.XPATH,'//*[@Name="Full screen"]')))
                            alist.recordClick(self.desktop, fullscreen_sc, "taking full screenshot", perf="1")

                        except:
                            raise Exception("couldn't take screenshot")
                    alist.recordSleep(10, "Sleep", perf="1")

                    # closing trouble shooter 
                    logging.info("Closing the trouble shooter")
                    self.troubleshoot_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[@Name="Get Help"]')))
                    troubleshoot_close_btn = self.troubleshoot_driver.find_element_by_name("Close Get Help")
                    alist.recordClick(self.troubleshoot_driver, troubleshoot_close_btn, "clicking trouble shoot close button", perf="1")
                    alist.recordSleep(3, "Sleep", perf="1")
                    
                    #closing settings 
                    logging.info("Closing the settings screen")
                    self.settings_driver = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[@Name="Settings"]')))
                    setting_close_btn = self.settings_driver.find_element_by_name("Close Settings")
                    alist.recordClick(self.settings_driver, setting_close_btn, "clicking settings close button", perf="1")
                    alist.recordSleep(3, "Sleep", perf="1")
                    
                    try:                        
                        # self.context_menu = WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[@Name="Context"]')))
                        refresh_button = self.copilot_driver.find_element_by_name("Refresh")
                        alist.recordClick(refresh_button, refresh_button, "click refresh", perf="1")
                        alist.recordSleep(5, "Sleep", perf="1")
                    except:
                        try:
                            logging.info("Couldn't find refresh button. Looking for it in other options.")
                            # Click additional options to clear the chat by clicking refresh
                            additional_option_button = self.copilot_driver.find_element_by_name("More options")
                            alist.recordClick(self.copilot_driver, additional_option_button, "click more options", perf="1")
                            alist.recordSleep(2, "Sleep", perf="1")
                            refresh_button = self.desktop.find_element_by_name("Refresh")
                            alist.recordClick(self.desktop, refresh_button, "click refresh", perf="1")
                        except:
                            raise Exception("Couldn't find refresh button.")

                    alist.recordSleep(5, "sleeping for end of phase", perf="1")

                    alist.saveRecording("copilot_skills")
                    passed_check = True
                    break
                
                except:
                    logging.exception('')
                    try:
                        logging.debug("Killing copilot")
                        self._kill("msedge.exe")
                        logging.debug("Killing system settings")
                        self._kill("SystemSettings.exe")
                        logging.debug("Killing troubleshooter")
                        self._kill("GetHelp.exe")
                        time.sleep(5)
                        ActionChains(self.desktop).key_down(Keys.META).send_keys("c").key_up(Keys.META).perform() #launch copilot again
                    except:
                        pass
                    time.sleep(10)
            if not passed_check:
                raise Exception("Didn't pass case skills")

    def get_region(self, driver, threshold = 10, x = 1, y = 1, width = 1, height = 1, image = "N/A"):
        coor = driver.location
        size = driver.size
        x = int(coor["x"] * x)
        y = int(coor["y"] * y)
        width = int(size["width"] * width)
        height = int(size["height"] * height)

        return [threshold, x, y, width, height, image]

    def tearDown(self):
        logging.info("Performing teardown.")
        time.sleep(5)  # Let edge close gracefully before killing driver.
        # try:
        #     WebDriverWait(self.desktop, 60).until(EC.presence_of_element_located((By.XPATH,'//*[@Name="Windows Copilot Preview"]'))).find_element_by_name("Close").click()
        # except:
        #     pass

        core.app_scenario.Scenario.tearDown(self)

        if self.training_mode == "1":
            time.sleep(2)
            self._kill("WinAppDriver.exe")
        else:
            self._kill("InputInject.exe")


    def launchOrSwitchApp(self, alist, app):
        # Check if app is already running
        self.active_driver = self.desktop
        apps_elem = self._get_app_tray(self.desktop)
        # start_button = self._get_start_button(self.desktop)
        if "edge" in app:
            id = None
            if app == "edge":
                id = "MSEdge"
            elif app == "edgedev":
                id = "MSEdgeDev"
            elif app == "edgebeta":
                id = "MSEdgeBeta"
            elif app == "edgecanary":
                id = "MSEdgeCanary"
            else:
                self.fail("Unsuported app name: " + app)
            try:
                app_button = apps_elem.find_element_by_accessibility_id(id)
            except:
                try:
                    app_button = apps_elem.find_element_by_accessibility_id("Appid: " + id)
                except Exception as e:
                    try:
                        app_button = apps_elem.find_element_by_xpath('//Button[contains(@AutomationId,"' + id + '")]')
                    except:
                        self._page_source(self.desktop)
                        raise e
        else:
            try:
                app_button = apps_elem.find_element_by_xpath('//Button[contains(@Name,"' + app + '")]')
            except Exception as e :
                self._page_source(self.desktop)
                raise e        
        #app_button = apps_elem.find_element_by_xpath('//Button[contains(@Name,"' + app + '")]')
        # If this the first call, we don't know if we are already focused on the desired app
        # So do the robust thing and click a known element (Start button) before switching to the desired task
        # Scratch that, we are going to the Start menu every time so that after a full training, you can playback a single phase.
        # if app not in self.open_apps:
        # alist.recordClick(self.desktop, start_button, "Start")
        # alist.recordSleep(1, "Sleep", False)
        alist.recordClick(self.desktop, app_button, "Click " + app + " in task bar")


    def getWindowHandle(self, win):
        win_handle1 = win.get_attribute("NativeWindowHandle")
        win_handle2 = int(win_handle1)
        win_handle3 = format(win_handle2, 'x') # convert to hex string
        return win_handle3


    def getDriverFromWin(self, win):
        win_handle = self.getWindowHandle(win)

        # Launch new session attached to the window
        desired_caps = {}
        desired_caps["appTopLevelWindow"] = win_handle
        driver = self._launchApp(desired_caps, track_driver = False)
        time.sleep(2)  
        driver.switch_to_window(win_handle)
        # driver.maximize_window()
        return driver

    def kill(self):
        try:
            logging.debug("Killing InputInject.exe")
            self._kill("InputInject.exe")
        except:
            pass
        try:
            logging.debug("Killing copilot")
            self._kill("msedge.exe")
        except:
            pass
        try:
            logging.debug("Killing notepad.exe")
            self._kill("notepad.exe")
        except:
            pass
        try:
            logging.debug("Killing system settings")
            self._kill("SystemSettings.exe")
        except:
            pass
        try:
            logging.debug("Killing troubleshooter")
            self._kill("GetHelp.exe")
        except:
            pass
        try:
            logging.debug("Killing WinAppDriver.exe")
            self._kill("WinAppDriver.exe")
        except:
            pass
        