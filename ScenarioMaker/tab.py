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
from image_label import ImageLabel
import collections

def comment_line(s):
    stripped = s.lstrip()
    indent = len(s) - len(stripped)
    return s[:indent] + "# " + stripped

class Tab(QtWidgets.QWidget):
    make_connection_signal = QtCore.pyqtSignal()

    def __init__(self, app, settings_data, parent=None, index=0):
        QtWidgets.QWidget.__init__(self, parent=parent)
        self.tab_name = "test"
        self.app = app
        self.main_win = parent
        self.index = index

        hlayout = QtWidgets.QHBoxLayout()
        self.actionList = QtWidgets.QTreeView()
        self.actionList.setMaximumWidth(250)
        self.actionList.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.actionList.setDragDropMode(QtWidgets.QListView.DragDropMode.DragDrop)
        self.actionList.setHeaderHidden(True)
        self.actionList.setItemsExpandable(False)
        self.actionList.setMouseTracking(False)
        self.actionList.setRootIsDecorated(False)
        self.actionList.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.actionList.setDropIndicatorShown(True)
        self.actionList.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.actionList.setIconSize(QtCore.QSize(48,24))
    
        hlayout.addWidget(self.actionList)
        vlayout = QtWidgets.QVBoxLayout()

        self.labelImage = ImageLabel()
        self.labelImage.setAutoFillBackground(False)
        vlayout.addWidget(self.labelImage)
        hlayout.addLayout(vlayout)
        self.setLayout(hlayout)

        self.settings = settings_data
        self.dut_ip = self.settings.get("dut_ip")
        self.working_dir = ""
        # self.settings.set("working_dir", self.working_dir)
        # self.jsonFileName = os.path.join(self.working_dir, "ScenarioMaker.json")
        self.jsonFileName = ""
        self.last_capture = None
        self.last_capture_pil = None
        self.control_key = False
        self.alt_key = False
        self.shift_key = False
        # self.connection_manager = ConnectionManager(self.settings)
        self.prev_wheel_time = datetime.now()
        self.capture_mode = "remote"

        if self.working_dir != "" and not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
            f_out = open(os.path.join(self.working_dir, "__init__.py"), "w")
            f_out.close()

        # Initialize variables
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
        self.hostPixelRatio = self.screen().devicePixelRatio()

        # Connect action list view
        self.actionModel = actions.ActionModel(self)
        self.actionList.setModel(self.actionModel)
        self.actionList.clicked.connect(self.on_action_item_clicked)
        self.actionList.setStyleSheet(Path("list_style.qss").read_text())
        self.actionList.setItemDelegate(actions.UnderlineDelegate())
        self.actionList.installEventFilter(self)

        self.labelImage.setMouseTracking(True)
        self.setMouseTracking(True)
        self.labelImage.setFocus()

        # # Open working folder
        # if Path(self.jsonFileName).is_file():
        #     self.actionModel.open(self.save_dir, self.working_dir, self.jsonFileName)
        #     self.actionList.expandAll()
        #     self.setWindowModified(True)
        #     self.actionModel.layoutChanged.emit()
        #     self.setWindowTitle("Scenario Maker - " + str(self.working_dir) + "[*]")
        # else:
        #     self.new_pressed()

        self.labelImage.mouse_wheel_signal.connect(self.update_mouse_wheel)
        self.labelImage.mouse_move_signal.connect(self.update_mouse_move)
        self.labelImage.mouse_lpress_signal.connect(self.update_mouse_lpress)
        self.labelImage.mouse_rpress_signal.connect(self.update_mouse_rpress)
        self.labelImage.mouse_lrelease_signal.connect(self.update_mouse_lrelease)
        self.labelImage.mouse_rrelease_signal.connect(self.update_mouse_rrelease)
        

    ###
    ### Mouse and keyboard events
    ###

    # def event(self, event):
    #     if event.type() == QtCore.QEvent.Type.FocusIn:
    #         print("Focus in tab")
    #     return super().event(event) # Pass event to default handler if not tab

    def focusInEvent(self, event):
        print("Focus in")
        self.modifier_count = 0
        super().focusInEvent(event)

    @pyqtSlot(QtGui.QWheelEvent)
    def update_mouse_wheel(self, event):
        delta = event.angleDelta().y()
        current_time = datetime.now()
        time_since_last_wheel = (current_time - self.prev_wheel_time).total_seconds()
        self.prev_wheel_time = current_time
        if self.mode_scroll:
            if time_since_last_wheel > 0.25:
                dir = "down"
                if delta > 0:
                    dir = "up"
                dut_x, dut_y = self.image_to_dut_coords(self.selection_x, self.selection_y)
                x_frac = max(0, dut_x / self.main_win.dut_screen_width)
                y_frac = max(0, dut_y / self.main_win.dut_screen_height)
                action = self.actionModel.appendAction(self.working_dir, type=self.action_type, x="{:.3f}".format(x_frac), y="{:.3f}".format(y_frac), delay=str(self.settings.get("default_delay")), direction=dir)
                if self.main_win.connected:
                    result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "Scroll", dut_x, dut_y, 720, dir, self.main_win.current_display, "0", "0", 0, 0, 0, 0, 0, 0)
            # else squash events

        elif self.mode_select or self.mode_record:
            ratio = self.labelImage.r

            scale = 1.1
            if delta > 0:
                # print(f"Mouse wheel scrolled up {delta}")
                if not self.shift_key:
                    self.selection_width *= scale
                if not self.control_key:
                    self.selection_height *= scale
                # print(f"select_w set to {self.selection_width}")
            elif delta < 0:
                # print(f"Mouse wheel scrolled down {delta}")
                if self.selection_width < 5 or self.selection_height < 5:
                    return
                if not self.shift_key:
                    self.selection_width /= scale
                if not self.control_key:
                    self.selection_height /= scale
            w = int(self.selection_width * ratio)
            h = int(self.selection_height * ratio)
            x = self.selection_x - int(w / 2)
            y = self.selection_y - int(h / 2)

            self.labelImage.drawSelect(x, y, w, h, self.selection_cx_frac, self.selection_cy_frac)
        else:
            # Pass through scrolling
            dir = "down"
            if delta > 0:
                dir = "up"
            dut_x, dut_y = self.image_to_dut_coords(self.selection_x, self.selection_y)
            if self.main_win.connected:
                result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "Scroll", dut_x, dut_y, 120, dir, self.main_win.current_display, "0", "0", 0, 0, 0, 0, 0, 0)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_move(self, event):
        # print (event.position())
        self.selection_x = int(event.position().x())
        self.selection_y = int(event.position().y())
        if self.mode_select or self.mode_record:
            ratio = self.labelImage.r
            w = int(self.selection_width * ratio)
            h = int(self.selection_height * ratio)
            x = self.selection_x - int(w / 2)
            y = self.selection_y - int(h / 2)
            self.labelImage.drawSelect(x, y, w, h, self.selection_cx_frac, self.selection_cy_frac)
        elif self.mode_region:
            self.region_x = min(self.selection_x, self.region_x)
            self.region_y = min(self.selection_y, self.region_y)
            self.region_w = abs(self.selection_x - self.region_x)
            self.region_h = abs(self.selection_y - self.region_y)
            self.labelImage.drawSelect(self.region_x, self.region_y, self.region_w, self.region_h, self.selection_cx_frac, self.selection_cy_frac)
        else:
            dut_x, dut_y = self.image_to_dut_coords_e(event)
            if self.main_win.connected:
                result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "MoveTo", dut_x, dut_y, self.main_win.current_display)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_lpress(self, event):
        self.update_mouse_press(event, True)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_rpress(self, event):
        self.update_mouse_press(event, False)

    def update_mouse_press(self, event, primary):
        # self.labelImage.setFocus()
        if self.mode_select or self.mode_record or self.action_type == "Capture" or self.action_type == "Check":  # Save coordinates for selection
            dut_x, dut_y = self.image_to_dut_coords_e(event)
            w = self.selection_width * self.screen().devicePixelRatio()
            h = self.selection_height * self.screen().devicePixelRatio()
            # Upper left screen coords
            x = (dut_x) - (w/2)
            y = (dut_y) - (h/2)
            if self.mode_record:
                # First flush any typing action, then do a Screen Capture action, then a Mouse Click action
                self.create_typing_action()
                self.screen_capture_pressed()
                self.action_type = "Click"
            if self.action_type == "Click" or self.action_type == "Move":
                action = self.actionModel.appendAction(self.working_dir, type=self.action_type, x="{:.3f}".format(self.selection_cx_frac), y="{:.3f}".format(self.selection_cy_frac), delay=str(self.settings.get("default_delay")), primary=primary)
                self.capture_screen(action[u'file_name'][0], int(x), int(y), int(w), int(h))
                self.actionModel.setIcon(self.working_dir, action)
                self.mode_select = False
                self.labelImage.clearSelect()
                if not self.mode_record:
                    # self.unhighlight_button(self.ui.mouseClickButton)
                    # self.unhighlight_button(self.ui.mouseMoveButton)
                    pass
                if self.mode_record:
                    if self.main_win.connected:
                        result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "TapDown", dut_x, dut_y, primary, self.main_win.current_display)
            if self.action_type == "Check Until Found" or  self.action_type == "Check Until Not Found":
                action = self.actionModel.appendAction(self.working_dir, type=self.action_type, x="{:.3f}".format(0.0), y="{:.3f}".format(0.0), w="{:.3f}".format(1.0), h="{:.3f}".format(1.0), delay=str(self.settings.get("default_delay")))
                self.capture_screen(action[u'file_name'][0], int(x), int(y), int(w), int(h))
                self.actionModel.setIcon(self.working_dir, action)
                self.mode_select = False
                self.labelImage.clearSelect()
            if self.action_type == "Capture" or self.action_type == "Check":
                self.region_x = int(event.position().x())
                self.region_y = int(event.position().y())
                self.mode_region = True

        else: # Pass click through to DUT
            dut_x, dut_y = self.image_to_dut_coords_e(event)
            if self.main_win.connected:
                result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "TapDown", dut_x, dut_y, primary, self.main_win.current_display)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_lrelease(self, event):
        # print (event.position())
        if self.mode_region:
            self.mode_region = False
            return
        dut_x, dut_y = self.image_to_dut_coords_e(event)
        if self.main_win.connected:
            result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "TapUp", dut_x, dut_y, True, self.main_win.current_display)

    @pyqtSlot(QtGui.QMouseEvent)
    def update_mouse_rrelease(self, event):
        # print (event.position())
        dut_x, dut_y = self.image_to_dut_coords_e(event)
        if self.main_win.connected:
            result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "TapUp", dut_x, dut_y, False, self.main_win.current_display)

    def image_to_dut_coords_e(self, event):
        return self.image_to_dut_coords(event.position().x(), event.position().y())

    def image_to_dut_coords(self, x, y):
        # print(f"cursor_x:{cursor_x}, cursor_y:{cursor_y}")
        x_offset = self.labelImage.x
        y_offset = self.labelImage.y
        ratio = self.labelImage.r
        image_x = x - x_offset
        image_y = y - y_offset
        dut_x = int(image_x * self.hostPixelRatio / ratio)
        dut_y = int(image_y * self.hostPixelRatio / ratio)
        return dut_x, dut_y

    def keyPressEvent(self, event):
        self.setFocus()
        key = event.key()
        is_arrow_key = (key in [Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right])
        if is_arrow_key and (self.mode_select or self.mode_record):
            ratio = self.labelImage.r
            adjust = ratio / 20
            scale = 1.1
            if key == Qt.Key.Key_Right:
                if self.selection_cx_frac <= 1.0 - adjust:
                    self.selection_cx_frac += adjust
            elif key == Qt.Key.Key_Down:
                if self.selection_cy_frac <= 1.0 - adjust:
                    self.selection_cy_frac += adjust
            if key == Qt.Key.Key_Left:
                if self.selection_cx_frac >= 0.0 + adjust:
                    self.selection_cx_frac -= adjust
            elif key == Qt.Key.Key_Up:
                if self.selection_cy_frac >= 0.0 + adjust:
                    self.selection_cy_frac -= adjust
            w = int(self.selection_width * ratio)
            h = int(self.selection_height * ratio)
            x = self.selection_x - int(w / 2)
            y = self.selection_y - int(h / 2)
            self.labelImage.drawSelect(x, y, w, h, self.selection_cx_frac, self.selection_cy_frac)
            return
        print("Key pressed")
        # Trick is that to send modifiers through InputInject, we need to build a string with them first.
        # 1) If no modifiers, send keys directly one at a time.  If recording, also build action_typing_str at same time.
        # 2) If modifier(s), build string whether recording or not.
        # 3) When modifier released, send built string
        # 4) If built strings are only shifted alpha chars, then convert them to uppercase
        if isinstance(event, QtGui.QKeyEvent):
            key_text = ""
            if key == Qt.Key.Key_Shift:
                print("Shift pressed")
                self.modifier_count += 1
                self.modifier_string += '\ue008'
                self.action_typing_str += '\ue008'
                self.shift_key = True
            elif key == Qt.Key.Key_Control:
                print("Control pressed")
                self.modifier_count += 1
                self.modifier_string += '\ue009'
                self.action_typing_str += '\ue009'
                self.control_key = True
            elif key == Qt.Key.Key_Alt:
                print("Alt pressed")
                self.modifier_count += 1
                self.modifier_string += '\ue00a'
                self.action_typing_str += '\ue00a'
                self.alt_key = True
            # Not a modifier
            # elif key in key_map.KeyMap:
            elif KeyMap.ContainsQtKey(key):
                # special character
                # key_text = key_map.KeyMap[key]
                key_text = KeyMap.QtToWDKey(key)
            else:
                # regular character
                key_text = QtGui.QKeySequence(key).toString().lower()
            only_shift = self.alt_key == False and self.control_key == False
            print(f"key_text: {key_text}")
            print(f"Modifiers: {event.modifiers()} Count: {self.modifier_count} Connected: {self.main_win.connected}")

            if self.modifier_count == 0:
                # print(f"Sending: {key_text}")
                if self.mode_typing or self.mode_record:
                    self.labelImage.clearSelect()
                    self.action_typing_str += key_text
                if self.main_win.connected:
                    print(f"Sending: {key_text}")
                    result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "Type", key_text, 0, "0", 0, 0, 0, 0, 0, 0)
            elif only_shift:
                # if Shift is pressed, convert to uppercase
                if key_text.isalpha():
                    key_text = key_text.upper()
                self.modifier_string = ""
                if self.mode_typing or self.mode_record:
                    self.labelImage.clearSelect()
                    self.action_typing_str = self.convert_capitals(self.action_typing_str) + key_text
                if self.main_win.connected:
                    result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "Type", key_text, 0, "0", 0, 0, 0, 0, 0, 0)
            else:
                self.modifier_string += key_text
                self.action_typing_str += key_text
                if self.mode_typing or self.mode_record:
                    self.labelImage.clearSelect()
                    # self.action_typing_str += key_text
            print(f"action_typing_str: {self.action_typing_str}")
        else:
            print("Not key event")

    def keyReleaseEvent(self, event):
        if isinstance(event, QtGui.QKeyEvent):
            # key_text = event.text()
            # print(f"Key Released: {key_text}")
            modifier = False
            key = event.key()
            if key == Qt.Key.Key_Shift:
                # print("Shift released")
                self.modifier_count -= 1
                modifier = True
                self.shift_key = False
            elif key == Qt.Key.Key_Control:
                # print("Control released")
                self.modifier_count -= 1
                modifier = True
                self.control_key = False
            elif key == Qt.Key.Key_Alt:
                # print("Alt released")
                self.modifier_count -= 1
                modifier = True
                self.alt_key = False

            # print(f"modifier count: {self.modifier_count}")
            # If all modifiers released, then send accumulated string
            if modifier == True and self.modifier_count == 0 and len(self.modifier_string) > 0:
                # Check if string is only shift-ing letters, and replace with upper cases
                # self.action_typing_str = self.convert_capitals(self.action_typing_str)
                print(f"Sending mstring: {self.modifier_string}")
                if self.main_win.connected:
                    result = rpc.plugin_call(self.dut_ip, 8000, "InputInject", "Type", self.modifier_string, 150, "0", 0, 0, 0, 0, 0, 0, 0)
                self.modifier_string = ""
                if self.mode_typing or self.mode_record:
                    self.create_typing_action()
                self.action_typing_str = ""

    def convert_capitals(self, s):
        capitalize = False
        new_str = ""
        for c in s:
            if c == '\ue009' or c == '\ue00a':
                # Don't try to convert sring that contains ALT or CTRL modifiers
                return s
            if c == '\ue008':
                capitalize = True
                # Remove Shift modifier
                continue
            if capitalize:
                if c.isalpha(): 
                    new_str += c.upper()
                # TODO: include symbols and map appropriately
            else:
                new_str += c
        return new_str

    ###
    ### Toolbar buttons
    ###

    def cancel_pressed(self):
        if self.action_type in ["Capture", "Check", "Typing", "Scroll"]:
            self.action_type = ""
            self.action_typing_str = ""
            self.mode_typing = False
            self.mode_region = False
            self.labelImage.clearSelect()
            self.app.restoreOverrideCursor()
            self.main_win.ui.okButton.hide()
            self.main_win.ui.cancelButton.hide()

    def ok_pressed(self):
        if self.action_type == "Capture":
            self.region_capture_pressed()
        elif self.action_type == "Check":
            self.region_check_pressed()
        elif self.action_type == "Typing":
            self.typing_pressed()
        elif self.action_type == "Scroll":
            self.scroll_pressed()

    def settings_pressed(self):
        self.labelImage.setFocus()
        s = settings.SettingsWindow(self, self.settings)
        s.exec()
        self.dut_ip = self.settings.get("dut_ip")

    def update_dut_ip(self):
        self.dut_ip = self.settings.get("dut_ip")

    def mouse_click_pressed(self):
        self.labelImage.setFocus()
        if self.mode_select == True:
            self.labelImage.clearSelect()
            self.deselect_all_buttons()
        else:
            self.mode_select = True
            self.selection_cx_frac = 0.5
            self.selection_cy_frac = 0.5
            self.action_type = "Click"
            # self.highlight_button(self.ui.mouseClickButton)

    def mouse_click_coords_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Click Coord", x="0.5", y="0.5", delay=str(self.settings.get("default_delay")))
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        if result == 1:
            # self.setWindowModified(True)
            pass

    def mouse_move_pressed(self):
        self.labelImage.setFocus()
        if self.mode_select == True:
            self.labelImage.clearSelect()
            self.deselect_all_buttons()
        else:
            self.mode_select = True
            self.selection_cx_frac = 0.5
            self.selection_cy_frac = 0.5
            self.action_type = "Move"
            # self.highlight_button(self.ui.mouseMoveButton)
    
    def scroll_pressed(self):
        self.labelImage.setFocus()
        if self.mode_scroll == True:
            self.mode_scroll = False
            self.labelImage.clearSelect()
            self.main_win.ui.okButton.hide()
            self.main_win.ui.cancelButton.hide()
        else:
            self.mode_scroll = True
            self.selection_cx_frac = 0.5
            self.selection_cy_frac = 0.5
            self.action_type = "Scroll"
            self.main_win.ui.okButton.show()
            self.main_win.ui.cancelButton.show()

    def command_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Command", command="cmd /c", delay=str(self.settings.get("default_delay")))
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def delay_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Delay", delay=str(self.settings.get("default_delay")))
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def delay_to_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Delay To", delay=str(self.settings.get("default_delay")))
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def record_pressed(self):
        self.labelImage.setFocus()
        if self.mode_record == True:
            self.mode_record = False
            self.labelImage.clearSelect()
            self.create_typing_action()
            self.deselect_all_buttons()
            self.main_win.ui.recordButton.setText("Record")
        else:
            self.mode_record = True
            self.main_win.ui.recordButton.setText("Stop")
            # self.highlight_button(self.ui.recordButton)

    def region_capture_pressed(self):
        self.labelImage.setFocus()
        if self.action_type == "Capture":
            dut_x, dut_y = self.image_to_dut_coords(self.region_x, self.region_y)
            dut_w = self.region_w * self.hostPixelRatio / self.labelImage.r
            dut_h = self.region_h * self.hostPixelRatio / self.labelImage.r
            x_frac = max(0, dut_x / self.main_win.dut_screen_width)
            y_frac = max(0, dut_y / self.main_win.dut_screen_height)
            w_frac = min(1.0, dut_w / self.main_win.dut_screen_width)
            h_frac = min(1.0, dut_h / self.main_win.dut_screen_height)

            action = self.actionModel.appendAction(self.working_dir, type="Capture", x="{:.3f}".format(x_frac), y="{:.3f}".format(y_frac), w="{:.3f}".format(w_frac), h="{:.3f}".format(h_frac), delay=str(self.settings.get("capture_delay")))
            self.capture_screen(action[u'file_name'][0], x=int(dut_x), y=int(dut_y), w=int(dut_w), h=int(dut_h), thumbnail=True)
            self.actionModel.setIcon(self.working_dir, action)

            self.action_type = ""
            self.mode_region = False
            self.labelImage.clearSelect()
            self.app.restoreOverrideCursor()
            self.main_win.ui.okButton.hide()
            self.main_win.ui.cancelButton.hide()

        else:
            self.action_type = "Capture"
            self.app.setOverrideCursor(Qt.CursorShape.CrossCursor)
            self.main_win.ui.okButton.show()
            self.main_win.ui.cancelButton.show()

    def region_check_pressed(self):
        self.labelImage.setFocus()

        if self.action_type == "Check":
            dut_x, dut_y = self.image_to_dut_coords(self.region_x, self.region_y)
            dut_w = self.region_w * self.hostPixelRatio / self.labelImage.r
            dut_h = self.region_h * self.hostPixelRatio / self.labelImage.r

            x_frac = max(0, dut_x / self.main_win.dut_screen_width)
            y_frac = max(0, dut_y / self.main_win.dut_screen_height)
            w_frac = max(0, dut_w / self.main_win.dut_screen_width)
            h_frac = max(0, dut_h / self.main_win.dut_screen_height)

            action = self.actionModel.appendAction(self.working_dir, type="Check", x="{:.3f}".format(x_frac), y="{:.3f}".format(y_frac), w="{:.3f}".format(w_frac), h="{:.3f}".format(h_frac), delay=str(self.settings.get("default_delay")))
            self.capture_screen(action[u'file_name'][0], x=int(dut_x), y=int(dut_y), w=int(dut_w), h=int(dut_h))
            self.actionModel.setIcon(self.working_dir, action)

            self.action_type = ""
            self.mode_region = False
            self.labelImage.clearSelect()
            self.app.restoreOverrideCursor()
            self.main_win.ui.okButton.hide()
            self.main_win.ui.cancelButton.hide()
        else:
            self.action_type = "Check"
            self.main_win.ui.okButton.show()
            self.main_win.ui.cancelButton.show()

    def screen_capture_pressed(self):
        self.labelImage.setFocus()
        if self.mode_record == False:
            # self.highlight_button(self.ui.screenCapButton)
            pass
        action = self.actionModel.appendAction(self.working_dir, type="Capture", x="0", y="0", w="1", h="1", delay=str(self.settings.get("capture_delay")))
        self.capture_screen(action[u'file_name'][0], thumbnail=True)
        self.actionModel.setIcon(self.working_dir, action)
        # self.setWindowModified(True)
        if self.mode_record == False:
            # self.unhighlight_button(self.ui.screenCapButton)
            pass

    def typing_pressed(self):
        self.labelImage.setFocus()
        if self.mode_typing == True:
            self.mode_typing = False
            self.labelImage.clearSelect()
            self.create_typing_action()
            self.deselect_all_buttons()
            self.main_win.ui.okButton.hide()
            self.main_win.ui.cancelButton.hide()
        else:
            self.mode_typing = True
            self.action_type = "Typing"
            self.action_typing_str = ""
            self.main_win.ui.okButton.show()
            self.main_win.ui.cancelButton.show()

    def window_move_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Window Move", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def window_maximize_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Window Maximize", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def try_block_pressed(self):
        try_action = self.actionModel.appendAction(self.working_dir, type="Try", delay="0.0")
        self.actionModel.appendAction(self.working_dir, type="Except", delay="0.0")
        self.actionModel.appendAction(self.working_dir, type="On Success", delay="0.0")
        self.actionModel.appendAction(self.working_dir, type="End Try", delay="0.0")
        self.actionList.expandAll()
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), try_action)
        self.actionModel.setInsertionPoint(index)
        self.actionModel.layoutChanged.emit()

    def loop_block_pressed(self):
        loop_action = self.actionModel.appendAction(self.working_dir, type="Loop", count="1", delay="0.0")
        self.actionModel.appendAction(self.working_dir, type="End Loop", delay="0.0")
        self.actionList.expandAll()
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), loop_action)
        self.actionModel.setInsertionPoint(index)
        self.actionModel.layoutChanged.emit()

    def exit_loop_pressed(self):
        loop_action = self.actionModel.appendAction(self.working_dir, type="Exit Loop", count="1", delay="0.0")
        self.actionList.expandAll()
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), loop_action)
        self.actionModel.setInsertionPoint(index)
        self.actionModel.layoutChanged.emit()

    def next_loop_pressed(self):
        loop_action = self.actionModel.appendAction(self.working_dir, type="Next Loop", count="1", delay="0.0")
        self.actionList.expandAll()
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), loop_action)
        self.actionModel.setInsertionPoint(index)
        self.actionModel.layoutChanged.emit()

    def if_block_pressed(self):
        if_action = self.actionModel.appendAction(self.working_dir, type="If", delay="0.0")
        self.actionModel.appendAction(self.working_dir, type="End If", delay="0.0")
        self.actionList.expandAll()
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), if_action)
        self.actionModel.setInsertionPoint(index)
        self.actionModel.layoutChanged.emit()

    def else_if_pressed(self):
        else_if_action = self.actionModel.appendAction(self.working_dir, type="Else If", delay="0.0")
        self.actionList.expandAll()
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), else_if_action)
        self.actionModel.setInsertionPoint(index)
        self.actionModel.layoutChanged.emit()

    def else_pressed(self):
        else_action = self.actionModel.appendAction(self.working_dir, type="Else", delay="0.0")
        self.actionList.expandAll()
        # index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), else_action)
        # self.actionModel.setInsertionPoint(index)
        self.actionModel.layoutChanged.emit()

    def check_until_found_pressed(self):
        self.labelImage.setFocus()
        if self.mode_select == True:
            self.labelImage.clearSelect()
            self.deselect_all_buttons()
        else:
            self.mode_select = True
            self.selection_cx_frac = 0.5
            self.selection_cy_frac = 0.5
            self.action_type = "Check Until Found"

    def check_until_not_found_pressed(self):
        self.labelImage.setFocus()
        if self.mode_select == True:
            self.labelImage.clearSelect()
            self.deselect_all_buttons()
        else:
            self.mode_select = True
            self.selection_cx_frac = 0.5
            self.selection_cy_frac = 0.5
        self.action_type = "Check Until Not Found"

    def set_default_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Set Default", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def set_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Set", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def set_user_default_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Set User Default", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def set_display_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Set Display", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def increment_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Increment", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def decrement_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Decrement", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def end_pressed(self):
        self.actionModel.appendAction(self.working_dir, type="End", delay="0.0")
        self.actionList.expandAll()
        self.actionModel.layoutChanged.emit()

    def fail_pressed(self):
        self.actionModel.appendAction(self.working_dir, type="Fail", delay="0.0")
        self.actionList.expandAll()
        self.actionModel.layoutChanged.emit()

    def information_pressed(self):
        self.actionModel.appendAction(self.working_dir, type="Information", delay="0.0")
        self.actionList.expandAll()
        self.actionModel.layoutChanged.emit()

    def comment_pressed(self):
        action = self.actionModel.appendAction(self.working_dir, type="Comment", delay="0.0")
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), action)
        dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
        result = dialog.exec()
        self.save()

    def setup_pressed(self):
        self.actionModel.appendAction(self.working_dir, type="Setup", delay="0.0")
        self.actionList.expandAll()
        self.actionModel.layoutChanged.emit()

    def run_test_pressed(self):
        self.actionModel.appendAction(self.working_dir, type="Run Test", delay="0.0")
        self.actionList.expandAll()
        self.actionModel.layoutChanged.emit()

    def teardown_pressed(self):
        self.actionModel.appendAction(self.working_dir, type="Teardown", delay="0.0")
        self.actionList.expandAll()
        self.actionModel.layoutChanged.emit()

    def code_pressed(self):
        code_action = self.actionModel.appendAction(self.working_dir, type="Code", delay="0.0")
        self.actionList.expandAll()
        self.actionModel.layoutChanged.emit()
        # working_dir = self.settings.get("working_dir")
        file_path = os.path.join(self.working_dir, code_action[u'file_name'][0])
        self.editor = CodeEditorWindow(None, file_path)
        self.editor.show()

    def include_pressed(self):
        # Prompt for folder
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select directory')
        if folder:
            folder = str(Path(folder))
            # Get default parameters
            params = []
            base_name = os.path.basename(folder)
            include_json_path = os.path.join(folder, base_name + ".json")
            with open(include_json_path) as json_file:
                actions = json.load(json_file)
            for action in actions:
                if action['type'] == "Set Default":
                    parameter = collections.OrderedDict()
                    parameter['name'] = action['name']
                    parameter['value'] = action['value']
                    parameter['val_options'] = action['val_options']
                    params.append(parameter)
            # Append action
            # relative_path = os.path.relpath(folder, self.working_dir)
            action = self.actionModel.appendAction(self.working_dir, type="Include", include_path=folder, params=params)
    
    def new_pressed(self):
        # Prompt for folder
        new_dir, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Enter new name scenario name', self.settings.get("last_folder"), options=QtWidgets.QFileDialog.Option.ShowDirsOnly)
        if not new_dir:
            return False
        
        self.working_dir = new_dir.replace("/","\\")
        scenario_name = os.path.basename(self.working_dir)
        self.jsonFileName = os.path.join(self.working_dir, scenario_name + ".json")

        if os.path.exists(self.working_dir):
            # prompt with dialog, "Are you sure?"
            reply = QtWidgets.QMessageBox.question(self, 'Confirm', 
                "Directory already exists. Are you sure you want to overwrite it?", 
                QtWidgets.QMessageBox.StandardButton.Yes, 
                QtWidgets.QMessageBox.StandardButton.No)
            if reply == QtWidgets.QMessageBox.StandardButton.No:
                return
            shutil.rmtree(self.working_dir)
            os.makedirs(self.working_dir)
        else:
            os.makedirs(self.working_dir)

        # Delete actions from model
        self.actionModel.remove(self.working_dir, self.actionModel.root.index())
        self.actionModel.removeRows(0, self.actionModel.rowCount(self.actionModel.root.index()))
        self.actionModel.init_trackers()
        self.actionModel.layoutChanged.emit()
        # Add __init.py file
        f_out = open(os.path.join(self.working_dir, "__init__.py"), "w")
        f_out.close()

        self.actionModel.appendAction(self.working_dir, type="Information")
        self.setWindowTitle("Scenario Maker - " + str(self.working_dir) + "[*]")
        self.main_win.set_tab_title(self.index, scenario_name)
        return True

    def open_pressed(self):
        # Prompt for folder
        open_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select directory', self.settings.get("last_folder"))
        if open_dir:
            open_dir = open_dir.replace("/","\\")
            self.open(open_dir)

    def open(self, open_dir):
        # TODO: prompt for unsaved changes
        # Prompt for folder
        open_dir = open_dir.replace("/","\\")
        self.working_dir = open_dir

        # Clear action list
        self.actionModel.removeRows(0, self.actionModel.rowCount(None))
        self.actionModel.init_trackers()
        self.actionModel.layoutChanged.emit()
        # Open folder
        folder = os.path.basename(open_dir)
        self.main_win.setWindowTitle("Scenario Maker - " + str(open_dir) + "[*]")
        self.main_win.set_tab_title(self.index, folder)

        # # Delete images in default working dir
        # print(f"Rmoving working directory: {open_dir}")
        # shutil.rmtree(open_dir)
        # os.makedirs(open_dir)
        # # Add __init.py file
        # f_out = open(os.path.join(open_dir, "__init__.py"), "w")
        # f_out.close()
        # self.jsonFileName = os.path.join(open_dir, "ScenarioMaker.json")

        # # Copy items to working_dir
        # files=os.listdir(self.save_dir)
        # print(f"Files to copy from {self.save_dir}: files")
        # for fname in files:
        #     filename, file_extension = os.path.splitext(fname)
        #     # We want to copy code block python files, but not the generated scenario file
        #     if file_extension == ".py" and not filename.startswith("code_"):
        #         continue
        #     src_file = os.path.join(self.save_dir,fname)
        #     if os.path.isdir(src_file):
        #         continue
        #     shutil.copy(src_file, open_dir)

        # # Rename json to ScenarioMaker.json
        # old_json_filename = os.path.basename(open_dir) + ".json"
        # old_json_path = os.path.join(open_dir, old_json_filename)
        # new_json_path = os.path.join(open_dir, "ScenarioMaker.json")
        # os.replace(old_json_path, new_json_path)

        # Open json from working_dir
        self.jsonFileName = os.path.join(self.working_dir, os.path.basename(open_dir) + ".json")
        self.actionModel.open(open_dir, self.jsonFileName)
        self.actionList.expandAll()
        self.setWindowModified(False)
        self.settings.set("last_folder", open_dir)
        self.actionList.setModel(self.actionModel)
        self.actionModel.layoutChanged.emit()

    def create_typing_action(self):
        if self.action_typing_str != "":
            action = self.actionModel.appendAction(self.working_dir, type="Type", text=self.action_typing_str, typing_delay="[typing_delay]", delay=str(self.settings.get("default_delay")))
            self.action_typing_str = ""
            self.actionModel.layoutChanged.emit()

    def highlight_button(self, button):
        return
        pal = button.palette()
        brush = QtGui.QBrush(QtGui.QColor(0x55, 0xFF, 0x00))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        fontbrush = QtGui.QBrush(QtGui.QColor(0x2b, 0x80, 0x00))
        fontbrush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        pal.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Button, brush)
        pal.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.ButtonText, fontbrush)
        button.setPalette(pal)
        QtWidgets.QApplication.processEvents()

    def deselect_all_buttons(self):
        self.mode_select = False
        self.action_type = ""
        return
        self.unhighlight_button(self.ui.mouseClickButton)
        self.unhighlight_button(self.ui.mouseMoveButton)
        self.unhighlight_button(self.ui.commandButton)
        self.unhighlight_button(self.ui.delayButton)
        self.unhighlight_button(self.ui.recordButton)
        self.unhighlight_button(self.ui.regionCapButton)
        self.unhighlight_button(self.ui.regionCheckButton)
        self.unhighlight_button(self.ui.screenCapButton)
        self.unhighlight_button(self.ui.typingButton)
        self.unhighlight_button(self.ui.scrollButton)

    def unhighlight_button(self, button):
        return
        pal = button.palette()
        brush = QtGui.QBrush(QtGui.QColor(0x00, 0x90, 0x00))
        brush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        fontbrush = QtGui.QBrush(QtGui.QColor(0xff, 0xff, 0xff))
        fontbrush.setStyle(QtCore.Qt.BrushStyle.SolidPattern)
        pal.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.Button, brush)
        pal.setBrush(QtGui.QPalette.ColorGroup.Active, QtGui.QPalette.ColorRole.ButtonText, fontbrush)
        button.setPalette(pal)
        QtWidgets.QApplication.processEvents()

    ###
    ### Helpers
    ###

    @pyqtSlot(np.ndarray)
    def update_image(self, cv_img):
        if self.capture_mode == "remote":
            """Updates the image_label with a new opencv image"""
            rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
            qt_img = self.convert_cv_qt(rgb_image)
            qt_img.setDevicePixelRatio(self.screen().devicePixelRatio())
            # self.last_capture = qt_img
            self.labelImage.setImage(qt_img)
            self.last_capture_pil = Image.fromarray(rgb_image)
    
    def convert_cv_qt(self, rgb_image):
        """Convert from an opencv image to QPixmap"""
        # rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        # print(f"Image dimensions: {w}, {h}")
        convert_to_Qt_format = QtGui.QImage(rgb_image.data, w, h, bytes_per_line, QtGui.QImage.Format.Format_RGB888)
        return convert_to_Qt_format

    def find_previous_index(self, tree_view, current_index):
        model = tree_view.model()
        if not current_index.isValid():
            return QtCore.QModelIndex()
        # Get the row and parent of the current index
        row = current_index.row()
        parent = current_index.parent()
        # If the current index is the first child, move to the parent
        if row == 0:
            return parent
        # Otherwise, move to the previous sibling
        previous_index = model.index(row - 1, 0, parent)
        # If the previous sibling has children, move to its last child
        while model.hasChildren(previous_index):
            previous_index = model.index(model.rowCount(previous_index) - 1, 0, previous_index)
        return previous_index
    
    # def capture_screen(self, name, x=0, y=0, w=-1, h=-1, thumbnail=False):
    #     # OpenCV version
    #     if w == -1:
    #         w = self.last_capture_pil.width
    #     if h == -1:
    #         h = self.last_capture_pil.height

    #     x_frac = x / self.last_capture_pil.width
    #     y_frac = y / self.last_capture_pil.height
    #     w_frac = w / self.last_capture_pil.width
    #     h_frac = h / self.last_capture_pil.height

    #     screen_data = rpc.plugin_screenshot(self.dut_ip, 8000, "InputInject", x=x_frac, y=y_frac, w=w_frac, h=h_frac)
    #     img = qoi.decode(screen_data)
    #     rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    #     image = Image.fromarray(img)

    #     filepath = os.path.join(self.working_dir, name)
    #     if not os.path.exists(self.working_dir):
    #         os.makedirs(self.working_dir)
    #     dut_dpi = int(96 * self.dutPixelRatio)

    #     if thumbnail:
    #         max_width = 500
    #         max_height = 500
    #         r1 = max_width / image.width
    #         r2 = max_height / image.height
    #         r = min(r1, r2)
    #         if r > 1.0:
    #             r = 1.0
    #         image = image.resize((int(image.width*r), int(image.height*r)))
    #     print(f"Saving template with dpi {dut_dpi}")
    #     image.save(filepath, dpi=(dut_dpi, dut_dpi))
    #     return filepath

    def capture_screen(self, name, x=0, y=0, w=-1, h=-1, thumbnail=False):
        if w == -1:
            w = self.last_capture_pil.width
        if h == -1:
            h = self.last_capture_pil.height
        # image = self.last_capture.copy(x, y, w, h)
        image = self.last_capture_pil.crop((x, y, x+w, y+h))
        filepath = os.path.join(self.working_dir, name)
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        dut_dpi = int(96 * self.main_win.dutPixelRatio)

        if thumbnail:
            max_width = 500
            max_height = 500
            r1 = max_width / image.width
            r2 = max_height / image.height
            r = min(r1, r2)
            if r > 1.0:
                r = 1.0
            image = image.resize((int(image.width*r), int(image.height*r)))
        print(f"Saving template with dpi {dut_dpi}")
        image.save(filepath, dpi=(dut_dpi, dut_dpi))
        return filepath


    def save(self, copy_from_path=None):
        if self.working_dir == "":
            print("No working directory set, not saving.")
            return

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        self.settings.set("working_dir", self.working_dir)
        folder = os.path.basename(self.working_dir)
        self.jsonFileName = os.path.join(self.working_dir, folder + ".json")
        save_actions = self.actionModel.save(self.working_dir)
        self.setWindowModified(False)
        self.main_win.setWindowTitle("Scenario Maker - " + str(self.working_dir) + "[*]")
        self.main_win.set_tab_title(self.index, folder)

        if copy_from_path != None:
            # Copy images and code blocks from copy_from_path to working_dir
            files=os.listdir(copy_from_path)
            print(f"Files to copy from {copy_from_path}: {files}")
            for fname in files:
                filename, file_extension = os.path.splitext(fname)
                # We want to copy code block python files, but not the generated scenario file or json file
                if file_extension == ".py" and not filename.startswith("code_"):
                    continue
                if file_extension == ".json":
                    continue
                shutil.copy(os.path.join(copy_from_path, fname), self.working_dir)

        # # Delete ScenarioMaker.json in save folder
        # old_json_path = os.path.join(self.working_dir, "ScenarioMaker.json")
        # if os.path.exists(old_json_path):
        #     print(f"Removing old json: {old_json_path}")
        #     os.remove(old_json_path)

        # Write __init__.py
        with open(os.path.join(self.working_dir, "__init__.py"), 'w') as f:
            f.write(f"from .{folder} import *")
        head, tail = os.path.split(self.working_dir)
        self.settings.set("last_folder", head)

        # Overwrite default_params.py
        params_path = os.path.join(self.working_dir, "default_params.py")
        f_template = open("default_params_template.py")
        f_out = open((params_path), "w")
        user_only_params = False
        for line in f_template.readlines():
            if "return" in line:
                if user_only_params:
                    for user_only_include, rel_to_save_dir in sorted(set(self.actionModel.user_only_includes), key=lambda x: x[0]):
                        here = ", here=__file__" if rel_to_save_dir else ""
                        f_out.write(f"    import_run_user_only({repr(user_only_include)}{here})\n")
                for action in save_actions:
                    if action['type'] in ['Setup', 'Run Test', 'Teardown']:
                        # Only get initial sets
                        break
                    if (not user_only_params and action['type'] == "Set Default") or \
                       (user_only_params and action['type'] == "Set User Default"):
                        if user_only_params:
                            section = None
                        else:
                            section = folder
                        name = action['name'].strip('[]')
                        val = action['value']
                        description = action['description']
                        val_options = [x.strip() for x in action['val_options'].split(',')]
                        if len(val_options) == 1 and val_options[0] == '':
                            val_options = []
                        # Parse out section instead of assuming global
                        l = name.split(':')
                        if len(l) == 1:
                            name = l[0]
                        elif len(l) == 2:
                            section = l[0]
                            name = l[1]
                        else:
                            print(f"ERROR - Invalid parameter name: {name}")
                        if user_only_params:
                            method = "Params.setUserDefault"
                            if action.get('multiple', False):
                                new_line = f"    {method}({repr(section)}, '{name}', '{val}', desc='{description}', valOptions={val_options}, multiple=True)\n"
                            else:
                                new_line = f"    {method}({repr(section)}, '{name}', '{val}', desc='{description}', valOptions={val_options})\n"
                        else:
                            new_line = f"    Params.setDefault('{section}', '{name}', '{val}', desc='{description}', valOptions={val_options})\n"
                        if not action['enabled']:
                            new_line = comment_line(new_line)
                        f_out.write(new_line)
                    if not user_only_params and action['type'] == "Set":
                        section = None
                        new_line = ""
                        name = action['name'].strip('[]')
                        val = action['value']
                        # Parse out section instead of assuming global
                        l = name.split(':')
                        if len(l) == 1:
                            name = l[0]
                            new_line = f"    Params.setParam({section}, '{name}', '{val}')\n"
                        elif len(l) == 2:
                            section = l[0]
                            name = l[1]
                            new_line = f"    Params.setParam('{section}', '{name}', '{val}')\n"
                        else:
                            print(f"ERROR - Invalid parameter name: {name}")
                        if not action['enabled']:
                            new_line = comment_line(new_line)
                        f_out.write(new_line)
                user_only_params = True
            f_out.write(line)
        f_template.close()
        f_out.close()

        # Check if python file exists
        python_path = os.path.join(self.working_dir, folder + ".py")
        if Path(python_path).is_file():
            print(f"Save path: {python_path} already exists, not overwriting.")
            # If so, don't touch it.
            return
        else:
            # If not, overwrite it from template.
            class_name = ''.join(word.title() for word in folder.split('_'))
            print(f"Class_name: {class_name}")
            f_template = open("scenario_template.py")
            f_out = open((python_path), "w")
            for line in f_template.readlines():
                line = line.replace("scenario_template", folder)
                line = line.replace("ScenarioTemplate", class_name)
                f_out.write(line)
            f_template.close()
            f_out.close()
            print(f"Save path: {python_path} written.")


    def save_a_copy(self):
        length = self.actionModel.rowCount(None)
        if length == 0:
            return
        copy_from_path = self.working_dir
        # self.working_dir = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select directory', self.settings.get("last_folder"))
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Enter new name to save scenario as', self.settings.get("last_folder"), options=QtWidgets.QFileDialog.Option.ShowDirsOnly)
        # dialog = QtWidgets.QFileDialog(self)
        # dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        # dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
        # dialog.setOption(QtWidgets.QFileDialog.Option.ShowDirsOnly)
        # if dialog.exec():
        #     self.working_dir = dialog.selectedFiles()[0]
        if path:
            self.working_dir = str(Path(path)) # convert from posix to Windows format
            print(self.working_dir)
            if os.path.exists(self.working_dir):
                # prompt with dialog, "Are you sure?"
                reply = QtWidgets.QMessageBox.question(self, 'Confirm', 
                    "Directory already exists. Are you sure you want to overwrite it?", 
                    QtWidgets.QMessageBox.StandardButton.Yes, 
                    QtWidgets.QMessageBox.StandardButton.No)
                if reply == QtWidgets.QMessageBox.StandardButton.No:
                    return
                shutil.rmtree(self.working_dir)
                os.makedirs(self.working_dir)
            else:
                os.makedirs(self.working_dir)
            self.save(copy_from_path)
        else:
            # User cancelled save dialog, do nothing.
            return

    def open_image(self):
        image_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select image')
        if image_path:
            self.capture_mode = "image"
            img = QtGui.QPixmap(image_path).toImage()
            img.setDevicePixelRatio(self.screen().devicePixelRatio())

            self.labelImage.setImage(img)
            self.last_capture_pil = Image.fromqimage(img)

    def remote_connect(self):
        self.capture_mode = "remote"

    ###
    ### Action item list
    ###

    def on_action_item_clicked(self, item):
        indexes = self.actionList.selectedIndexes()
        if indexes:
            # Indexes is a list of a single item in single-select mode.
            for index in indexes:
                print(f"Selecting row {index.row()}")
            index = indexes[0]
            self.actionModel.setInsertionPoint(index)
        self.labelImage.setFocus()


    def on_action_item_delete(self, item):
        indexes = self.actionList.selectedIndexes()
        if indexes:
            quit_msg = "Are you sure you want to delete this action?"
            reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg, QtWidgets.QMessageBox.StandardButton.Yes, QtWidgets.QMessageBox.StandardButton.No)
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # Indexes is a list of a single item in single-select mode.
                index = indexes[0]
                # Remove the item and refresh.
                print(f"Deleting row: {index.row()}")
                self.actionModel.remove(self.working_dir, index, remove_files=True)
                print(len(self.actionModel.actions))
                if len(self.actionModel.actions) == 0:
                    self.actionModel.init_trackers()
                prev_index = self.find_previous_index(self.actionList, index)
                self.actionModel.setInsertionPoint(prev_index)
                self.actionModel.layoutChanged.emit()
                # Clear the selection (as it is no longer valid).
                self.actionList.clearSelection()
                # self.setWindowModified(True)
                self.save()
                self.labelImage.setFocus()
            else:
                self.labelImage.setFocus()
                return

    def on_action_item_edit(self, item):
        indexes = self.actionList.selectedIndexes()
        if indexes:
            # Indexes is a list of a single item in single-select mode.
            index = indexes[0]
            print(f"Editing row {index.row()}")
            dialog = actions.ActionDialog(self.actionModel, index, self.working_dir)
            result = dialog.exec()
            if result == 1:
                self.setWindowModified(True)
                self.save()
                self.actionModel.layoutChanged.emit()

    def on_action_item_enable(self, item):
        indexes = self.actionList.selectedIndexes()
        if indexes:
            # Indexes is a list of a single item in single-select mode.
            index = indexes[0]
            action = self.actionModel.data(index, Qt.ItemDataRole.UserRole)
            enabled = action['enabled']
            if enabled:
                action['enabled'] = False
            else:
                action['enabled'] = True
            item = self.actionModel.itemFromIndex(index)
            item.setData(action, Qt.ItemDataRole.UserRole)
            self.actionModel.layoutChanged.emit()
            self.save()

    def on_action_item_open(self, item):
        indexes = self.actionList.selectedIndexes()
        if indexes:
            # Indexes is a list of a single item in single-select mode.
            index = indexes[0]
            action = self.actionModel.data(index, Qt.ItemDataRole.UserRole)
            include_path = action['include_path']
            self.main_win.open_in_new_tab(include_path)


    def eventFilter(self, source, event):
        if (event.type() == QtCore.QEvent.Type.ContextMenu and source is self.actionList):

            indexes = self.actionList.selectedIndexes()
            if indexes:
                index = indexes[0]
                action = self.actionModel.data(index, Qt.ItemDataRole.UserRole)
                enabled = action['enabled']

                menu = QtWidgets.QMenu()
                action_delete = menu.addAction("Delete")
                action_edit = menu.addAction("Edit")
                if enabled:
                    action_enable = menu.addAction("Disable")
                else:
                    action_enable = menu.addAction("Enable")
                if action['type'] == 'Include':
                    action_open = menu.addAction("Open in new tab")
                    action_open.triggered.connect(self.on_action_item_open)

                action_delete.triggered.connect(self.on_action_item_delete)
                action_edit.triggered.connect(self.on_action_item_edit)
                action_enable.triggered.connect(self.on_action_item_enable)
                menu.exec(event.globalPos())
                return True
        return super(Tab, self).eventFilter(source, event)

    def close(self):
        # self.settings.set('size', self.size())
        # self.settings.set('pos', self.pos())

        # if self.isWindowModified():
        #     quit_msg = "Are you sure you want to quit without saving changes?"
        #     reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg, QtWidgets.QMessageBox.StandardButton.Yes, QtWidgets.QMessageBox.StandardButton.No)
        #     if reply == QtWidgets.QMessageBox.StandardButton.No:
        #         return False
            
        # # Clear working_dir
        # print(f"Clearing folder: {self.working_dir}")
        # shutil.rmtree(self.working_dir)
        self.save()
        return True
