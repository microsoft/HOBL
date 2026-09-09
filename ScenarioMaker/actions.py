# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.

"""
Manages the list of actions.
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QDialog, QCheckBox, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QInputDialog, QLabel, QDialogButtonBox, QGroupBox, QComboBox
from settings import SettingsData
import os
import json
import time
import collections
from key_map import KeyMap
from code_editor import CodeEditorWindow
import datetime
from pathlib import Path

class ActionModel(QtGui.QStandardItemModel):
    actions = []
    def __init__(self, parent, *args, actions=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actions = actions or []
        self.main_win = parent
        self.user_only_includes = []
        self.init_trackers()

    def init_trackers(self):
        print("Initializing trackers")
        self.insertion_point = None
        self.root = self.invisibleRootItem()
        self.parent_item = self.root

    def rowCount(self, parent_index):
        if parent_index == None:
            parent_index = self.root.index()
        row = 0
        while True:
            test_index = self.index(row, 0, parent_index)
            if not test_index.isValid():
                break
            row += 1
        return row
    
    def remove(self, working_dir, index, remove_files=False):
        self.traverse_remove(working_dir, index, remove_files)
        self.removeRow(index.row(), index.parent())
        self.save(working_dir)
        self.main_win.setWindowModified(True)
        self.layoutChanged.emit()

    def traverse_remove(self, working_dir, index, remove_files=False):
        if self.hasChildren(index):
            for row in range(self.rowCount(index)):
                child_index = self.index(row, 0, index)
                self.traverse_remove(working_dir, child_index, remove_files)
        action = self.data(index, Qt.ItemDataRole.UserRole)
        if action == None:
            return
        print(f"Deleting {action['id']} {action['type']}-{action['description']}")
        self.remove_action_by_id(action['id'], working_dir, remove_files)

    def remove_action_by_id(self, id, working_dir, remove_files=False):
        # working_dir = SettingsData.get("working_dir")
        for i in range(len(self.actions)):
            # print(f"Checking action {i}: {self.actions[i]['id']} {self.actions[i]['type']}-{self.actions[i]['description']}")
            if self.actions[i]['id'] == id:
                if remove_files and 'file_name' in self.actions[i] and self.actions[i]['file_name'] != "":
                    for file_name in self.actions[i]['file_name']:
                        file_path = os.path.join(working_dir, file_name)
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        else:
                            print(f"File path does not exist: {file_path}")
                del self.actions[i]
                break

    def setInsertionPoint(self, index):
        self.insertion_point = index
        if self.isIndexParent(index):
            self.parent_item = self.itemFromIndex(index)
        else:
            self.parent_item = self.itemFromIndex(index).parent()
        self.layoutChanged.emit()

    def getInsertionPoint(self):
        return self.insertion_point
    
    def isIndexParent(self, index):
        if index == None:
            return False
        action = self.data(index, Qt.ItemDataRole.UserRole)
        if action == None:
            return False
        # Actions, such that the next action should be indented under it
        if action['type'] in ['Try', 'Except', 'Else', 'On Success', 'If', 'Else If', 'Loop', 'Setup', 'Run Test', 'Teardown', 'Switch', 'Case', 'Default Case']:
            return True
        return False
    
    def isTypeParent(self, type):
        # Actions that we don't want indented under an Index Parent
        if type in ['Except', 'On Success', 'Else', 'Else If', 'End Try', 'End If', 'End Loop', 'End Switch', 'Run Test', 'Teardown']:
            return True
        return False

    def appendAction(self, working_dir, type="", x="", y="", w="", h="", text="", command="", id="", description="", typing_delay="[typing_delay]", delay="0", file_name="", include_path="", params=[], direction="", val_options="", count="", primary=True):
        action = collections.OrderedDict()
        action[u'id'] = id
        action[u'type'] = type
        action[u'description'] = description
        action[u'enabled'] = True
        if type not in ['Information', 'Try', 'If', 'Setup', 'Teardown', 'Run Test'] and not self.isTypeParent(type):
            action[u'delay'] = delay
        if x != "":
            action[u'x'] = x
        if y != "":
            action[u'y'] = y
        if w != "":
            action[u'w'] = w
        if h != "":
            action[u'h'] = h
        if text != "":
            action[u'text'] = text
        if command != "":
            action[u'command'] = command
        if file_name != "":
            action[u'file_name'] = [file_name]
        if include_path != "":
            action[u'include_path'] = include_path
        if count != "":
            action[u'count'] = count
        if params != []:
            action[u'params'] = params
        if id == "":
            action[u'id'] = self.get_id()
            print(f"Created action {type} with ID {action[u'id']}")
    
        if file_name == "":
            if self.has_image(type):
                action[u'file_name'] = ["image_" + action[u'id'] + ".png"]
            elif type == "Code": # Code block
                action[u'file_name'] = ["code_" + action[u'id'] + ".py"]

        if type in ["Check", "Click", "Move"]:
            action['exception_on'] = "No match"
            action['match_threshold'] = ""
            action['scale'] = ""

        if type == "Click":
            action['primary'] = primary

        if type == "Scroll":
            action['direction'] = direction

        if type in ["Type", "Window Move"]:
            action['typing_delay'] = typing_delay

        if type == "Capture":
            action['recapture'] = False

        if type in ["Set", "Set Default", "Set User Default", "Increment", "Decrement"]:
            action['value'] = ""
            action['name'] = ""

        if type in ["Set Display", "Window Move"]:
            action['screen'] = "0"

        if type in ["If", "Else If"]:
            action['left_term'] = ""
            action['eval_method'] = "=="
            action['right_term'] = ""

        if type in ["Set Default", "Set User Default"]:
            action['val_options'] = val_options

        if type == "Set User Default":
            action['multiple'] = False

        if type == "Check Until Found" or type == "Check Until Not Found":
            action['timeout'] = "120"

        if type == "Information":
            action['author'] = SettingsData.get("author")
            action['capture_device'] = SettingsData.get("device")
            action['create_date'] = str(datetime.date.today())

        action[u'children'] = []


        item = QtGui.QStandardItem(type)
        if (self.insertion_point == None or self.isIndexParent(self.insertion_point)) and not self.isTypeParent(type):
            print("Insert_row = 0")
            insertion_row = 0
        elif (self.insertion_point == None or self.isIndexParent(self.insertion_point)) and self.isTypeParent(type):
            insertion_row = self.insertion_point.row() + 1
            self.parent_item = self.itemFromIndex(self.insertion_point).parent()
            print(f"Insertion_row2 = {insertion_row}")
        else:
            if self.insertion_point == None:
                insertion_row = 0
                print("Insert_row2 = 0")
            else:
                insertion_row = self.insertion_point.row() + 1
                print(f"Insertion_row = {insertion_row}")

        self.actions.append(action)
        # print(f"Len actions: {len(self.actions)}")
        if self.parent_item == None:
            self.root.insertRow(insertion_row, item)
        else:
            self.parent_item.insertRow(insertion_row, item)
        print(f"Inserting at row {insertion_row}, parent {self.dump_item(self.parent_item)}")
        # Need the action to be inserted (above) before we can find the previous capture.
        if type in ['Click', 'Move', 'Check', 'Check Until Found', 'Check Until Not Found']:
            action['capture_id'], trash = self.find_prev_capture(id=action[u'id'], cap_id=None, parent_index=self.root.index())

        self.insertion_point = item.index()
        item.setData(action, Qt.ItemDataRole.UserRole)
        label = self.setDisplayString(action)
        item.setData(label, Qt.ItemDataRole.DisplayRole)
        icon = QtGui.QIcon()
        item.setData(icon, Qt.ItemDataRole.DecorationRole)

        # self.save(working_dir)
        self.main_win.save()

        self.main_win.setWindowModified(True)

        self.layoutChanged.emit()

        # Do not enable drag and drop onto child items
        if not self.isIndexParent(item.index()):
            item.setDropEnabled(False)
            print("Disabled drop")

        return self.actions[-1]

    def setIcon(self, working_dir, action):
        if "file_name" not in action:
            return
        index = self.getIndexFromAction(self.root.index(), action)
        item = self.itemFromIndex(index)
        image_path = os.path.join(working_dir, action['file_name'][0])
        icon = QtGui.QIcon(image_path)
        item.setData(icon, Qt.ItemDataRole.DecorationRole)
    
    def setDisplayString(self, action):
        type = action['type']
        label = type
        if type in ["If", "Else If"]:
            label += f": {action['left_term']} {action['eval_method']} {action['right_term']}"
        elif type in ["Set", "Set Default", "Set User Default"]:
            label += ": " + action['name'] + "=" + action['value']
        elif type in ["Set Display", "Window Move"]:
            label += f": {action['screen']}"
        elif type in ["Increment", "Decrement"]:
            label += ": " + action['name'] + ", " + action['value']
        elif type == "Loop":
            label += ": " + action['count']
        elif type in ["Delay", "Delay To"]:
            label += ": " + action['delay']
        elif type == "Include":
            label += ": " + os.path.basename(action['include_path'])
        elif type == "Comment":
            label = "# " + action['description']
        else:
            label += ": " + action['description']
        return label

    def dump_item(self, item):
        if item == None:
            return "None"
        action = self.data(item.index(), Qt.ItemDataRole.UserRole)
        if action == None:
            return "None"
        return f"{action['id']} {action['type']}-{action['description']}"
        
    def has_image(self, type):
        if type == "Click" or type == "Capture" or type == "Move" or type == "Check" or type == "Check Until Found" or type == "Check Until Not Found":
            return True
        return False
    
    def get_id(self):
        # 1 million tenths of a second covers 28 hours
        # 100 million tenths of a second covers 115 days
        # 1 billion tenths of a second covers 3 years
        while True:
            n = (time.time() * 10) % 1000000000 # 1 billion
            id = self.int32_to_id(int(n))
            if not self.id_used(id):
                return id
            time.sleep(0.11) # This delay ensures we don't get duplicate ID's

    def id_used(self, id):
        for action in self.actions:
            if id == action[u'id']:
                return True
        return False

    def int32_to_id(self, n):
        if n==0: return "0"
        chars="0123456789ACEFHJKLMNPRTUVWXY"
        length=len(chars)
        result=""
        remain=n
        while remain>0:
            pos = remain % length
            remain = remain // length
            result = chars[pos] + result
        return result

    def getIndexFromAction(self, parent_index, action):
        index = None
        for row in range(self.rowCount(parent_index)):
            test_index = self.index(row, 0, parent_index)
            test_action = self.data(test_index, Qt.ItemDataRole.UserRole)
            if test_action == None:
                return None
            if test_action['id'] == action['id']:
                return test_index
            if self.hasChildren(test_index):
                index = self.getIndexFromAction(test_index, action)
            if index != None:
                break
        return index

    def open(self, dir, filename):
        with open(filename) as json_file:
            self.actions = json.load(json_file)
        self.init_trackers()
        self.traverse_open(dir, self.actions, self.parent_item)

    def traverse_open(self, dir, actions, parent_item):
        for action in actions:
            if "enabled" not in action:
                action['enabled'] = True
            if action['type'] == "Include":
                save_path = Path(dir)
                include_path = Path(action['include_path'])
                abspath = (save_path / include_path).resolve()
                if not abspath.exists():
                    abspath = (Path.cwd().parent / include_path).resolve()
                action['include_path'] = str(abspath)

            label = self.setDisplayString(action)
            item = QtGui.QStandardItem(label)

            parent_item.appendRow(item)
            # action[u'index'] = item.index() # index isn't valid untl after appendRow().  Need to set all fields before setData()
            item.setData(action, Qt.ItemDataRole.UserRole)
            self.setIcon(dir, action)
            self.insertion_point = item.index()
            if "children" in action:
                self.traverse_open(dir, action[u'children'], item)

    def find_prev_capture(self, id, cap_id, parent_index):
        # print(f"find_prev_capture called with cap_id {cap_id}, id {id}")
        for row in range(self.rowCount(parent_index)):
            index = self.index(row, 0, parent_index)
            action = self.data(index, Qt.ItemDataRole.UserRole)
            if action == None:
                # print(f"Returning cap_id {cap_id}, action is None")
                return (cap_id, False)
            else:
                # print(f"Traversing {action['type'], action['id']}")
                if action['type'] == "Capture":
                    cap_id = action['id']
                    # print(f"Found capture: {cap_id}")
                if id == action['id']:
                    # We've traversed to the current action
                    # print(f"Returning cap_id {cap_id}, matched our id")
                    return (cap_id, True)
            if self.hasChildren(index):
                (cap_id, bail) = self.find_prev_capture(id, cap_id, index)
                if bail:
                    return (cap_id, True)
        # print(f"Returning cap_id {cap_id}")
        return (cap_id, False)
    
    def dump_actions(self, l):
        print("Dumping action list...")
        json_str = json.dumps(l, indent=4, separators=(',', ': '))
        print(f"{json_str}")

    def traverse_save(self, parent_index, working_dir):
        action_list = []
        for row in range(self.rowCount(parent_index)):
            index = self.index(row, 0, parent_index)
            action = (self.data(index, Qt.ItemDataRole.UserRole)).copy()
            if action == None:
                return action_list
            if action['type'] == "Include":
                try:
                    action['include_path'] = str(Path(action['include_path']).relative_to(Path.cwd().parent))
                    self.user_only_includes.append((action['include_path'], False))
                except:
                    action['include_path'] = os.path.relpath(action['include_path'], working_dir)
                    self.user_only_includes.append((action['include_path'], True))
            print(f"action: {action['type']}-{action['description']}")
            if self.hasChildren(index):
                child_actions = self.traverse_save(index, working_dir)
                action['children'] = child_actions
            action_list.append(action)
        return action_list

    def save(self, working_dir):
        filename = os.path.join(working_dir, os.path.basename(working_dir) + ".json")
        # build tree structure from model
        print(f"Saving json: {filename}")
        save_actions = []
        self.user_only_includes = []
        save_actions = self.traverse_save(self.root.index(), working_dir)
        with open(filename, "w") as json_file:
            json_str = json.dumps(save_actions, indent=4, separators=(',', ': '), sort_keys=True)
            json_file.write(json_str)
        return save_actions


class UnderlineDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        # decide here if item should be bold and set font weight to bold if needed 
        insertion_point = index.model().getInsertionPoint()
        action = index.model().data(index, Qt.ItemDataRole.UserRole)
        parent_action = index.model().data(index.parent(), Qt.ItemDataRole.UserRole)
        # print(f"action id: {action['id']}")
        # if parent_action:
        #     print(f"parent id: {parent_action['id']}")
        # if parent_action:
        #     print(f"insertion point: {insertion_point}, row: {index.row()}, parent: {parent_action[u'id']}")
        # else:
        #     print(f"insertion point: {insertion_point}, row: {index.row()}")
        # actions = index.model().actions
        # print(len(actions))

        if action['type'] == "Comment":
            option.palette.setColor(QtGui.QPalette.ColorRole.Text, Qt.GlobalColor.darkGreen)
            option.palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, Qt.GlobalColor.darkGreen)
        elif action['enabled'] == False:
            option.palette.setColor(QtGui.QPalette.ColorRole.Text, Qt.GlobalColor.lightGray)
            option.palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, Qt.GlobalColor.lightGray)
        else:
            option.palette.setColor(QtGui.QPalette.ColorRole.Text, Qt.GlobalColor.black)
            option.palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

        option.decorationPosition = QtWidgets.QStyleOptionViewItem.Position.Right

        if index == insertion_point:
            rect = option.rect
            painter.setPen(QtGui.QPen(QtGui.QColor(0xff, 0x00, 0x00), 2, Qt.PenStyle.SolidLine))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            # option.font.setWeight(QtGui.QFont.Weight.Bold)

        QtWidgets.QStyledItemDelegate.paint(self, painter, option, index)



class ActionDialog(QDialog):
    
    def __init__(self, model, index, working_dir):
        super().__init__()
        self.setWindowTitle("Action Properties")
        self.actionModel = model
        self.working_dir = working_dir
        self.file_name = None
        self.action = self.actionModel.data(index, Qt.ItemDataRole.UserRole)
        self.type = self.action[u'type']
        # print(f"Index: {index}")
        # print(f"Save action: {self.action}")
        # print(f"Index row: " + str(index.row()))
        # print(model.actions)

        self.formGroupBox = QGroupBox()
        self.formGroupBox.setFixedWidth(500)
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.formGroupBox)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        mainLayout.addWidget(self.buttonBox)
        self.setLayout(mainLayout)
        layout = QFormLayout()

        self.idEdit = QLineEdit(self, text=self.action[u'id'])
        self.typeEdit = QLineEdit(self, text=self.action[u'type'])
        self.descriptionEdit = QLineEdit(self, text=self.action[u'description'])
        layout.addRow(QLabel("ID"), self.idEdit)
        layout.addRow(QLabel("Type"), self.typeEdit)
        layout.addRow(QLabel("Description"), self.descriptionEdit)

        if 'delay' in self.action:
            self.delayEdit = QLineEdit(self, text=self.action[u'delay'])
            layout.addRow(QLabel("Delay"), self.delayEdit)
        if 'x' in self.action:
            self.xEdit = QLineEdit(self, text=self.action[u'x'])
            layout.addRow(QLabel("X"), self.xEdit)
        if 'y' in self.action:
            self.yEdit = QLineEdit(self, text=self.action[u'y'])
            layout.addRow(QLabel("Y"), self.yEdit)
        if 'w' in self.action:
            self.wEdit = QLineEdit(self, text=self.action[u'w'])
            layout.addRow(QLabel("W"), self.wEdit)
        if 'h' in self.action:
            self.hEdit = QLineEdit(self, text=self.action[u'h'])
            layout.addRow(QLabel("H"), self.hEdit)
        if 'count' in self.action:
            self.countEdit = QLineEdit(self, text=self.action[u'count'])
            layout.addRow(QLabel("Count"), self.countEdit)
        if 'name' in self.action:
            self.nameEdit = QLineEdit(self, text=self.action[u'name'])
            layout.addRow(QLabel("Parameter Name"), self.nameEdit)
        if 'value' in self.action:
            if self.type in ["Set Default", "Set User Default"]:
                label = "Default Value"
            else:
                label = "Value"
            self.valueEdit = QLineEdit(self, text=self.action[u'value'])
            layout.addRow(QLabel(label), self.valueEdit)
        if 'screen' in self.action:
            self.screenEdit = QLineEdit(self, text=self.action[u'screen'])
            layout.addRow(QLabel("Screen"), self.screenEdit)
        if 'left_term' in self.action:
            self.leftTermEdit = QLineEdit(self, text=self.action[u'left_term'])
            layout.addRow(QLabel("Left Term"), self.leftTermEdit)
        if 'eval_method' in self.action:
            self.evalMethodCombo = QComboBox()
            self.evalMethodCombo.addItems(['==', '!=', '<', '<=', '>', '>=', 'in', 'not in'])
            self.evalMethodCombo.setCurrentText(self.action[u'eval_method'])
            layout.addRow(QLabel("Eval Method"), self.evalMethodCombo)
        if 'right_term' in self.action:
            self.rightTermEdit = QLineEdit(self, text=self.action[u'right_term'])
            layout.addRow(QLabel("Right Term"), self.rightTermEdit)
        if 'val_options' in self.action:
            self.valOptionsEdit = QLineEdit(self, text=self.action[u'val_options'])
            layout.addRow(QLabel("Value Options"), self.valOptionsEdit)
        if 'author' in self.action:
            self.authorEdit = QLineEdit(self, text=self.action[u'author'])
            layout.addRow(QLabel("Author"), self.authorEdit)
        if 'capture_device' in self.action:
            self.captureDeviceEdit = QLineEdit(self, text=self.action[u'capture_device'])
            layout.addRow(QLabel("Capture Device"), self.captureDeviceEdit)
        if 'create_date' in self.action:
            self.createDateEdit = QLineEdit(self, text=self.action[u'create_date'])
            layout.addRow(QLabel("Creation Date"), self.createDateEdit)
        if 'primary' in self.action:
            self.primaryCheckbox = QCheckBox( "Primary", self)
            self.primaryCheckbox.setChecked(self.action[u'primary'])
            layout.addRow(self.primaryCheckbox)
        if 'text' in self.action:
            display_string = KeyMap.WDToDisplayString(self.action[u'text'])
            self.textEdit = QTextEdit(self, plainText=display_string)
            layout.addRow(QLabel("Text"), self.textEdit)
        if 'typing_delay' in self.action:
            self.keyDelayEdit = QLineEdit(self, text=self.action[u'typing_delay'])
            layout.addRow(QLabel("Typing Delay"), self.keyDelayEdit)
        if 'command' in self.action:
            self.commandEdit = QLineEdit(self, text=self.action[u'command'])
            layout.addRow(QLabel("Command"), self.commandEdit)
        if 'include_path' in self.action:
            self.includePathEdit = QLineEdit(self, text=self.action[u'include_path'])
            layout.addRow(QLabel("Include Path"), self.includePathEdit)
        if 'match_threshold' in self.action:
            self.matchThresholdEdit = QLineEdit(self, text=self.action[u'match_threshold'])
            layout.addRow(QLabel("Match Threshold"), self.matchThresholdEdit)
        if 'scale' in self.action:
            self.scaleEdit = QLineEdit(self, text=self.action[u'scale'])
            layout.addRow(QLabel("Scale"), self.scaleEdit)
        if 'timeout' in self.action:
            self.timeoutEdit = QLineEdit(self, text=self.action[u'timeout'])
            layout.addRow(QLabel("Timeout"), self.timeoutEdit)
        if 'file_name' in self.action:
            file_names = self.action[u'file_name']
            self.fileNameEdit = QLineEdit(self, text=",".join(file_names))
            if self.type == "Code":
                self.file_name = file_names[0]
                h_layout = QHBoxLayout()
                edit_button = QPushButton("Edit")
                edit_button.clicked.connect(self.editCode)
                open_external_button = QPushButton("Open Externally")
                open_external_button.setToolTip("Open the code file in the OS default editor (e.g. VS Code).")
                open_external_button.clicked.connect(self.openCodeExternally)
                h_layout.addWidget(self.fileNameEdit)
                h_layout.addWidget(edit_button)
                h_layout.addWidget(open_external_button)
                layout.addRow(QLabel("File Name"), h_layout)
            else:
                h_layout_fn = QHBoxLayout()
                h_layout_fn.addWidget(self.fileNameEdit)
                add_image_button = QPushButton("+")
                add_image_button.setFixedWidth(30)
                add_image_button.clicked.connect(self.addImageCheck)
                h_layout_fn.addWidget(add_image_button)
                layout.addRow(QLabel("File Name"), h_layout_fn)
                h_layout = QHBoxLayout()
                for file_name in file_names:
                    image_path = os.path.join(working_dir, file_name)
                    self.thumbnail = self.makeThumbnail(image_path)
                    h_layout.addWidget(self.thumbnail)
                layout.addRow(QLabel("Thumbnail"), h_layout)
        if 'capture_id' in self.action:
            self.captureEdit = QLineEdit(self, text=self.action[u'capture_id'])
            layout.addRow(QLabel("Capture ID"), self.captureEdit)
        if 'exception_on' in self.action:
            self.exceptionCombo = QComboBox()
            self.exceptionCombo.addItems(['No match', 'Match', 'Never'])
            self.exceptionCombo.setCurrentText(self.action[u'exception_on'])
            layout.addRow(QLabel("Exception on"), self.exceptionCombo)
        if 'direction' in self.action:
            self.directionCombo = QComboBox()
            self.directionCombo.addItems(['down', 'up'])
            self.directionCombo.setCurrentText(self.action[u'direction'])
            layout.addRow(QLabel("Direction"), self.directionCombo)
        if 'recapture' in self.action:
            self.recaptureCheckBox = QCheckBox()
            self.recaptureCheckBox.setChecked(self.action['recapture'])
            layout.addRow(QLabel("Re-capture"), self.recaptureCheckBox)
        if 'multiple' in self.action:
            self.multipleCheckBox = QCheckBox()
            self.multipleCheckBox.setChecked(self.action['multiple'])
            layout.addRow(QLabel("Multiple"), self.multipleCheckBox)

        if 'params' in self.action and len(self.action['params']) > 0:
            self.vals = []
            for param in self.action['params']:
                name = param['name']
                val = param['value']
                val_options = param['val_options'].split(',')
                val_options = [j.strip() for j in param['val_options'].split(",")]
                if len(val_options) == 1 and val_options[0] == "":
                    val_options = []
                if len(val_options) > 0:
                    valCombo = QComboBox()
                    valCombo.setEditable(True)
                    valCombo.addItems(val_options)
                    valCombo.setCurrentText(val)
                    self.vals.append(valCombo)
                    layout.addRow(QLabel(name), valCombo)
                else:
                    valEdit = QLineEdit(self, text=val)
                    self.vals.append(valEdit)
                    layout.addRow(QLabel(name), valEdit)

        self.formGroupBox.setLayout(layout)

         # adding action when form is accepted
        self.buttonBox.accepted.connect(self.save)
 
        # adding action when form is rejected
        self.buttonBox.rejected.connect(self.reject)

    def makeThumbnail(self, image_path):
        max_width = 500
        max_height = 500
        label = QLabel()
        thumbnail_img = QtGui.QPixmap(image_path)
        print(f"Image path: {image_path}")
        print(f"Screen pixel ration: {self.screen().devicePixelRatio()}")
        thumbnail_img.setDevicePixelRatio(self.screen().devicePixelRatio())
        r1 = max_width / thumbnail_img.width()
        r2 = max_height / thumbnail_img.height()
        r = min(r1, r2)
        if r > 1.0:
            r = 1.0
        thumbnail_scaled = thumbnail_img.scaled(thumbnail_img.size() * r, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(thumbnail_scaled)
        return label

    def editCode(self):
        file_path = os.path.join(self.working_dir, self.file_name)
        self.editor = CodeEditorWindow(None, file_path)
        self.editor.show()
        self.save()

    def openCodeExternally(self):
        file_path = os.path.join(self.working_dir, self.file_name)
        # Create the file with the template contents if it doesn't exist yet, so the
        # external editor has something to open.

        if not QDesktopServices.openUrl(QUrl.fromLocalFile(file_path)):
            QtWidgets.QMessageBox.warning(
                self,
                "Open Externally",
                f"Could not open the file in an external editor:\n{file_path}"
            )
        self.save()
    
    def addImageCheck(self):
        # hide the edit window so it can modify the imageLabel
        self.hide()
        tab = self.actionModel.main_win
        tab.mode_select = True
        tab.selection_cx_frac = 0.5
        tab.selection_cy_frac = 0.5
        tab.pending_dialog = self          # Tab remembers the dialog
        # tab.pending_action = self.action   # Tab knows which action to update
        tab.action_type = "AddImage" #Add image to list of templates to check against the screen capture
        tab.main_win.ui.cancelButton.show()

    def save(self):
        self.action[u'id'] = self.idEdit.text()
        if 'delay' in self.action:
            self.action[u'delay'] = self.delayEdit.text()
        self.action[u'description'] = self.descriptionEdit.text()

        if 'x' in self.action:
            self.action[u'x'] = self.xEdit.text()
        if 'y' in self.action:
            self.action[u'y'] = self.yEdit.text()
        if 'w' in self.action:
            self.action[u'w'] = self.wEdit.text()
        if 'h' in self.action:
            self.action[u'h'] = self.hEdit.text()
        if 'count' in self.action:
            self.action[u'count'] = self.countEdit.text()
        if 'name' in self.action:
            name = self.nameEdit.text().strip('[]')
            self.action[u'name'] = '[' + name + ']'
        if 'expression' in self.action:
            self.action[u'expression'] = self.expressionEdit.text()
        if 'value' in self.action:
            self.action[u'value'] = self.valueEdit.text()
        if 'screen' in self.action:
            self.action[u'screen'] = self.screenEdit.text()
        if 'left_term' in self.action:
            self.action[u'left_term'] = self.leftTermEdit.text()
        if 'eval_method' in self.action:
            self.action[u'eval_method'] = self.evalMethodCombo.currentText()
        if 'right_term' in self.action:
            self.action[u'right_term'] = self.rightTermEdit.text()
        if 'val_options' in self.action:
            self.action[u'val_options'] = self.valOptionsEdit.text()
        if 'author' in self.action:
            self.action[u'author'] = self.authorEdit.text()
        if 'capture_device' in self.action:
            self.action[u'capture_device'] = self.captureDeviceEdit.text()
        if 'create_date' in self.action:
            self.action[u'create_date'] = self.createDateEdit.text()
        if 'primary' in self.action:
            self.action[u'primary'] = self.primaryCheckbox.isChecked()
        if 'text' in self.action:
            wd_string = KeyMap.DisplayToWDString(self.textEdit.toPlainText())
            self.action[u'text'] = wd_string
        if 'typing_delay' in self.action:
            self.action[u'typing_delay'] = self.keyDelayEdit.text()
        if 'match_threshold' in self.action:
            self.action[u'match_threshold'] = self.matchThresholdEdit.text()
        if 'scale' in self.action:
            self.action[u'scale'] = self.scaleEdit.text()
        if 'timeout' in self.action:
            self.action[u'timeout'] = self.timeoutEdit.text()
        if 'command' in self.action:
            self.action[u'command'] = self.commandEdit.text()
        if 'include_path' in self.action:
            self.action[u'include_path'] = self.includePathEdit.text()
        if 'file_name' in self.action:
            self.action[u'file_name'] = [j.strip() for j in self.fileNameEdit.text().split(",")]
        if 'capture_id' in self.action:
            self.action[u'capture_id'] = self.captureEdit.text()
        if 'exception_on' in self.action:
            self.action[u'exception_on'] = self.exceptionCombo.currentText()
        if 'direction' in self.action:
            self.action[u'direction'] = self.directionCombo.currentText()
        if 'recapture' in self.action:
            self.action['recapture'] = self.recaptureCheckBox.isChecked()
        if 'multiple' in self.action:
            self.action['multiple'] = self.multipleCheckBox.isChecked()

        if 'params' in self.action and len(self.action['params']) > 0:
            i = 0
            for param in self.action['params']:
                name = param['name']
                try:
                    param['value'] = self.vals[i].currentText()
                except:
                    param['value'] = self.vals[i].text()
                i += 1

                # val_options = param['val_options'].split(',')
                # if len(val_options) > 0:
                #     self.valCombo = QComboBox()
                #     self.valCombo.addItems(val_options)
                #     self.valCombo.setCurrentText(val)
                #     layout.addRow(QLabel(name), self.valCombo)
                # else:
                #     self.valEdit = QLineEdit(self, text=val)
                #     layout.addRow(QLabel(name), self.valEdit)



                # params = []
                # base_name = os.path.basename(folder)
                # include_json_path = os.path.join(folder, base_name + ".json")
                # with open(include_json_path) as json_file:
                #     actions = json.load(json_file)
                # for action in actions:
                #     if action['type'] == "Set Default":
                #         parameter = collections.OrderedDict()
                #         parameter['name'] = action['name']
                #         parameter['val'] = action['expression']
                #         parameter['val_options'] = action['val_options']
                #         params.append(parameter)



                # self.action[u'params'] = params


        # Update action view with new description
        index = self.actionModel.getIndexFromAction(self.actionModel.root.index(), self.action)
        item = self.actionModel.itemFromIndex(index)
        label = self.actionModel.setDisplayString(self.action)
        item.setData(label, Qt.ItemDataRole.DisplayRole)
        item.setData(self.action, Qt.ItemDataRole.UserRole)

        super().accept()
