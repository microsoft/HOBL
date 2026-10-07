# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""
Creates the main window of the app.
"""

from PyQt6 import QtWidgets, uic, QtGui, QtCore
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QThread
import numpy as np
from datetime import datetime, timedelta
import time
import settings
import cv2
import call_rpc as rpc
from key_map import KeyMap
import actions
import os
import PIL.Image as Image
import shutil
from pathlib import Path
from connection_manager import ConnectionManager
from code_editor import CodeEditorWindow
import qoi
import json
from tab import Tab

main_form, main_base = uic.loadUiType("main_window2.ui")


class MainWindow(QtWidgets.QMainWindow, main_form):
    def __init__(self, app, settings_data, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent=parent)
        self.app = app
        self.ui = main_form()
        self.ui.setupUi(self)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setStyleSheet(Path("tab_style.qss").read_text())
        central_layout = self.ui.centralwidget.layout()
        central_layout.addWidget(self.tab_widget)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.currentChanged.connect(self.update_title)
        self.tab_widget.currentChanged.connect(self.update_dpi_controls)
        # tab_count = self.tab_widget.count()
        # tab_title = "Untitled-"+str(tab_count)
        # self.tab_widget.addTab(Tab(app, settings_data, self, tab_count), tab_title)
        self.tab_widget.tabCloseRequested.connect(self.tab_close_handler)
        self.settings = settings_data
        self.dut_ip = self.settings.get("dut_ip")
        self.last_capture = None
        self.last_capture_pil = None
        self.control_key = False
        self.alt_key = False
        self.shift_key = False
        self.dut_screen_height = 0
        self.dut_screen_width = 0
        self.dutPixelRatio = 0
        self.connection_manager = ConnectionManager(self.settings)
        self.prev_wheel_time = datetime.now()
        self.current_display = 0
        self.modifier_count = 0
        self.modifier_string = ""
        self.mode_select = False
        self.mode_scroll = False
        self.mode_record = False
        self.mode_typing = False
        self.mode_region = False
        self.action_typing_str = ""
        self.selection_width = 50
        self.selection_height = 50
        self.selection_x = 0
        self.selection_y = 0
        self.selection_cx_frac = 0.5
        self.selection_cy_frac = 0.5
        self.region_x = 0
        self.region_y = 0
        self.region_w = 0
        self.region_h = 0
        self.action_type = ""
        self.connected = False
        self.hostPixelRatio = self.screen().devicePixelRatio()

        # Add toolbar buttons
        stylesheet = Path("button_style.qss").read_text()

        self.ui.settingsButton.setStyleSheet(stylesheet)
        self.ui.settingsButton.clicked.connect(self.settings_pressed)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        menu.addAction(self.menu_action("New", "Start a new action list.", self.new_pressed))
        # menu.addAction(self.menu_action("New Tab", "Start a new action list in a new tab.", self.new_tab_pressed))
        menu.addAction(self.menu_action("Open in New Tab", "Open an existing action list.", self.open_pressed))
        # menu.addAction(self.menu_action("Save", "Save current action list.", self.save))
        menu.addAction(self.menu_action("Save a Copy", "Save action list to a new location.", self.save_a_copy))
        menu.addAction(self.menu_action("Open Image", "Display image file for captures.", self.open_image))
        menu.addAction(self.menu_action("Open Remote Connection", "Display DUT screen for captures.", self.remote_connect))
        menu.setStyleSheet(stylesheet)
        self.displaysMenu = menu.addMenu("Displays")
        self.ui.fileButton.setMenu(menu)
        self.ui.fileButton.setStyleSheet(stylesheet)
        
        self.ui.recordButton.setStyleSheet(stylesheet)
        self.ui.recordButton.clicked.connect(self.record_pressed)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        menu.addAction(self.menu_action("Full Screen", "Capture the full screen.", self.screen_capture_pressed))
        menu.addAction(self.menu_action("Screen Region", "Drag a region of the screen to capture.", self.region_capture_pressed))
        menu.setStyleSheet(stylesheet)
        self.ui.captureButton.setMenu(menu)
        self.ui.captureButton.setStyleSheet(stylesheet)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        menu.addAction(self.menu_action("Mouse Click", "Select a UI element to click.", self.mouse_click_pressed))
        menu.addAction(self.menu_action("Mouse Click Coords", "Click on specified coordinates.", self.mouse_click_coords_pressed))
        menu.addAction(self.menu_action("Mouse Move", "Select a UI element to move mouse ptr to.", self.mouse_move_pressed))
        menu.addAction(self.menu_action("Scroll", "Scroll a page up or down using mouse wheel.", self.scroll_pressed))
        menu.addAction(self.menu_action("Type", "Record key strokes.", self.typing_pressed))
        menu.addAction(self.menu_action("Window Move", "Move active window to current display, if needed.", self.window_move_pressed))
        menu.addAction(self.menu_action("Window Maximize", "Maximize active window, if needed.", self.window_maximize_pressed))
        menu.setStyleSheet(stylesheet)
        self.ui.inputButton.setMenu(menu)
        self.ui.inputButton.setStyleSheet(stylesheet)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        menu.addAction(self.menu_action("Region Check", "Drag a region check if present.", self.region_check_pressed))
        menu.setStyleSheet(stylesheet)
        self.ui.validationButton.setMenu(menu)
        self.ui.validationButton.setStyleSheet(stylesheet)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        menu.addAction(self.menu_action("Command", "Enter a shell command to send to DUT.", self.command_pressed))
        menu.addAction(self.menu_action("Code", "Edit a code block to run on the Host.", self.code_pressed))
        menu.setStyleSheet(stylesheet)
        self.ui.scriptingButton.setMenu(menu)
        self.ui.scriptingButton.setStyleSheet(stylesheet)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        menu.addAction(self.menu_action("Set Default", "Set the default value of a parameter.", self.set_default_pressed))
        menu.addAction(self.menu_action("Set", "Set the value of a parameter.", self.set_pressed))
        menu.addAction(self.menu_action("Set User Default", "Set the default value of a user overridable parameter.", self.set_user_default_pressed))
        menu.addAction(self.menu_action("Set Display", "Set the display to use.", self.set_display_pressed))
        menu.addAction(self.menu_action("Increment", "Increment the value of a parameter.", self.increment_pressed))
        menu.addAction(self.menu_action("Decrement", "Decrement the value of a parameter.", self.decrement_pressed))
        menu.setStyleSheet(stylesheet)
        self.ui.parametersButton.setMenu(menu)
        self.ui.parametersButton.setStyleSheet(stylesheet)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        menu.addAction(self.menu_action("If", "Insert an If block.", self.if_block_pressed))
        menu.addAction(self.menu_action("Else If", "Insert an Else If statement.", self.else_if_pressed))
        menu.addAction(self.menu_action("Else", "Insert an Else statement.", self.else_pressed))
        menu.addSeparator()
        menu.addAction(self.menu_action("Check Until Found", "Select a region to check, then an element to check for until found.", self.check_until_found_pressed))
        menu.addAction(self.menu_action("Check Until Not Found", "Select a region to check, then an element to check for until not found.", self.check_until_not_found_pressed))
        menu.setStyleSheet(stylesheet)
        self.ui.conditionalsButton.setMenu(menu)
        self.ui.conditionalsButton.setStyleSheet(stylesheet)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        menu.addAction(self.menu_action("Loop", "Insert an Loop block.", self.loop_block_pressed))
        menu.addAction(self.menu_action("Next Loop", "Jump to the start of the next loop iteration.", self.next_loop_pressed))
        menu.addAction(self.menu_action("Exit Loop", "Stop looping and exit the loop block.", self.exit_loop_pressed))
        menu.addSeparator()
        menu.addAction(self.menu_action("Try", "Insert an Try/Except block.", self.try_block_pressed))
        menu.addAction(self.menu_action("Include", "Insert another module.", self.include_pressed))
        menu.addAction(self.menu_action("Delay", "Wait for specified seconds.", self.delay_pressed))
        menu.addAction(self.menu_action("Delay To", "Wait until specified seconds from beginning of test.", self.delay_to_pressed))
        menu.addAction(self.menu_action("End", "Return control to parent.", self.end_pressed))
        menu.addAction(self.menu_action("Fail", "Immmediately Fail the scenario.", self.fail_pressed))
        menu.setStyleSheet(stylesheet)
        self.ui.flowControlButton.setMenu(menu)
        self.ui.flowControlButton.setStyleSheet(stylesheet)

        menu = QtWidgets.QMenu()
        menu.setToolTipsVisible(True)
        # menu.addAction(self.menu_action("Information", "Add information about this test.", self.information_pressed))
        menu.addAction(self.menu_action("Comment", "Add a comment.", self.comment_pressed))
        menu.addSeparator()
        menu.addAction(self.menu_action("Setup", "Insert a Setup section, for actions prior to measurement.", self.setup_pressed))
        menu.addAction(self.menu_action("Run Test", "Insert a Run Test section for actions to be measured.", self.run_test_pressed))
        menu.addAction(self.menu_action("Teardown", "Insert a Teardown aection for actions after measurement.", self.teardown_pressed))
        menu.setStyleSheet(stylesheet)
        self.ui.structureButton.setMenu(menu)
        self.ui.structureButton.setStyleSheet(stylesheet)

        self.ui.cancelButton.setStyleSheet(stylesheet)
        self.ui.cancelButton.clicked.connect(self.cancel_pressed)
        self.ui.cancelButton.hide()
        self.ui.okButton.setStyleSheet(stylesheet)
        self.ui.okButton.clicked.connect(self.ok_pressed)
        self.ui.okButton.hide()

        # DPI controls docked to the tab bar's top-right corner so they sit
        # under the OK/Cancel buttons without crowding them.
        self.dpiLabel = QtWidgets.QLabel("DPI:")
        self.dpiEdit = QtWidgets.QLineEdit("")
        self.dpiEdit.setFixedWidth(30)
        self.dpiEdit.setValidator(QtGui.QIntValidator(1, 9999, self))
        self.dpiEdit.setEnabled(True)
        self.dpiCornerWidget = QtWidgets.QWidget()
        dpi_corner_layout = QtWidgets.QHBoxLayout(self.dpiCornerWidget)
        dpi_corner_layout.setContentsMargins(0, 0, 6, 0)
        dpi_corner_layout.setSpacing(4)
        dpi_corner_layout.addWidget(self.dpiLabel)
        dpi_corner_layout.addWidget(self.dpiEdit)
        self.tab_widget.setCornerWidget(self.dpiCornerWidget, Qt.Corner.TopRightCorner)
        self.dpiLabel.hide()
        self.dpiEdit.hide()

        self.connection_manager.connection_available_signal.connect(self.connection_available)
        self.connection_manager.connection_attempt_signal.connect(self.connection_attempt)
        self.connection_manager.connection_no_ip_signal.connect(self.connection_no_ip)

        # self.labelImage.setMouseTracking(True)
        self.setMouseTracking(True)
        self.tab_widget.setMouseTracking(True)
        self.tab_widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        # self.labelImage.setFocus()

        # # Open working folder
        # if Path(self.jsonFileName).is_file():
        #     self.actionModel.open(self.jsonFileName)
        #     self.actionList.expandAll()
        #     self.setWindowModified(True)
        #     self.actionModel.layoutChanged.emit()
        #     self.setWindowTitle("Scenario Maker - " + str(self.working_dir) + "[*]")
        # else:
        #     self.new_pressed()
        
        # Start connection_manager thread
        self.connection_manager.start()

    def connection_available(self):
        print("Connection available.")
        self.ui.statusBar.showMessage(f"Connected to DUT at {self.dut_ip}.")
        screen_info = rpc.plugin_screen_info(self.dut_ip, 8000, "InputInject")
        self.dut_screen_width, self.dut_screen_height, self.dutPixelRatio = screen_info[self.current_display]
        print (f"DUT screen {self.current_display} size {self.dut_screen_width} x {self.dut_screen_height} @ scale {self.dutPixelRatio}.")
        print (f"Host Windows scaling factor: {self.hostPixelRatio}")
        self.get_display_info(len(screen_info))
        self.connection_manager.remote_thread.change_pixmap_signal.connect(self.update_image)
        self.connected = True

    def connection_attempt(self):
        print("Trying to connect.")
        self.ui.statusBar.showMessage(f"Trying to connect to DUT at {self.dut_ip}...")

    def connection_no_ip(self):
        self.ui.statusBar.showMessage(f"Set valid IP address for DUT.")
        self.settings_pressed()

    def get_display_info(self, num_displays):
        self.displaysMenu.clear()

        for display in range(num_displays):
            action = QAction(f"Display {display}", self)
            action.setData(display)
            action.triggered.connect(self.update_display)

            if display == self.current_display:
                font = action.font()
                font.setBold(True)
                action.setFont(font)

            self.displaysMenu.addAction(action)

    def update_display(self):
        action = self.sender()
        self.current_display = action.data()
        self.connection_manager.set_display(self.current_display)
        self.connection_manager.resume()

    def menu_action(self, label, tip, method):
        m_action = QAction(QIcon(), label, self)
        m_action.setToolTip(tip)
        m_action.triggered.connect(method)
        return m_action

    def update_title(self):
        w = self.tab_widget.currentWidget()
        if not w:
            self.setWindowTitle("Scenario Maker")
            return
        title = w.working_dir if w.working_dir else "Untitled"
        self.setWindowTitle(f"Scenario Maker - {title}[*]")

    def set_tab_title(self, index, title):
        self.tab_widget.setTabText(index, title)

    def tab_close_handler(self, index):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        result = w.close()
        if result:
            self.tab_widget.removeTab(index)

    ###
    ### Mouse and keyboard events
    ###
    # def event(self, event):
    #     if event.type() == QtCore.QEvent.Type.FocusIn:
    #         print("Focus in")
    #     # if event.type() == QtCore.QEvent.Type.KeyPress:
    #     #     print("here")
    #     #     if event.key() == Qt.Key.Key_Tab:
    #     #         # Handle Tab key press here
    #     #         print("Tab key pressed\n")
    #     #         return True  # Consume the event
    #     return super().event(event) # Pass event to default handler if not tab


    @pyqtSlot(QtGui.QWheelEvent)
    def update_mouse_wheel(self, event):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.update_mouse_wheel(event)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_move(self, event):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.update_mouse_move(event)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_lpress(self, event):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.update_mouse_lpress(event)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_rpress(self, event):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.update_mouse_rpress(event)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_lrelease(self, event):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.update_mouse_lrelease(event)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_rrelease(self, event):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.update_mouse_rrelease(event)

    def keyPressEvent(self, event):
        print("here1")
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.keyReleaseEvent(event)

    # def focusInEvent(self, event):
    #     print("in")
    #     super().focusInEvent(event)

    ###
    ### Toolbar buttons
    ###

    def cancel_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.cancel_pressed()

    def ok_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.ok_pressed()

    def settings_pressed(self):
        # self.labelImage.setFocus()
        s = settings.SettingsWindow(self, self.settings)
        s.finished.connect(lambda: self.connection_manager.resume())
        s.exec()
        self.dut_ip = self.settings.get("dut_ip")

        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.update_dut_ip()

    def mouse_click_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.mouse_click_pressed()

    def mouse_click_coords_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.mouse_click_coords_pressed()

    def mouse_move_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.mouse_move_pressed()
    
    def scroll_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.scroll_pressed()

    def command_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.command_pressed()

    def delay_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.delay_pressed()

    def delay_to_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.delay_to_pressed()

    def record_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.record_pressed()

    def region_capture_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.region_capture_pressed()

    def region_check_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.region_check_pressed()

    def screen_capture_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.screen_capture_pressed()

    def typing_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.typing_pressed()

    def window_move_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.window_move_pressed()

    def window_maximize_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.window_maximize_pressed()

    def try_block_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.try_block_pressed()

    def loop_block_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.loop_block_pressed()

    def exit_loop_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.exit_loop_pressed()

    def next_loop_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.next_loop_pressed()

    def if_block_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.if_block_pressed()

    def else_if_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.else_if_pressed()

    def else_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.else_pressed()

    def check_until_found_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.check_until_found_pressed()

    def check_until_not_found_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.check_until_not_found_pressed()

    def set_default_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.set_default_pressed()

    def set_user_default_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.set_user_default_pressed()

    def set_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.set_pressed()

    def set_display_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.set_display_pressed()

    def increment_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.increment_pressed()

    def decrement_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.decrement_pressed()

    def end_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.end_pressed()

    def fail_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.fail_pressed()

    def information_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.information_pressed()

    def comment_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.comment_pressed()

    def setup_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.setup_pressed()

    def run_test_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.run_test_pressed()

    def teardown_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.teardown_pressed()

    def code_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.code_pressed()

    def include_pressed(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.include_pressed()
    
    def new_pressed(self):
        tab_count = self.tab_widget.count()
        tab_title = "Untitled-"+str(tab_count)
        self.tab_widget.addTab(Tab(self.app, self.settings, self, tab_count), tab_title)
        self.tab_widget.setCurrentIndex(tab_count)
        w = self.tab_widget.currentWidget()
        if not w:
            return
        if not w.new_pressed():
            self.tab_widget.removeTab(tab_count)

    # def new_tab_pressed(self):
    #     tab_count = self.tab_widget.count()
    #     tab_title = "Untitled-"+str(tab_count)
    #     self.tab_widget.addTab(Tab(self.app, self.settings, self, tab_count), tab_title)
    #     self.tab_widget.setCurrentIndex(tab_count)

    def open_pressed(self):
        tab_count = self.tab_widget.count()
        tab_title = "Untitled-"+str(tab_count)
        self.tab_widget.addTab(Tab(self.app, self.settings, self, tab_count), tab_title)
        self.tab_widget.setCurrentIndex(tab_count)
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.open_pressed()

    def deselect_all_buttons(self):
        self.mode_select = False
        self.action_type = ""

    ###
    ### Helpers
    ###

    @pyqtSlot(np.ndarray)
    def update_image(self, cv_img):
        """Updates the image_label with a new opencv image"""
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.update_image(cv_img)
    
    def save(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.save()

    def save_a_copy(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.save_a_copy()

    def open_image(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.open_image()

    def show_dpi_controls(self):
        self.dpiLabel.show()
        self.dpiEdit.show()

    def hide_dpi_controls(self):
        self.dpiLabel.hide()
        self.dpiEdit.hide()

    def update_dpi_controls(self):
        w = self.tab_widget.currentWidget()
        if w and getattr(w, "capture_mode", None) == "image":
            self.show_dpi_controls()
        else:
            self.hide_dpi_controls()

    def remote_connect(self):
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.remote_connect()

    def open_in_new_tab(self, path):
        tab_count = self.tab_widget.count()
        tab_title = "Untitled-"+str(tab_count)
        self.tab_widget.addTab(Tab(self.app, self.settings, self, tab_count), tab_title)
        self.tab_widget.setCurrentIndex(tab_count)
        w = self.tab_widget.currentWidget()
        if not w:
            return
        w.open(path)

    ###
    ### Action item list
    ###

    def closeEvent(self, event):
        # self.settings.set('size', self.size())
        # self.settings.set('pos', self.pos())

        for i in reversed(range(self.tab_widget.count())):
            self.tab_widget.setCurrentIndex(i)
            w = self.tab_widget.currentWidget()
            can_close = w.close()
            if not can_close:
                event.ignore()
                return
            self.tab_widget.removeTab(i)

        self.connection_manager.stop()
        if self.connected:
            result = rpc.call_rpc(self.dut_ip, 8000, "RunWithResultAndExitCode", ["uname"])

            if result != "TIMEOUT":
                if "result" in json.loads(result):
                    cmd = ["killall", "ScreenServer"]
                else:
                    cmd = ["cmd.exe", "/C taskkill /IM ScreenServer.exe /T /F"]

                rpc.call_rpc(self.dut_ip, 8000, "RunWithResultAndExitCode", cmd)
        event.accept()

