# ///////////////////////////////////////////////////////////////
#
# BY: WANDERSON M.PIMENTA
# PROJECT MADE WITH: Qt Designer and PySide6
# V: 1.0.0
#
# This project can be used freely for all uses, as long as they maintain the
# respective credits only in the Python scripts, any information in the visual
# interface (GUI) can be modified without any implication.
#
# There are limitations on Qt licenses if you want to use your products
# commercially, I recommend reading them on the official website:
# https://doc.qt.io/qtforpython/licenses.html
#
# ///////////////////////////////////////////////////////////////

# IMPORT PACKAGES AND MODULES
# ///////////////////////////////////////////////////////////////
from collections import defaultdict
import logging
from re import sub
import re

import sys

from .functions_main_window import *
import os
import platform
import json
import subprocess

# IMPORT QT CORE
# ///////////////////////////////////////////////////////////////
from qt_core import *

from ble.fsr_controller import FSRController
from ble.ble_scanner import BLEScanner
from stimulator.stimulator_parameters import StimulatorParameters
from stimulator.stimulation_classes import StimulationBasic
from stimulator.gait_model_stimulation_functions import MUSCULAR_GROUP_SELECTION
from stimulator.gait_phases import Phase

# IMPORT SETTINGS
# ///////////////////////////////////////////////////////////////
from gui.core.json_settings import Settings

# IMPORT THEME COLORS
# ///////////////////////////////////////////////////////////////
from gui.core.json_themes import Themes

# IMPORT PY ONE DARK WIDGETS
# ///////////////////////////////////////////////////////////////
from gui.widgets import *

# LOAD UI MAIN
# ///////////////////////////////////////////////////////////////
from .ui_main import *

# MAIN FUNCTIONS
# ///////////////////////////////////////////////////////////////
from .functions_main_window import MainFunctions

# EXPERIMENT FUNCTIONS
# # ///////////////////////////////////////////////////////////////
from angle_calibrator import AngleCalibrator
from stimulator.ComPortFunc import list_serial_devices, close_serial_port, open_serial_port

from modify_svg import change_number_to, change_color_to

# FOR PYLANCE
# ///////////////////////////////////////////////////////////////
from typing import TYPE_CHECKING, Optional
from serial import Serial
from gui.widgets.py_left_menu.py_left_menu_button import PyLeftMenuButton


if TYPE_CHECKING:
    from .ui_main import UI_MainWindow
    from gui.core.functions import Functions

LINE_WIDTH = 200
LINE_HEIGHT = 30
LINE_WIDTH_MID = 300
BUTTON_WIDTH = 200
BUTTON_HEIGHT_HOME = 60
BUTTON_HEIGHT = 40
DROPDOWN_WIDTH = 120
LEFT = True
RIGHT = False

def _default_patients_phase1_dir() -> str:
    """
    Resolve default dataset base dir depending on OS/user
    Create the folder if it doesn't exist.
    """
    try:
        sysname = platform.system().lower()
        if "windows" in sysname:
            appdata = os.getenv("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
            base = os.path.join(appdata, "Programs", "NeuroPulse Analyzer", "NeuroPulseAnalyzer_Dataset")
        elif "darwin" in sysname or "mac" in sysname:
            base = os.path.join(os.path.expanduser("~/Library/Application Support"), "NeuroPulse Analyzer", "NeuroPulseAnalyzer_Dataset")
        else:
            base = os.path.join(os.path.expanduser("~/.local/share"), "NeuroPulse Analyzer", "NeuroPulseAnalyzer_Dataset")
        phase1 = os.path.join(base, "phase1")
        os.makedirs(phase1, exist_ok=True)
        return phase1
    except Exception:
        # Fallback near the app root if anything fails
        return os.path.join(os.path.abspath(os.getcwd()), "NeuroPulseAnalyzer_Dataset", "phase1")


PATIENTS_BASE_DIR = _default_patients_phase1_dir()
FILE_NAME_FORMAT = "Task-SubjID-Time"



# PY WINDOW
# ///////////////////////////////////////////////////////////////
class SetupMainWindow:
    def __init__(self):
        super().__init__()
        # SETUP MAIN WINDOw
        # Load widgets from "gui\uis\main_window\ui_main.py"
        # ///////////////////////////////////////////////////////////////
        self.ui = UI_MainWindow()
        self.ui.setup_ui(self)

    # ADD LEFT MENUS
    # ///////////////////////////////////////////////////////////////
    add_left_menus = [
        {
            "btn_icon": "icon_add_user.svg",
            "btn_id": "btn_subject_info",
            "btn_text": "Add Subject Information",
            "btn_tooltip": "Add subject information",
            "show_top": True,
            "is_active": True,
        },
        {
            "btn_icon": "icon_task.svg",
            "btn_id": "btn_task_info",
            "btn_text": "Select Task",
            "btn_tooltip": "Select task",
            "show_top": True,
            "is_active": False,
        },
        {
            "btn_icon": "icon_settings.svg",
            "btn_id": "btn_home",
            "btn_text": "Connect devices",
            "btn_tooltip": "Connect devices",
            "show_top": True,
            "is_active": False,
        },
        {
            "btn_icon": "icon_stimulation.svg",
            "btn_id": "btn_stimulation_2",
            "btn_text": "Stimulation Parameters",
            "btn_tooltip": "Open stimulation parameters",
            "show_top": True,
            "is_active": False,
        },
    ]

    # ADD TITLE BAR MENUS
    # ///////////////////////////////////////////////////////////////
    add_title_bar_menus = [
        {
            "btn_icon": "icon_search.svg",
            "btn_id": "btn_search",
            "btn_tooltip": "Search",
            "is_active": False,
        },
        {
            "btn_icon": "icon_settings.svg",
            "btn_id": "btn_top_settings",
            "btn_tooltip": "Top settings",
            "is_active": False,
        },
    ]

    # SETUP CUSTOM BTNs OF CUSTOM WIDGETS
    # Get sender() function when btn is clicked
    # ///////////////////////////////////////////////////////////////
    def setup_btns(self) -> PyPushButton | PyLeftMenuButton:
        if self.ui.title_bar.sender() is not None:
            return self.ui.title_bar.sender()
        elif self.ui.left_menu.sender() is not None:
            return self.ui.left_menu.sender()
        elif self.ui.left_column.sender() is not None:
            return self.ui.left_column.sender()

    # Add here all the threads that are used in the application
    def close_processes(self):
        # Close the stimulator connection if it is open
        if self.serial_port is not None:
            self.serial_port.close()
            self.serial_port = None

        # Close the subprocess if it is running
        # if self.process is not None:
        #     self.process.terminate()
        #     self.process.wait()
        #     self.process = None

    # SETUP MAIN WINDOW WITH CUSTOM PARAMETERS
    # ///////////////////////////////////////////////////////////////
    def setup_gui(self):
        # ROOT PATH
        # Path to root folder of this workspace using ..
        self.root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))

        # APP TITLE
        # ///////////////////////////////////////////////////////////////
        self.setWindowTitle(self.settings["app_name"])

        # REMOVE TITLE BAR
        # ///////////////////////////////////////////////////////////////
        if self.settings["custom_title_bar"]:
            self.setWindowFlag(Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground)

        # ADD GRIPS
        # ///////////////////////////////////////////////////////////////
        if self.settings["custom_title_bar"]:
            self.left_grip = PyGrips(self, "left", self.hide_grips)
            self.right_grip = PyGrips(self, "right", self.hide_grips)
            self.top_grip = PyGrips(self, "top", self.hide_grips)
            self.bottom_grip = PyGrips(self, "bottom", self.hide_grips)
            self.top_left_grip = PyGrips(self, "top_left", self.hide_grips)
            self.top_right_grip = PyGrips(self, "top_right", self.hide_grips)
            self.bottom_left_grip = PyGrips(self, "bottom_left", self.hide_grips)
            self.bottom_right_grip = PyGrips(self, "bottom_right", self.hide_grips)

        # LEFT MENUS / GET SIGNALS WHEN LEFT MENU BTN IS CLICKED / RELEASED
        # ///////////////////////////////////////////////////////////////
        # ADD MENUS
        self.ui.left_menu.add_menus(SetupMainWindow.add_left_menus)

        # SET SIGNALS
        self.ui.left_menu.clicked.connect(self.btn_clicked)
        self.ui.left_menu.released.connect(self.btn_released)

        # Route the new left-menu button to Page 10
        try:
            new_stim_btn = MainFunctions.get_left_menu_btn(self, "btn_stimulation_2")
            if new_stim_btn:
                new_stim_btn.clicked.connect(lambda: (
                    self.ui.left_menu.select_only_one("btn_stimulation_2"),
                    MainFunctions.set_page(self, self.ui.load_pages.page_10)
                ))
        except Exception:
            pass

        # TITLE BAR / ADD EXTRA BUTTONS
        # ///////////////////////////////////////////////////////////////
        # ADD MENUS
        self.ui.title_bar.add_menus(SetupMainWindow.add_title_bar_menus)

        # SET SIGNALS
        self.ui.title_bar.clicked.connect(self.btn_clicked)
        self.ui.title_bar.released.connect(self.btn_released)

        # ADD Title
        if self.settings["custom_title_bar"]:
            self.ui.title_bar.set_title(self.settings["app_name"])
        else:
            self.ui.title_bar.set_title("Welcome to PyOneDark")

        # LEFT COLUMN SET SIGNALS
        # ///////////////////////////////////////////////////////////////
        self.ui.left_column.clicked.connect(self.btn_clicked)
        self.ui.left_column.released.connect(self.btn_released)

        # SET INITIAL PAGE / SET LEFT AND RIGHT COLUMN MENUS
        # ///////////////////////////////////////////////////////////////
        MainFunctions.set_page(self, self.ui.load_pages.page_02)
        MainFunctions.set_left_column_menu(
            self,
            menu=self.ui.left_column.menus.menu_1,
            title="Settings Left Column",
            icon_path=Functions.set_svg_icon("icon_settings.svg"),
        )
        MainFunctions.set_right_column_menu(self, self.ui.right_column.menu_1)

        # ///////////////////////////////////////////////////////////////
        # EXAMPLE CUSTOM WIDGETS
        # Here are added the custom widgets to pages and columns that
        # were created using Qt Designer.
        # This is just an example and should be deleted when creating
        # your application.
        #
        # OBJECTS FOR LOAD PAGES, LEFT AND RIGHT COLUMNS
        # You can access objects inside Qt Designer projects using
        # the objects below:
        #
        # <OBJECTS>
        # LEFT COLUMN: self.ui.left_column.menus
        # RIGHT COLUMN: self.ui.right_column
        # LOAD PAGES: self.ui.load_pages
        # </OBJECTS>
        # ///////////////////////////////////////////////////////////////

        # LOAD SETTINGS
        # ///////////////////////////////////////////////////////////////
        settings = Settings()
        self.settings = settings.items

        # LOAD THEME COLOR
        # ///////////////////////////////////////////////////////////////
        themes = Themes()
        self.themes = themes.items

        # SET TOOLTIP STYLE
        # ///////////////////////////////////////////////////////////////
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(f"""
                QToolTip {{
                    background-color: {self.themes["app_color"]["dark_one"]};
                    color: {self.themes["app_color"]["text_foreground"]};
                    padding: 5px;
                    font: 800 9pt "Segoe UI";
                }}
            """)

        # LEFT COLUMN
        # ///////////////////////////////////////////////////////////////

        # PUSH BUTTON 1
        self.btn_load_subject_data = SetupMainWindow.create_std_push_btn(self.themes, text="  Load Subject Data")  # Spaces because of icon
        # Add icon to button
        icon = QIcon(Functions.set_svg_icon("icon_folder_open.svg"))
        self.btn_load_subject_data.setIcon(icon)
        self.btn_load_subject_data.setMaximumWidth(1e6)

        # PUSH BUTTON 2
        self.btn_save_subject_data = SetupMainWindow.create_std_push_btn(self.themes, text="  Save Subject Data")  # Spaces because of icon
        # Add icon to button
        icon = QIcon(Functions.set_svg_icon("icon_save.svg"))
        self.btn_save_subject_data.setIcon(icon)
        self.btn_save_subject_data.setMaximumWidth(1e6)

        # PUSH BUTTON 3
        self.btn_load_task_data = SetupMainWindow.create_std_push_btn(self.themes, text="  Load Task Data")  # Spaces because of icon
        # Add icon to button
        icon = QIcon(Functions.set_svg_icon("icon_folder_open.svg"))
        self.btn_load_task_data.setIcon(icon)
        self.btn_load_task_data.setMaximumWidth(1e6)

        # PUSH BUTTON 4
        self.btn_save_task_data = SetupMainWindow.create_std_push_btn(self.themes, text="  Save Task Data")  # Spaces because of icon
        # Add icon to button
        icon = QIcon(Functions.set_svg_icon("icon_save.svg"))
        self.btn_save_task_data.setIcon(icon)
        self.btn_save_task_data.setMaximumWidth(1e6)

        # BUTTONS CLICKED
        self.subject_data_path = self.root_path

        def load_subject_data():
            # Load subject data from JSON file
            file_name, _ = QFileDialog.getOpenFileName(
                self,
                "Load Subject Data",
                self.subject_data_path,
                "JSON Files (*.json);;All Files (*)",
            )
            if file_name:
                # Update the path to the subject data folder
                self.subject_data_path = os.path.dirname(file_name)
                with open(file_name, "r") as f:
                    data: dict = json.load(f)
                    # Populate the line edits with the data from the JSON file
                    self.lineEdit_first_name.setText(data.get("first_name", ""))
                    self.lineEdit_last_name.setText(data.get("last_name", ""))
                    self.lineEdit_subject_id.setText(data.get("subject_id", ""))
                    self.lineEdit_age.setText(data.get("age", ""))
                    self.lineEdit_height.setText(data.get("height", ""))
                    self.lineEdit_weight.setText(data.get("weight", ""))
                    self.channel_dict["Channel 0"].setText(data.get("channel_0", ""))
                    self.channel_dict["Channel 1"].setText(data.get("channel_1", ""))
                    self.channel_dict["Channel 2"].setText(data.get("channel_2", ""))
                    self.channel_dict["Channel 3"].setText(data.get("channel_3", ""))
                    self.channel_dict["Channel 4"].setText(data.get("channel_4", ""))
                    self.channel_dict["Channel 5"].setText(data.get("channel_5", ""))
                    self.channel_dict["Channel 6"].setText(data.get("channel_6", ""))
                    self.channel_dict["Channel 7"].setText(data.get("channel_7", ""))
                    # The max values are optional, so if they are not present, use the optimal values
                    self.channel_max_dict["Channel 0"].setText(data.get("channel_0_max", self.channel_dict["Channel 0"].text()))
                    self.channel_max_dict["Channel 1"].setText(data.get("channel_1_max", self.channel_dict["Channel 1"].text()))
                    self.channel_max_dict["Channel 2"].setText(data.get("channel_2_max", self.channel_dict["Channel 2"].text()))
                    self.channel_max_dict["Channel 3"].setText(data.get("channel_3_max", self.channel_dict["Channel 3"].text()))
                    self.channel_max_dict["Channel 4"].setText(data.get("channel_4_max", self.channel_dict["Channel 4"].text()))
                    self.channel_max_dict["Channel 5"].setText(data.get("channel_5_max", self.channel_dict["Channel 5"].text()))
                    self.channel_max_dict["Channel 6"].setText(data.get("channel_6_max", self.channel_dict["Channel 6"].text()))
                    self.channel_max_dict["Channel 7"].setText(data.get("channel_7_max", self.channel_dict["Channel 7"].text()))

        def load_task_data():
            # Load task data from JSON file
            file_name, _ = QFileDialog.getOpenFileName(
                self,
                "Load Task Data",
                self.tasks_path,
                "JSON Files (*.json);;All Files (*)",
            )
            if file_name:
                with open(file_name, "r") as f:
                    data: dict = json.load(f)
                    # Update the dropdown menu with the loaded tasks
                    actions = [QAction(name) for name in data["tasks"].keys()]
                    self.dropdown_btn_task.set_actions(actions)
                # Update path
                self.tasks_path = file_name

        def save_task_data():
            # Save task data to JSON file
            if self.dropdown_btn_task.text() == "New Task":
                # If the task name is "New Task", ask for a new name
                new_task_name, ok = QInputDialog.getText(self, "New Task Name", "Enter a new task name:")
                if ok and new_task_name:
                    self.dropdown_btn_task.setText(new_task_name)
                    self.dropdown_btn_task.menu().insertAction(self.dropdown_btn_task.menu().actions()[-1], QAction(new_task_name))
                    self.lineEdit_selected_task.setText(new_task_name)
                else:
                    return
            # Get the file name to save the task data
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save Task Data",
                self.tasks_path,
                "JSON Files (*.json);;All Files (*)",
            )
            # If the file name is not empty, save the task data
            if file_name:
                # Load other tasks in the menu from the previously loaded file
                with open(self.tasks_path, "r") as f:
                    data: dict = json.load(f)
                task_data = {
                    "burst_frequency": self.lineEdit_burst_frequency.text(),
                    "burst_duration": self.lineEdit_burst_duration.text(),
                    "pulse_deadtime": self.lineEdit_pulse_deadtime.text(),
                    "interpulse_interval": self.lineEdit_interpulse_interval.text(),
                    "carrier_frequency": self.lineEdit_carrier_frequency.text(),
                    "electrode_placement": self.dropdown_btn_placement.text(),
                    "gait_detection_toggle": self.gait_toggle.isChecked(),
                    "tscs_toggle": self.tscs_toggle.isChecked(),
                    "fes_toggle": self.fes_toggle.isChecked(),
                    "imu_toggle": self.imu_toggle.isChecked(),
                    "walking_speed_toggle": self.walking_speed_toggle.isChecked(),
                    "use_4_imus": self.imu4_radio_btn.isChecked(),
                    "do_closed_loop": self.closed_loop_toggle.isChecked(),
                    "fsr_toggle": self.fsr_toggle.isChecked(),
                    "phase_detection_toggle": self.phase_toggle.isChecked(),
                    "use_subphases": self.subphase_radio_btn.isChecked(),
                }
                # Add the new task parameters
                data["tasks"][self.dropdown_btn_task.text()] = task_data
                # Remove and readd "New Task" so that it is always the last action
                data["tasks"].pop("New Task")
                data["tasks"]["New Task"] = {}
                with open(file_name, "w") as f:
                    json.dump(data, f)
                    print("Data saved at: {}".format(file_name))
                # Update path
                self.tasks_path = file_name

        def save_subject_data():
            # Save subject data to JSON file
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save Subject Data",
                self.subject_data_path + "/subj{}.json".format(self.lineEdit_subject_id.text()),
                os.path.join(self.current_session_path or self.subject_data_path, f"subj{self.lineEdit_subject_id.text()}.json"),
                "JSON Files (*.json);;All Files (*)",
            )
            if file_name:
                # Update the path to the subject data folder
                self.subject_data_path = os.path.dirname(file_name)
                data = {
                    "first_name": self.lineEdit_first_name.text(),
                    "last_name": self.lineEdit_last_name.text(),
                    "subject_id": self.lineEdit_subject_id.text(),
                    "age": self.lineEdit_age.text(),
                    "height": self.lineEdit_height.text(),
                    "weight": self.lineEdit_weight.text(),
                    "channel_0": self.channel_dict["Channel 0"].text(),
                    "channel_1": self.channel_dict["Channel 1"].text(),
                    "channel_2": self.channel_dict["Channel 2"].text(),
                    "channel_3": self.channel_dict["Channel 3"].text(),
                    "channel_4": self.channel_dict["Channel 4"].text(),
                    "channel_5": self.channel_dict["Channel 5"].text(),
                    "channel_6": self.channel_dict["Channel 6"].text(),
                    "channel_7": self.channel_dict["Channel 7"].text(),
                    "channel_0_max": self.channel_max_dict["Channel 0"].text(),
                    "channel_1_max": self.channel_max_dict["Channel 1"].text(),
                    "channel_2_max": self.channel_max_dict["Channel 2"].text(),
                    "channel_3_max": self.channel_max_dict["Channel 3"].text(),
                    "channel_4_max": self.channel_max_dict["Channel 4"].text(),
                    "channel_5_max": self.channel_max_dict["Channel 5"].text(),
                    "channel_6_max": self.channel_max_dict["Channel 6"].text(),
                    "channel_7_max": self.channel_max_dict["Channel 7"].text(),
                }
                with open(file_name, "w") as f:
                    json.dump(data, f)
                    print("Data saved at: {}".format(file_name))

        # CONNECT BUTTONS
        self.btn_load_subject_data.clicked.connect(load_subject_data)
        self.btn_save_subject_data.clicked.connect(save_subject_data)
        self.btn_load_task_data.clicked.connect(load_task_data)
        self.btn_save_task_data.clicked.connect(save_task_data)

        # ADD WIDGETS
        self.ui.left_column.menus.load_btn_layout.addWidget(self.btn_load_subject_data)
        self.ui.left_column.menus.save_btn_layout.addWidget(self.btn_save_subject_data)
        self.ui.left_column.menus.load_task_btn_layout.addWidget(self.btn_load_task_data)
        self.ui.left_column.menus.save_task_btn_layout.addWidget(self.btn_save_task_data)

        # Change frame color
        self.frame_stylesheet = (
            f"QFrame {{\n"
            f"  background-color: {self.themes['app_color']['bg_two']};\n"
            f"}}\n"
            f"QFrame:disabled {{\n"
            f"  background-color: {self.themes['app_color']['bg_three']};\n"
            f"  border: 1px solid {self.themes['app_color']['bg_one']};\n"
            f"  border-radius: 5px;\n"
            f"}}\n"
        )
        self.ui.left_column.menus.menu_2_break_line_frame.setStyleSheet(self.frame_stylesheet)

        # PAGES
        # ///////////////////////////////////////////////////////////////

        # PAGE 1 - SETUP HOME PAGE
        # ///////////////////////////////////////////////////////////////
        # PUSH BUTTON 1
        self.stop_btn = PyPushButton(
            text="Stop",
            radius=8,
            color=self.themes["app_color"]["text_foreground"],
            bg_color="darkred",
            bg_color_hover=self.themes["app_color"]["red"],
            bg_color_pressed=self.themes["app_color"]["pink"],
        )
        self.stop_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Add fontsize of 50 to stylesheet
        stylesheet = self.stop_btn.styleSheet()
        first_linebreak = stylesheet.find("border")
        stylesheet = stylesheet[:first_linebreak] + "font-size: 50px;\n" + stylesheet[first_linebreak:]
        self.stop_btn.setStyleSheet(stylesheet)
        # Safe label original text
        self.title_label = self.ui.load_pages.title_label.text()

        # PUSH BUTTON 2
        self.subject_info_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Next page")
        self.subject_info_btn.setMaximumHeight(BUTTON_HEIGHT_HOME)

        # PUSH BUTTON 3
        self.task_info_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Task Information")
        self.task_info_btn.setMaximumHeight(BUTTON_HEIGHT_HOME)

        # PUSH BUTTON 4
        self.safe_info_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Save Information")
        self.safe_info_btn.setMaximumHeight(BUTTON_HEIGHT_HOME)

        # PUSH BUTTON 5
        self.stimulation_info_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Stimulation Parameters")
        self.stimulation_info_btn.setMaximumHeight(BUTTON_HEIGHT_HOME)

        # PUSH BUTTON 6
        self.setup_fsr_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Setup FSR")
        self.setup_fsr_btn.setMaximumHeight(BUTTON_HEIGHT_HOME)

        # PUSH BUTTON 7
        self.setup_imu_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Setup IMU")
        self.setup_imu_btn.setMaximumHeight(BUTTON_HEIGHT_HOME)

        # PUSH BUTTON 8
        self.start_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Confirm and Start")
        self.start_btn.setMaximumHeight(BUTTON_HEIGHT_HOME)

        # PUSH BUTTON 9
        self.scan_port_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Scan Port")

        # PUSH BUTTON 10
        self.connect_port_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Connect Port")

        # PUSH BUTTON 11
        self.disconnect_port_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Disconnect Port")

        # COMBO BOX 1 - PORT SELECTION
        self.dropbox_port = PyDropbox(
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            disable_color=self.themes["app_color"]["dark_four"],
        )

        # COMBO BOX 2 - BAUDRATE SELECTION
        self.dropbox_baudrate = PyDropbox(
            item_list=["9600", "115200", "230400", "250000", "500000", "921600"],
            default_value="921600",
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            disable_color=self.themes["app_color"]["dark_four"],
        )

        # SET FRAME BORDER
        self.ui.load_pages.stimulator_frame.setStyleSheet(
            f"QFrame#stimulator_frame {{border: 2px solid {self.themes['app_color']['bg_two']}; border-radius: 4px;}}"
        )

        # BUTTON CLICKED
        def subj_clicked():
            self.ui.left_menu.select_only_one("btn_stimulation_2")
            MainFunctions.set_page(self, self.ui.load_pages.page_10)

        def task_clicked():
            self.ui.left_menu.select_only_one("btn_task_info")
            MainFunctions.set_page(self, self.ui.load_pages.page_03)

        def safe_clicked():
            self.ui.left_menu.select_only_one("btn_subject_info")
            MainFunctions.set_page(self, self.ui.load_pages.page_02)

        def stim_clicked():
            self.ui.left_menu.select_only_one("btn_stimulation")
            MainFunctions.set_page(self, self.ui.load_pages.page_05)
        
        def new_stim_clicked():
            self.ui.left_menu.select_only_one("btn_stimulation_2")
            MainFunctions.set_page(self, self.ui.load_pages.page_06)

        def fsr_clicked():
            self.ui.left_menu.select_only_one("none")
            MainFunctions.set_page(self, self.ui.load_pages.page_08)

        def imu_clicked():
            self.ui.left_menu.select_only_one("none")
            MainFunctions.set_page(self, self.ui.load_pages.page_09)
        
        # Open directly the IMU GUI without going trough the page 9
        # def open_imu_gui():
        #     if self.process is not None:
        #         retcode = self.process.poll()
        #         if retcode is None:
        #             # Process is still running
        #             return
        #     self.process = subprocess.Popen(["./DeployDir/MovellaGUI"])

        def start_clicked():
            # Stop timer (don't want it running during experiment)
            if self.plot_dialog is not None:
                self.plot_dialog.timer.stop()
            self.angle_calibrator.stop()

            # Deselect all left menu buttons
            self.ui.left_menu.deselect_all()

            # Add confirm image
            svg_path = Functions.set_svg_image("modified_image.svg")
            self.confirm_image.load(svg_path)
            self.confirm_image.renderer().setAspectRatioMode(Qt.KeepAspectRatio)
            self.ui.load_pages.image_info_layout.addWidget(self.confirm_image)

            # Update file name (important for time)
            self.lineEdit_file_name.setText(
                SetupMainWindow.create_file_name(FILE_NAME_FORMAT, self.subject_info_dict, [])
            )

            # Send gait phases mapping to backend
            _send_gait_mapping_to_backend()

            # Update confirmation page
            SetupMainWindow.update_confirm_page(self.confirm_dict)

            # Load confirmation page (PAGE 6)
            MainFunctions.set_page(self, self.ui.load_pages.page_06)
        
        def _build_user_gait_mapping():
            # Returns a dict: {Phase: [ [left_targets], [right_targets] ]}
            # Use self.page10_gait_model_map (target -> set of phases)
            
            # ============ harded coded in gait_model_stimulation_functions the pre-set gait model that takes into account the targets for each phase for both FES and tSCS
            
            # if self.fes_toggle.isChecked():
            #     # FES mapping: Only swing phase triggers stimulation
                
            #         #BF: Biceps Femoris (hamstrings)
            #         #TA : Tibialis Anterior
            #         #GA: Gastrocnemius
            #         #VM: Vastus Medialis  
                    
            #     fes_map = {
            #         Phase.MID_SWING: [["BF_left", "TA_left"], ["BF_right", "TA_right"]],
            #         Phase.STANCE: [[], []],  # No stimulation during stance
            #         Phase.MID_STANCE: [["GA_left"], ["GA_right"]],
            #         Phase.PRE_SWING: [["GA_left"], ["GA_right"]],
            #         Phase.TERMINAL_SWING: [["VM_left", "TA_left"], ["VM_right", "TA_right"]],
            #         Phase.SWING: [[], []],
            #         Phase.LOADING_RESPONSE: [["BF_left", "TA_left" , "VM_left"], ["BF_right", "TA_right", "VM_right"]],
            #         Phase.UNKNOWN: [["unknown"], ["unknown"]]
            #     }
            #     return fes_map
            #else:
            user_map = {}
            # Reverse: for each phase, collect left/right targets
            for phase in Phase:
                if phase == Phase.UNKNOWN:
                    continue
                left_targets = []
                right_targets = []
                for tgt, phases in self.page10_gait_model_map.items():
                    if phase in phases:
                        # Use your target key map to determine left/right
                        # Example: if "left" in tgt, it's left; if "right" in tgt, it's right
                        if "left" in tgt:
                            left_targets.append(tgt)
                        elif "right" in tgt:
                            right_targets.append(tgt)
                user_map[phase] = [left_targets, right_targets]
            # Always add UNKNOWN phase
            user_map[Phase.UNKNOWN] = [["unknown"], ["unknown"]]
            return user_map

        def _send_gait_mapping_to_backend():
            user_gait_map = _build_user_gait_mapping()
            # Pass this dict to your backend instead of MUSCULAR_GROUP_SELECTION
            # For example, store it in a global, or pass as an argument to stimulation functions
            # Example:
            # stimulator.gait_model_stimulation_functions.MUSCULAR_GROUP_SELECTION = user_gait_map

            import stimulator.gait_model_stimulation_functions as gait_mod
            gait_mod.MUSCULAR_GROUP_SELECTION = user_gait_map

        def scan_clicked():
            # Refresh the list of serial devices
            self.dropbox_port.setEnabled(False)
            self.dropbox_port.clear()
            self.dropbox_port.setCurrentText("Scanning...")
            ports = list_serial_devices()
            self.dropbox_port.clear()
            if ports:
                self.dropbox_port.addItems(ports)
                _update_connection_status("Scanned")
            else:
                self.dropbox_port.addItem("No devices found")
                self.dropbox_port.setEnabled(False)
                _update_connection_status("Not Connected")

        self.serial_port: Optional[Serial] = None

        def connect_clicked():
            # Connect and save the serial port
            if self.serial_port is not None:
                close_serial_port(self.serial_port)
            if self.dropbox_port.currentText() != "":
                try:
                    self.serial_port = open_serial_port(self.dropbox_port.currentText().split(" ")[0], self.dropbox_baudrate.currentText())
                    self.dropbox_baudrate.setEnabled(False)
                    self.dropbox_port.setEnabled(False)
                    # Close all channels
                    StimulatorParameters.close_all_channels(self.serial_port)
                    _update_connection_status("Connected")

                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Connection Error",
                        f"Failed to connect to the serial port: {e}\nPlease check the port and baudrate settings and try again.",
                    )
                    # If connection fails, reset the serial port
                    self.serial_port = None
                    self.dropbox_baudrate.setEnabled(True)
                    self.dropbox_port.setEnabled(True)
                    _update_connection_status("Not Connected")


        def close_clicked():
            # Close the serial port if it is open
            if self.serial_port is not None:
                close_serial_port(self.serial_port)
                self.serial_port = None
                self.dropbox_baudrate.setEnabled(True)
                self.dropbox_port.setEnabled(True)
                _update_connection_status("Not Connected")

        # CONNECT BUTTONS
        self.stop_btn.clicked.connect(self.stop_clicked)
        self.subject_info_btn.clicked.connect(subj_clicked)
        self.task_info_btn.clicked.connect(task_clicked)
        self.safe_info_btn.clicked.connect(safe_clicked)
        self.stimulation_info_btn.clicked.connect(stim_clicked)
        self.setup_fsr_btn.clicked.connect(fsr_clicked)
        #self.setup_imu_btn.clicked.connect(open_imu_gui) Dans version to take u straight to movella dots 
        self.setup_imu_btn.clicked.connect(imu_clicked)
        self.start_btn.clicked.connect(start_clicked)

        self.scan_port_btn.clicked.connect(scan_clicked)
        self.connect_port_btn.clicked.connect(connect_clicked)
        self.disconnect_port_btn.clicked.connect(close_clicked)

        # Return key triggers the buttons
        self.stop_btn.setAutoDefault(True)
        self.subject_info_btn.setAutoDefault(True)
        self.task_info_btn.setAutoDefault(True)
        self.safe_info_btn.setAutoDefault(True)
        self.stimulation_info_btn.setAutoDefault(True)
        self.start_btn.setAutoDefault(True)

        # ADD WIDGETS
        self.ui.load_pages.stop_layout.addWidget(self.stop_btn)
        #self.ui.load_pages.select_layout.addWidget(self.safe_info_btn, 0, 1)
        #self.ui.load_pages.select_layout.addWidget(self.task_info_btn, 0, 2)
        #self.ui.load_pages.select_layout.addWidget(self.stimulation_info_btn, 1, 0)
        self.ui.load_pages.select_layout.addWidget(self.setup_fsr_btn, 0, 0)
        self.ui.load_pages.select_layout.addWidget(self.setup_imu_btn, 0, 1)

        self.ui.load_pages.stimulator_layout.addWidget(self.dropbox_port, 0, 1, 1, 2)
        self.ui.load_pages.stimulator_layout.addWidget(self.dropbox_baudrate, 1, 1, 1, 2)

        # Ensure columns 1-2 expand like the dropboxes
        self.ui.load_pages.stimulator_layout.setColumnStretch(0, 0)
        self.ui.load_pages.stimulator_layout.setColumnStretch(1, 1)
        self.ui.load_pages.stimulator_layout.setColumnStretch(2, 1)

        # --- Connection Status row (below Baud Rate) ---
        # Label on the left, long cell on the right spanning two columns
        self.connection_status_label = QLabel("Connection Status")
        self.connection_status_label.setStyleSheet("font-size: 15pt; font-weight:500;")

        # Use standard line edit style, but make it read-only and centered
        
        # Read-only status field styled similar to PyDropbox
        self.connection_status_value = QLineEdit("Not Connected")
        self.connection_status_value.setReadOnly(True)
        self.connection_status_value.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.connection_status_value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.connection_status_value.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.connection_status_value.setMinimumHeight(25)
        self.connection_status_value.setMaximumHeight(25)
        self.connection_status_value.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.themes['app_color']['dark_one']};
                color: {self.themes['app_color']['text_foreground']};
                border-radius: 8px;
                border: 2px solid transparent;
                padding-left: 10px;
                padding-right: 10px;
            }}
            QLineEdit:disabled {{
                background-color: {self.themes['app_color']['dark_four']};
            }}
        """)

        # Place the status row at row 2 (under Baud rate), spanning two columns
        self.ui.load_pages.stimulator_layout.addWidget(self.connection_status_label, 2, 0)
        self.ui.load_pages.stimulator_layout.addWidget(self.connection_status_value, 2, 1, 1, 2)

        self.ui.load_pages.stimulator_layout.addWidget(self.scan_port_btn, 3, 0)
        self.ui.load_pages.stimulator_layout.addWidget(self.connect_port_btn, 3, 1)
        self.ui.load_pages.stimulator_layout.addWidget(self.disconnect_port_btn, 3, 2)

        # --- Connection Status (centered below buttons) ---
        # Helper to update status text
        def _update_connection_status(text: str):
            self.connection_status_value.setText(text)
            _set_connection_status_style(text.strip().lower() == "connected")

        
        # Helper to update status text
        def _set_connection_status_style(connected: bool):
            bg = self.themes["app_color"]["dark_four"] if connected else self.themes["app_color"]["dark_one"]
            self.connection_status_value.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {bg};
                    color: {self.themes['app_color']['text_foreground']};
                    border-radius: 8px;
                    border: 2px solid transparent;
                    padding-left: 10px;
                    padding-right: 10px;
                }}
                QLineEdit:disabled {{
                    background-color: {self.themes['app_color']['dark_four']};
                }}
            """)

        # Initialize connection status 
        _update_connection_status("Not Connected")
        
        self.ui.load_pages.start_layout.addWidget(self.start_btn, 0, 0)
        self.ui.load_pages.start_layout.addWidget(self.subject_info_btn, 0, 1)

        # HIDE STOP WIDGET
        self.ui.load_pages.stop_btn_widget.setVisible(False)

        # HIDE TIME LABEL
        self.ui.load_pages.time_label.setVisible(False)

        # PAGE 2 - SUBJECT INFORMATION
        # ///////////////////////////////////////////////////////////////

        # ///////////////////////////////////////////////////////////////

        # -------- Subject selector (outside frames, at the very top) --------
        def _scan_patient_dirs(base_dir: str) -> tuple[list[str], dict[str, str]]:
            subjects: list[str] = []
            mapping: dict[str, str] = {}
            try:
                if os.path.isdir(base_dir):
                    for name in sorted(os.listdir(base_dir)):
                        abs_path = os.path.join(base_dir, name)
                        if not os.path.isdir(abs_path):
                            continue
                        if name.startswith("Patient_"):
                            # Display ID like "Patient_001"
                            parts = name.split("_")
                            subj = "_".join(parts[:2]) if len(parts) >= 2 else name
                            subjects.append(subj)
                            mapping[subj] = abs_path
            except Exception as e:
                print(f"Patient scan failed: {e}")
            # Unique + sorted
            return sorted(set(subjects)), mapping
        
        # Compute next session_N directory under a patient folder
        def _next_session_dir(patient_folder: str) -> str:
            # If the folder doesn't exist yet, default to session_1 without scanning
            if not patient_folder or not os.path.isdir(patient_folder):
                return os.path.join(patient_folder, "session_1")
            next_idx = 1
            try:
                for name in os.listdir(patient_folder):
                    m = re.fullmatch(r"session_(\d+)", name)
                    if m:
                        next_idx = max(next_idx, int(m.group(1)) + 1)
            except Exception as e:
                print(f"Session scan failed: {e}")
            return os.path.join(patient_folder, f"session_{next_idx}")
        
        # Compute the session dir for a given phase key without creating folders
        def _compute_session_dir_for_phase(phase_key: str) -> str:
            try:
                pf = getattr(self, "selected_patient_folder", "")  # ...\phase1\Patient_XXX
                if not pf:
                    return self.lineEdit_safe_path.text().strip() or ""

                if phase_key == "phase_1":
                    return _next_session_dir(pf)

                # Phase 2 group selection → under phase2/groupN/Patient_XXX
                base_root = os.path.dirname(os.path.dirname(pf))  # ...\NeuroPulseAnalyzer_Dataset
                group_name = "group1" if phase_key.endswith("_group_1") else "group2"
                patient_name = os.path.basename(pf)
                phase2_patient_dir = os.path.join(base_root, "phase2", group_name, patient_name)

                # If it doesn't exist yet, preview session_1 directly without logging
                if not os.path.isdir(phase2_patient_dir):
                    return os.path.join(phase2_patient_dir, "session_1")

                # Else, scan to compute next session_N
                return _next_session_dir(phase2_patient_dir)
            except Exception:
                # Stay silent and keep current value
                return self.lineEdit_safe_path.text().strip()

        # Hook subject selection now that line edits exist
        def _read_patient_info_to_dict(xlsx_path: str) -> dict:
            try:
                import pandas as pd
                df = pd.read_excel(xlsx_path)
                if df.shape[1] == 2:
                    keys = [str(k).strip().lower() for k in df.iloc[:, 0].tolist()]
                    vals = df.iloc[:, 1].tolist()
                    return dict(zip(keys, vals))
                else:
                    row = df.iloc[0].to_dict()
                    return {str(k).strip().lower(): v for k, v in row.items()}
            except Exception as e:
                print(f"Failed to read {xlsx_path}: {e}")
                return {}

        def on_subject_selected(subj_id: str):
            # If Custom/None, clear fields and stop (no prefill from files)
            if not subj_id or subj_id in ("New", "Select Subject"):
                for le in [
                    self.lineEdit_subject_id,
                    self.lineEdit_first_name,
                    self.lineEdit_last_name,
                    self.lineEdit_age,
                    self.lineEdit_height,
                    self.lineEdit_weight,
                ]:
                    le.setText("")
                self.dropbox_sex.setCurrentText("Male")
                self.dropbox_injury.setCurrentIndex(-1)
                self.dropbox_affected_limb.setCurrentIndex(-1)
                return
            folder = self.patient_map.get(subj_id, "")
            if not folder:
                return
            self.lineEdit_subject_id.setText(subj_id)
            xlsx = os.path.join(folder, "patient_info.xlsx")
            info = _read_patient_info_to_dict(xlsx)
            print(info)

            # Normalize + set fields if present
            def _set_line(le: PyLineEdit, key: str):
                if key in info and info[key] is not None:
                    le.setText(str(info[key]))


            _set_line(self.lineEdit_first_name, "first name")
            _set_line(self.lineEdit_last_name, "last name")
            _set_line(self.lineEdit_age, "age")
            _set_line(self.lineEdit_height, "height")
            _set_line(self.lineEdit_weight, "weight")

            sex = str(info.get("sex", "")).strip().capitalize()
            if sex in ("Male", "Female", "Other"):
                self.dropbox_sex.setCurrentText(sex)

            injury_type = str(info.get("injury type", "")).strip().capitalize()
            print(injury_type)
            if injury_type in ("Stroke", "Spinal Cord Injury", "Other"):
                self.dropbox_injury.setCurrentText(injury_type)
            else:
                self.dropbox_injury.setCurrentIndex(-1)

            affected_limb = str(info.get("affected limb", "")).strip().capitalize()
            print(affected_limb)
            if affected_limb in ("Left", "Right", "Both"):
                self.dropbox_affected_limb.setCurrentText(affected_limb)
            else:
                self.dropbox_affected_limb.setCurrentIndex(-1)
            
            # Prepare next session folder under the selected patient and set it as default save path
            self.selected_patient_folder = folder
            session_dir = _next_session_dir(folder)
            self.current_session_path = session_dir
            self.lineEdit_safe_path.setText(session_dir)
            self.lineEdit_safe_path.setToolTip(session_dir)


        # Use a runtime-configurable base directory (default = PATIENTS_BASE_DIR)
        self.patients_base_dir = PATIENTS_BASE_DIR
        subjects, self.patient_map = _scan_patient_dirs(self.patients_base_dir)

        self.subject_selector_widget = QWidget(self.ui.load_pages.page_02)
        self.subject_selector_layout = QHBoxLayout(self.subject_selector_widget)
        self.subject_selector_layout.setContentsMargins(0, 0, 0, 9)
        self.subject_selector_layout.setSpacing(6)

        self.subject_selector_label = QLabel("Subject ID")
        self.subject_selector_label.setStyleSheet("font-size: 14pt;")
        self.subject_selector_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # Keep label from expanding and pushing the combo to the middle
        self.subject_selector_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        subject_items = ["New"] + subjects
        self.subject_id_dropbox = PyDropbox(
            item_list=subject_items,
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            disable_color=self.themes["app_color"]["dark_four"],
        )
        self.subject_id_dropbox.setMinimumHeight(LINE_HEIGHT)
        self.subject_id_dropbox.setMaximumWidth(LINE_WIDTH_MID)
        # Ensure default index is "Custom" even if the widget auto-selects first item
        self.subject_id_dropbox.setCurrentText("New")
        # Fix horizontal growth so it stays next to the label
        self.subject_id_dropbox.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.subject_selector_layout.addWidget(self.subject_selector_label)
        self.subject_selector_layout.addWidget(self.subject_id_dropbox)

        # Browse button to change dataset base folder
        self.dataset_browse_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Browse Dataset")
        self.dataset_browse_btn.setMaximumHeight(LINE_HEIGHT)
        self.dataset_browse_btn.setIcon(QIcon(Functions.set_svg_icon("icon_folder_open.svg")))
        self.subject_selector_layout.addWidget(self.dataset_browse_btn)

        # Save-to path (moved from Page 4 -> Page 2)
        self.save_path_label = QLabel("Save To")
        self.save_path_label.setStyleSheet("font-size: 12pt;")
        self.save_path_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
      
        # Reuse same styling as Page 4, but create here so it's available app-wide
        self.lineEdit_safe_path = PyLineEdit(
            text="",
            place_holder_text=self.root_path,
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            adjust_size=True,
            constraints=[300, 30, 900, 30],
        )
        self.lineEdit_safe_path.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.lineEdit_safe_path.setText(self.root_path)
        self.lineEdit_safe_path.setReadOnly(True)
        self.lineEdit_safe_path.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Save-path browse button
        self.save_path_browse_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Browse")
        self.save_path_browse_btn.setMaximumHeight(LINE_HEIGHT)
        self.save_path_browse_btn.setIcon(QIcon(Functions.set_svg_icon("icon_folder_open.svg")))

        def browse_save_path():
            path = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.lineEdit_safe_path.text() or self.root_path)
            if path:
                self.lineEdit_safe_path.setText(path)
        self.save_path_browse_btn.clicked.connect(browse_save_path)

        # Keep current base dir as tooltip on the selector
        self.subject_id_dropbox.setToolTip(f"Dataset: {self.patients_base_dir}")

        def _refresh_subjects():
            subs, self.patient_map = _scan_patient_dirs(self.patients_base_dir)
            # Avoid triggering on_subject_selected while repopulating
            self.subject_id_dropbox.blockSignals(True)
            self.subject_id_dropbox.clear()
            self.subject_id_dropbox.addItem("New")
            if subs:
                self.subject_id_dropbox.addItems(subs)
            self.subject_id_dropbox.setCurrentText("New")
            self.subject_id_dropbox.blockSignals(False)
            self.subject_id_dropbox.setToolTip(f"Dataset: {self.patients_base_dir}")

        def browse_dataset_dir():
            path = QFileDialog.getExistingDirectory(self, "Select NeuroPulseAnalyzer Dataset", self.patients_base_dir)
            if path:
                self.patients_base_dir = path
                _refresh_subjects()

        self.dataset_browse_btn.clicked.connect(browse_dataset_dir)

        # Insert the selector above all frames (top of Page 2)
        self.ui.load_pages.page_2_layout.insertWidget(1, self.subject_selector_widget, 0, Qt.AlignmentFlag.AlignLeft)
        
        ########## DEMOGRAPHICS FRAME
        # Create a bordered frame with a small top-left title
        self.demographics_frame = QFrame(self.ui.load_pages.page_02)
        self.demographics_frame.setObjectName("demographics_frame")
        self.demographics_frame.setStyleSheet(
            f"QFrame#demographics_frame {{border: 2px solid {self.themes['app_color']['bg_two']}; border-radius: 4px;}}"
        )
        self.demographics_layout = QVBoxLayout(self.demographics_frame)
        self.demographics_layout.setContentsMargins(9, 9, 9, 9)
        self.demographics_layout.setSpacing(6)

        # Title (top-left)
        self.demographics_title = QLabel("Demographics")
        self.demographics_title.setStyleSheet("font-size: 14pt;")
        self.demographics_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.demographics_layout.addWidget(self.demographics_title, 0, Qt.AlignmentFlag.AlignLeft)

        # Form grid inside the frame
        self.demographics_form = QWidget(self.demographics_frame)
        self.demographics_form_layout = QGridLayout(self.demographics_form)
        self.demographics_form_layout.setContentsMargins(0, 0, 0, 0)
        self.demographics_form_layout.setHorizontalSpacing(9)
        self.demographics_form_layout.setVerticalSpacing(6)
        self.demographics_layout.addWidget(self.demographics_form)

        # Sex selector
        self.dropbox_sex = PyDropbox(
            item_list=["Male", "Female", "Other"],
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            disable_color=self.themes["app_color"]["dark_four"],
        )

        
        # Make size consistent with line edits
        self.dropbox_sex.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.dropbox_sex.setMinimumHeight(LINE_HEIGHT)
        self.dropbox_sex.setMaximumWidth(LINE_WIDTH)

        # Demographics grid: labels + fields (2 columns) with centered alignment and bigger font
        label_style = "font-size: 14pt;"  # match Page 2 labels
        self.lbl_first_name = QLabel("First Name")
        self.lbl_first_name.setStyleSheet(label_style)
        self.lbl_first_name.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.lbl_last_name = QLabel("Last Name")
        self.lbl_last_name.setStyleSheet(label_style)
        self.lbl_last_name.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.lbl_age = QLabel("Age")
        self.lbl_age.setStyleSheet(label_style)
        self.lbl_age.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.lbl_sex = QLabel("Sex")
        self.lbl_sex.setStyleSheet(label_style)
        self.lbl_sex.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Insert the frame near the top of page_02 (right after the page title)
        # Title label is index 0 in page_2_layout, so insert at 1
        self.ui.load_pages.page_2_layout.insertWidget(2, self.demographics_frame)


        ########## BIOMETRICS FRAME
        # Create a bordered frame with a small top-left title
        self.biometric_frame = QFrame(self.ui.load_pages.page_02)
        self.biometric_frame.setObjectName("biometric_frame")
        self.biometric_frame.setStyleSheet(
            f"QFrame#biometric_frame {{border: 2px solid {self.themes['app_color']['bg_two']}; border-radius: 4px;}}"
        )
        self.biometric_layout = QVBoxLayout(self.biometric_frame)
        self.biometric_layout.setContentsMargins(9, 9, 9, 9)
        self.biometric_layout.setSpacing(6)

        # Title (top-left)
        self.biometric_title = QLabel("Biometrics")
        self.biometric_title.setStyleSheet("font-size: 14pt;")
        self.biometric_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.biometric_layout.addWidget(self.biometric_title, 0, Qt.AlignmentFlag.AlignLeft)

        # Form grid inside the frame
        self.biometric_form = QWidget(self.biometric_frame)
        self.biometric_form_layout = QGridLayout(self.biometric_form)
        self.biometric_form_layout.setContentsMargins(0, 0, 0, 0)
        self.biometric_form_layout.setHorizontalSpacing(9)
        self.biometric_form_layout.setVerticalSpacing(6)
        self.biometric_layout.addWidget(self.biometric_form)

        # Biometrics grid: labels + fields (2 columns) with centered alignment and bigger font
        label_style = "font-size: 14pt;"  # match Page 2 labels
        self.lbl_weight = QLabel("Weight")
        self.lbl_weight.setStyleSheet(label_style)
        self.lbl_weight.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.lbl_height = QLabel("Height")
        self.lbl_height.setStyleSheet(label_style)
        self.lbl_height.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Insert the frame near the top of page_02 (right after the page title)
        # Title label is index 0 in page_2_layout, so insert at 1
        self.ui.load_pages.page_2_layout.insertWidget(3, self.biometric_frame)

        ########## MEDICAL HISTORY FRAME
        # Create a bordered frame with a small top-left title
        self.medical_history_frame = QFrame(self.ui.load_pages.page_02)
        self.medical_history_frame.setObjectName("medical_history_frame")
        self.medical_history_frame.setStyleSheet(
            f"QFrame#medical_history_frame {{border: 2px solid {self.themes['app_color']['bg_two']}; border-radius: 4px;}}"
        )
        self.medical_history_layout = QVBoxLayout(self.medical_history_frame)
        self.medical_history_layout.setContentsMargins(9, 9, 9, 2)
        self.medical_history_layout.setSpacing(4)

        # Title (top-left)
        self.medical_history_title = QLabel("Medical History")
        self.medical_history_title.setStyleSheet("font-size: 14pt;")
        self.medical_history_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.medical_history_layout.addWidget(self.medical_history_title, 0, Qt.AlignmentFlag.AlignLeft)

        # Form grid inside the frame
        self.medical_history_form = QWidget(self.medical_history_frame)
        self.medical_history_form_layout = QGridLayout(self.medical_history_form)
        self.medical_history_form_layout.setContentsMargins(0, 0, 0, 0)
        self.medical_history_form_layout.setHorizontalSpacing(9)
        self.medical_history_form_layout.setVerticalSpacing(6)
        self.medical_history_layout.addWidget(self.medical_history_form)

        # Type injury selector
        self.dropbox_injury = PyDropbox(
            item_list=["Stroke", "Spinal Cord Injury", "Other"],
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            disable_color=self.themes["app_color"]["dark_four"],
        )
        

        # Make size consistent with line edits
        self.dropbox_injury.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.dropbox_injury.setMinimumHeight(LINE_HEIGHT)
        self.dropbox_injury.setMaximumWidth(LINE_WIDTH)
        # Show placeholder and no selection by default (New/Custom)
        self.dropbox_injury.setEditable(False)
        self.dropbox_injury.setPlaceholderText("Injury type")
        self.dropbox_injury.setCurrentIndex(-1)

        # Affected LIMB
        self.dropbox_affected_limb = PyDropbox(
            item_list=["Left", "Right", "Both"],
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            disable_color=self.themes["app_color"]["dark_four"],
        )

        # Make size consistent with line edits
        self.dropbox_affected_limb.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.dropbox_affected_limb.setMinimumHeight(LINE_HEIGHT)
        self.dropbox_affected_limb.setMaximumWidth(LINE_WIDTH)
        # Show placeholder and no selection by default (New/Custom)
        self.dropbox_affected_limb.setEditable(False)
        self.dropbox_affected_limb.setPlaceholderText("Affected limb")
        self.dropbox_affected_limb.setCurrentIndex(-1)

       

        # Medical history grid: labels + fields (2 columns) with centered alignment and bigger font
        label_style = "font-size: 14pt;"  # match Page 2 labels
        self.lbl_injury_type = QLabel("Injury Type")
        self.lbl_injury_type.setStyleSheet(label_style)
        self.lbl_injury_type.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.lbl_affected_limb = QLabel("Affected Limb")
        self.lbl_affected_limb.setStyleSheet(label_style)
        self.lbl_affected_limb.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Insert the frame near the top of page_02 (right after the page title)
        # Title label is index 0 in page_2_layout, so insert at 1
        self.ui.load_pages.page_2_layout.insertWidget(4, self.medical_history_frame)

        # Remove the old Designer grids from Page 2 (labels-only 3x2 blocks)
        for container in ("name_widget", "info_widget"):
            if hasattr(self.ui.load_pages, container):
                w = getattr(self.ui.load_pages, container)
                # Detach from layout and delete
                self.ui.load_pages.page_2_layout.removeWidget(w)
                w.setParent(None)
                w.deleteLater()


        # LINE EDIT 1 - FIRST NAME
        self.lineEdit_first_name = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="First Name")

        # LINE EDIT 2 - LAST NAME
        self.lineEdit_last_name = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Last Name")

        # LINE EDIT 3 - SUBJECT ID
        self.lineEdit_subject_id = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Subject ID")

        # LINE EDIT 4 - AGE
        self.lineEdit_age = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Age")

        # LINE EDIT 5 - HEIGHT
        self.lineEdit_height = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Height")

        # LINE EDIT 6 - WEIGHT
        self.lineEdit_weight = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Weight")

        # PUSH BUTTON 1 - FINISH
        self.finish_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Next page")

        # FILL DICTIONARY
        self.subject_info_dict: dict[str, PyLineEdit] = {
            "first_name": self.lineEdit_first_name,
            "last_name": self.lineEdit_last_name,
            "subject_id": self.lineEdit_subject_id,
            "age": self.lineEdit_age,
            "height": self.lineEdit_height,
            "weight": self.lineEdit_weight,
        }

        # BUTTON CLICKED
        def finish_btn_clicked():
            self.ui.left_menu.select_only_one("btn_stimulation_2")
            MainFunctions.set_page(self, self.ui.load_pages.page_10)
        
        def finish_btn_page3_to_setup():
            # Select "Home" in the left menu and show Page 1
            self.ui.left_menu.select_only_one("btn_home")
            MainFunctions.set_page(self, self.ui.load_pages.page_01)

        # CONNECT BUTTONS
        self.finish_btn.clicked.connect(task_clicked)
        self.finish_btn.setAutoDefault(True)  # Return key triggers the button

        # CONNECT LINE EDITS
        self.lineEdit_first_name.returnPressed.connect(self.lineEdit_last_name.setFocus)
        self.lineEdit_last_name.returnPressed.connect(self.lineEdit_subject_id.setFocus)
        self.lineEdit_subject_id.returnPressed.connect(self.lineEdit_height.setFocus)
        self.lineEdit_height.returnPressed.connect(self.lineEdit_weight.setFocus)
        self.lineEdit_weight.returnPressed.connect(self.lineEdit_age.setFocus)
        self.lineEdit_age.returnPressed.connect(self.finish_btn.setFocus)
        # Connect selection SUBJECT ID change
        self.subject_id_dropbox.currentTextChanged.connect(on_subject_selected)

        # ADD WIDGETS
        self.ui.load_pages.finish_btn_layout.addWidget(self.finish_btn)

         # --- Move "Save To" row above the Next button on Page 2 ---
        # Build a single row for: Save To | [path] | Browse
        self.save_to_widget = QWidget(self.ui.load_pages.page_02)
        self.save_to_layout = QHBoxLayout(self.save_to_widget)
        self.save_to_layout.setContentsMargins(0, 2, 0, 2)
        self.save_to_layout.setSpacing(6)
        self.save_to_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Keep all three controls packed to the left (no stretching)
        self.save_path_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.lineEdit_safe_path.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.lineEdit_safe_path.setMinimumWidth(LINE_WIDTH_MID)   # consistent width, adjust if needed
        self.lineEdit_safe_path.setMaximumWidth(LINE_WIDTH_MID)
        self.save_path_browse_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.save_to_layout.addWidget(self.save_path_label)
        self.save_to_layout.addWidget(self.lineEdit_safe_path)
        self.save_to_layout.addWidget(self.save_path_browse_btn)

        # Reorder Page 2: insert Save-To row above the existing finish button row
        page2_layout = self.ui.load_pages.page_2_layout
        finish_row_widget = self.ui.load_pages.finish_btn_widget
        page2_layout.removeWidget(finish_row_widget)
        page2_layout.addWidget(self.save_to_widget)
        page2_layout.addWidget(finish_row_widget)

         # Equalize vertical spacing: same gap above/below the Save-To row
        # Use a single spacing value for all siblings on Page 2
        page2_layout.setSpacing(6)  # adjust this value to taste (uniform between all rows)
        # Tight margins on the Save-To row itself
        if hasattr(self, "save_to_layout"):
            self.save_to_layout.setContentsMargins(0, 0, 0, 0)
            self.save_to_layout.setSpacing(6)
        # Remove any hidden spacer row that might add extra bottom gap
        if hasattr(self.ui.load_pages, "spaceholder_5"):
            try:
                w = self.ui.load_pages.spaceholder_5
                page2_layout.removeWidget(w)
                w.setParent(None)
                w.deleteLater()
            except Exception:
                pass

        # new
        # Route First/Last/Age into the Demographics frame and keep SubjectID/Height/Weight in their original sections
        # Demographics grid: labels + fields (2 columns)
        self.demographics_form_layout.addWidget(self.lbl_first_name, 0, 0, Qt.AlignmentFlag.AlignCenter)
        self.demographics_form_layout.addWidget(self.lineEdit_first_name, 1, 0)
        self.demographics_form_layout.addWidget(self.lbl_last_name, 0, 1, Qt.AlignmentFlag.AlignCenter)
        self.demographics_form_layout.addWidget(self.lineEdit_last_name, 1, 1)
        self.demographics_form_layout.addWidget(self.lbl_age, 3, 0, Qt.AlignmentFlag.AlignCenter)
        self.demographics_form_layout.addWidget(self.lineEdit_age, 4, 0)
        self.demographics_form_layout.addWidget(self.lbl_sex, 3, 1, Qt.AlignmentFlag.AlignCenter)
        self.demographics_form_layout.addWidget(self.dropbox_sex, 4, 1)

        # Biometrics grid: labels + fields (2 columns)
        self.biometric_form_layout.addWidget(self.lbl_height, 0, 1, Qt.AlignmentFlag.AlignCenter)
        self.biometric_form_layout.addWidget(self.lineEdit_height, 1, 1)
        self.biometric_form_layout.addWidget(self.lbl_weight, 0, 0, Qt.AlignmentFlag.AlignCenter)
        self.biometric_form_layout.addWidget(self.lineEdit_weight, 1, 0)

        # Medical history grid: labels + fields (2 columns)
        self.medical_history_form_layout.addWidget(self.lbl_injury_type, 0, 0, Qt.AlignmentFlag.AlignCenter)
        self.medical_history_form_layout.addWidget(self.dropbox_injury, 1, 0)
        self.medical_history_form_layout.addWidget(self.lbl_affected_limb, 0, 1, Qt.AlignmentFlag.AlignCenter)
        self.medical_history_form_layout.addWidget(self.dropbox_affected_limb, 1, 1)

        # PAGE 3 - TASK INFORMATION
        # ///////////////////////////////////////////////////////////////
        # MENU ACTIONS
        def load_task(activated_button: QToolButton, selected_action: QAction):
            # Don't change anything if "New Task" is selected
            if selected_action.text() == "New Task":
                return
            # Defer until UI is ready (these are created later in setup_gui)
            if not hasattr(self, "lineEdit_selected_task") or not hasattr(self, "gait_toggle"):
                QTimer.singleShot(0, lambda: load_task(activated_button, selected_action))
                return
            # load task.json and get task using the action name
            with open(self.tasks_path, "r") as f:
                data: dict = json.load(f)
                task: dict[str, int] = data["tasks"].get(selected_action.text(), None)
                # Populate the line edits with the data from the JSON file
                
                # For single stimulation type:
                self.lineEdit_burst_frequency.setText(task.get("burst_frequency", ""))
                self.lineEdit_burst_duration.setText(task.get("burst_duration", ""))
                self.lineEdit_pulse_deadtime.setText(task.get("pulse_deadtime", ""))
                self.lineEdit_interpulse_interval.setText(task.get("interpulse_interval", ""))
                self.lineEdit_carrier_frequency.setText(task.get("carrier_frequency", ""))
                
                # For Hybrid stimulation type (tSCS + FES):
                self.lineEdit_burst_frequency_tscs.setText(task.get("burst_frequency_tscs", ""))
                self.lineEdit_burst_duration_tscs.setText(task.get("burst_duration_tscs", ""))
                self.lineEdit_pulse_deadtime_tscs.setText(task.get("pulse_deadtime_tscs", ""))
                self.lineEdit_interpulse_interval_tscs.setText(task.get("interpulse_interval_tscs", ""))
                self.lineEdit_carrier_frequency_tscs.setText(task.get("carrier_frequency_tscs", ""))
                
                self.lineEdit_burst_frequency_fes.setText(task.get("burst_frequency_fes", ""))
                self.lineEdit_burst_duration_fes.setText(task.get("burst_duration_fes", ""))
                self.lineEdit_pulse_deadtime_fes.setText(task.get("pulse_deadtime_fes", ""))
                self.lineEdit_interpulse_interval_fes.setText(task.get("interpulse_interval_fes", ""))
                self.lineEdit_carrier_frequency_fes.setText(task.get("carrier_frequency_fes", ""))
                
                
                # Reflect task name on Page 10
                if hasattr(self, "lineEdit_selected_task_10"):
                    self.lineEdit_selected_task_10.setText(selected_action.text())
                self.gait_toggle.setChecked(task.get("gait_detection_toggle", False))
                self.tscs_toggle.setChecked(task.get("tscs_toggle", False))
                self.fes_toggle.setChecked(task.get("fes_toggle", False))
                self.walking_speed_toggle.setChecked(task.get("walking_speed_toggle", False))
                self.imu_toggle.setChecked(task.get("imu_toggle", False))
                self.imu2_radio_btn.setChecked(task.get("use_4_imus", False) is False)
                self.imu4_radio_btn.setChecked(task.get("use_4_imus", False))
                self.closed_loop_toggle.setChecked(task.get("do_closed_loop", False))
                self.fsr_toggle.setChecked(task.get("fsr_toggle", False))
                self.phase_toggle.setChecked(task.get("phase_detection_toggle", False))
                self.phase_radio_btn.setChecked(task.get("use_subphases", False) is False)
                self.subphase_radio_btn.setChecked(task.get("use_subphases", False))

                for action in self.dropdown_btn_placement.menu().actions():
                    # Load the correct image
                    if action.text() == task.get("electrode_placement", ""):
                        self.dropdown_btn_placement.on_action_triggered(action)
                        break
                self.lineEdit_selected_task.setText(selected_action.text())
                #calculate_stimulation_parameters() not sure if useful, ask DAN

        def load_task_image(activated_button: QToolButton, selected_action: QAction):
            # Load the correct back image (defer if channel/image widgets not ready yet)
            if not hasattr(self, "btn_chan_connection") or not hasattr(self, "back_image"):
                QTimer.singleShot(0, lambda: load_task_image(activated_button, selected_action))
                return
            # If the front image was removed, guard it
            if hasattr(self, "task_image"):
                SetupMainWindow.load_back_image(selected_action.text(), self.tasks_path, self.btn_chan_connection, self.task_image)
            SetupMainWindow.load_back_image(selected_action.text(), self.tasks_path, self.btn_chan_connection, self.back_image)
            # Also mirror to Page 10 image, if created
            if hasattr(self, "back_image_10") and self.back_image_10 is not None:
                SetupMainWindow.load_back_image(selected_action.text(), self.tasks_path, self.btn_chan_connection, self.back_image_10)
                # Rebuild Page 10 side rows based on electrode count
                try:
                    _rebuild_page10_rows()
                    QTimer.singleShot(0, _page10_render_all_labels_for_arrangement)
                except Exception:
                    pass
            update_target_list()
        
        # Render ALL labels (L1.., M1, R1..) on Page 10 image for current arrangement
        def _page10_render_all_labels_for_arrangement():
            if not hasattr(self, "back_image_10"):
                return

            # Determine current arrangement from placement dropdown
            arrangement = self.dropdown_btn_placement.text() if hasattr(self, "dropdown_btn_placement") else "No Electrodes"

            # Reset modified_image.svg to the base image for this arrangement
            SetupMainWindow.load_back_image(arrangement, self.tasks_path, self.btn_chan_connection, self.back_image_10)

            # Determine number of electrodes from JSON mapping
            try:
                buttons = SetupMainWindow.get_placement_buttons(self.tasks_path, arrangement)
                n = len(buttons)
            except Exception:
                n = 0

            # Define label order to match buttons order
            if n == 1:
                labels = ["M1"]
            elif n == 6:
                labels = ["L1", "L2", "L3", "R1", "R2", "R3"]
            elif n == 7:
                labels = ["L1", "L2", "L3", "M1", "R1", "R2", "R3"]
            elif n == 8:
                # Default left-to-right ordering matching button indices 0..7
                # Use FES-specific muscle names when either:
                #  - the placement string explicitly contains "fes", or
                #  - the FES toggle is checked (preferred).
                is_fes_arrangement = False
                try:
                    if getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked():
                        is_fes_arrangement = True
                    else:
                        is_fes_arrangement = "fes" in (arrangement or "").lower()
                except Exception:
                    is_fes_arrangement = "fes" in (arrangement or "").lower()

                
                if is_fes_arrangement:
                    # EDIT THIS ARRAY TO MATCH YOUR FES MUSCLE NAMES / DESIRED ORDER
                    labels = ["BF_L", "VM_L", "GA_L", "TA_L", "BF_R", "VM_R", "GA_R", "TA_R"]
                else:
                    labels = ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]
            else:
                labels = []

            # Apply labels and set them white
            path = Functions.set_svg_image("modified_image.svg")
            try:
                from modify_svg import change_label_to
            except Exception:
                return

            # Write labels on each electrode index
            for idx, text in enumerate(labels):
                try:
                    path = change_label_to(path, idx, text, fill="#FFFFFF")
                except Exception:
                    pass

            # Reload updated image
            try:
                self.back_image_10.load(path)
                self.back_image_10.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            except Exception:
                pass
        
        # Tighten vertical spacing in the Gait Detection settings
        def _tighten_gait_spacing():
            # Main gait settings panel
            # Use consistent row spacing everywhere so all rows look even
            self.ui.load_pages.gait_detection_layout.setSpacing(6)
            self.ui.load_pages.gait_detection_layout.setContentsMargins(9, 6, 9, 6)

            if hasattr(self.ui.load_pages, "imu_layout"):
                self.ui.load_pages.imu_layout.setSpacing(6)
                self.ui.load_pages.imu_layout.setContentsMargins(9, 6, 9, 6)
            if hasattr(self.ui.load_pages, "nb_imu_layout"):
                # horizontal row; small but non-zero spacing
                self.ui.load_pages.nb_imu_layout.setSpacing(6)
                self.ui.load_pages.nb_imu_layout.setContentsMargins(0, 0, 0, 0)
            if hasattr(self.ui.load_pages, "phase_detection_layout"):
                self.ui.load_pages.phase_detection_layout.setSpacing(6)
                self.ui.load_pages.phase_detection_layout.setContentsMargins(9, 6, 9, 6)

            if hasattr(self.ui.load_pages, "task_option_layout"):
                self.ui.load_pages.task_option_layout.setSpacing(6)
                self.ui.load_pages.task_option_layout.setContentsMargins(9, 6, 9, 6)

        def line_edit_focused(line: QLineEdit):
            # Create temporary dictionnary for readability
            name_to_place_in_svg = {
                "Burst Frequency [Hz]": 5,
                "Burst Duration [us]": 4,
                "Pulse Deadtime (T2) [us]": 1,
                "Interpulse Interval (T3) [us]": 3,
                "Carrier Frequency [Hz]": 6,
            }
            # Change the color of the corresponding part in the image depending on the line edit focused
            yellow = "#FFFF00"
            svg_path = Functions.set_svg_image("stimulation_parameters.svg")
            modified = change_color_to(svg_path, name_to_place_in_svg[self.line_edit_title_dict[line].text()], yellow, is_back=False)
            # Load the modified image
            self.stim_para_image.load(modified)
            self.stim_para_image.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

        def calculate_stimulation_parameters():
            parameters = StimulatorParameters(
                burst_frequency=self.lineEdit_burst_frequency.as_value(),
                burst_duration=self.lineEdit_burst_duration.as_value(),
                pulse_deadtime=self.lineEdit_pulse_deadtime.as_value(),
                interpulse_interval=self.lineEdit_interpulse_interval.as_value(),
                carrier_frequency=self.lineEdit_carrier_frequency.as_value(),
            )
            # Convert the period to ms:
            burst_period = parameters.burst_period * 1e-3
            if burst_period > 1e3:
                self.ui.load_pages.burst_period_value_label.setText("{:.2e}".format(burst_period))
            else:
                self.ui.load_pages.burst_period_value_label.setText(str(burst_period))
            self.ui.load_pages.pulse_width_value_label.setText(str(parameters.ideal_pulse_width))
            self.ui.load_pages.nb_pulses_value_label.setText(str(parameters.pulses_per_burst))
            self.ui.load_pages.pulse_period_value_label.setText(str(parameters.carrier_period))

        # Create actions from tasks
        self.tasks_path = os.path.join(os.path.join(self.root_path, "GUI"), "tasks_default.json")
        with open(self.tasks_path, "r") as f:
            data: dict = json.load(f)
            self.task_actions = [QAction(name) for name in data["tasks"].keys()]

        self.placement_actions = [
            QAction("No Electrodes"),
            QAction("Singlesite"),
            QAction("Three Electrodes"),
            QAction("Four Electrodes"),
            QAction("Multisite - Six Electrodes"),
            QAction("Multisite - Eight Electrodes"),
            QAction("Combination - Seven Electrodes"),
            QAction("FES - 8 Electrodes"),
            QAction("FES - No Stimulation"),
         #   QAction("FES - No Stimulation"), Add electrode placement for hybrid
            
        ]

        # Create a "Study Phase" frame to the LEFT of gait settings
        self.study_phase_frame = QFrame(self.ui.load_pages.task_frame_widget)
        self.study_phase_frame.setObjectName("study_phase_frame")
        self.study_phase_frame.setStyleSheet(self.frame_stylesheet)
        self.study_phase_layout = QVBoxLayout(self.study_phase_frame)
        self.study_phase_layout.setContentsMargins(9, 6, 6, 6)
        self.study_phase_layout.setSpacing(8)

        self.study_phase_title = QLabel("Study Phase", self.study_phase_frame)
        self.study_phase_title.setStyleSheet("font-size: 14pt;")
        self.study_phase_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.study_phase_layout.addWidget(self.study_phase_title)

        # Three radio options
        self.phase1_radio = SetupMainWindow.create_std_radio_btn(self.themes, text="Phase 1")
        self.phase2g1_radio = SetupMainWindow.create_std_radio_btn(self.themes, text="Phase 2 - Group 1 midline")
        self.phase2g2_radio = SetupMainWindow.create_std_radio_btn(self.themes, text="Phase 2 - Group 2 bilateral")
        self.FES_radio = SetupMainWindow.create_std_radio_btn(self.themes, text="FES")
        self.ss_tscs_fes_radio = SetupMainWindow.create_std_radio_btn(self.themes, text="Single site tSCS + FES")
        self.phase1_radio.setChecked(True)  # default

        self.study_phase_layout.addWidget(self.phase1_radio)
        self.study_phase_layout.addWidget(self.phase2g1_radio)
        self.study_phase_layout.addWidget(self.phase2g2_radio)
        self.study_phase_layout.addWidget(self.FES_radio)
        self.study_phase_layout.addWidget(self.ss_tscs_fes_radio)
        self.study_phase_layout.addStretch(1)

        # Exclusive selection
        self.study_phase_group = QButtonGroup(self.study_phase_frame)
        self.study_phase_group.addButton(self.phase1_radio)
        self.study_phase_group.addButton(self.phase2g1_radio)
        self.study_phase_group.addButton(self.phase2g2_radio)
        self.study_phase_group.addButton(self.FES_radio)
        self.study_phase_group.addButton(self.ss_tscs_fes_radio)
        self.study_phase_group.setExclusive(True)

        # Map study phases to task labels in the Task dropdown
        self._study_phase_to_task_label = {
            "phase_1": "No Stimulation - tSCS",   # Phase 1 -> task "No Stimulation"
            "phase_2_group_1": "Task 4 - Open Loop Singlesite",   # Phase 2 Group 1 -> "Task 4"
            "phase_2_group_2": "Task 6 - OL Single + Multisite",   # Phase 2 Group 2 -> "Task 6"
            "FES": "CL FES",  
            "SS_tSCS_FES" : "SS tSCS + FES",
        }

        def _select_task_by_label(label: str) -> bool:
            """Find action by text in the Task dropdown and trigger it to load the task."""
            if not label or not hasattr(self.ui.load_pages, "task_frame_widget"):
                return False
            # Safely walk the actions in the Task dropdown
            menu = getattr(self.dropdown_btn_task, "menu", lambda: None)()
            actions = menu.actions() if menu else []
            for act in actions:
                if act.text().strip().lower() == label.strip().lower():
                    # Prefer the dropdown's own trigger method if available (preserves button text, etc.)
                    if hasattr(self.dropdown_btn_task, "on_action_triggered"):
                        self.dropdown_btn_task.on_action_triggered(act)
                    else:
                        # Fallback: call the same loader used by the dropdown
                        try:
                            load_task(self.dropdown_btn_task, act)  # nested in setup_gui
                        except Exception as e:
                            print(f"Fallback task load failed: {e}")
                            return False
                    return True
            print(f"Task '{label}' not found in Task dropdown.")
            return False

        # Keep current selection for later use
        self.current_study_phase = "phase_1"

        def _apply_study_phase_to_task(phase_key: str):
            """Switch the current task based on the study phase selection."""
            label = self._study_phase_to_task_label.get(phase_key, "")
            if not label:
                return
            ok = _select_task_by_label(label)
            if ok:
                # Update the visible caption on the task button if needed
                if hasattr(self.dropdown_btn_task, "setText"):
                    self.dropdown_btn_task.setText(label)

        def _on_study_phase_changed():
            if self.phase1_radio.isChecked():
                self.current_study_phase = "phase_1"
                _apply_study_phase_to_task("phase_1")
            elif self.phase2g1_radio.isChecked():
                self.current_study_phase = "phase_2_group_1"
                _apply_study_phase_to_task("phase_2_group_1")
            elif self.phase2g2_radio.isChecked():
                self.current_study_phase = "phase_2_group_2"
                _apply_study_phase_to_task("phase_2_group_2")
            elif self.FES_radio.isChecked():
                self.current_study_phase = "FES"
                _apply_study_phase_to_task("FES")
            elif self.ss_tscs_fes_radio.isChecked():
                self.current_study_phase = "SS_tSCS_FES"
                _apply_study_phase_to_task("SS_tSCS_FES")

            # Update the Save Path preview with the computed session directory (no creation yet)
            session_dir = _compute_session_dir_for_phase(self.current_study_phase)
            if session_dir:
                self.lineEdit_safe_path.setText(session_dir)
                self.lineEdit_safe_path.setToolTip(session_dir)
                # If the confirm page is open, refresh its preview
                try:
                    SetupMainWindow.update_confirm_page(self.confirm_dict)
                except Exception:
                    pass

        # Connect radios to handler
        self.phase1_radio.toggled.connect(_on_study_phase_changed)
        self.phase2g1_radio.toggled.connect(_on_study_phase_changed)
        self.phase2g2_radio.toggled.connect(_on_study_phase_changed)
        self.FES_radio.toggled.connect(_on_study_phase_changed) 
        self.ss_tscs_fes_radio.toggled.connect(_on_study_phase_changed)
        

        # DROP DOWN BUTTON 1 - TASK SELECTION
        self.dropdown_btn_task = SetupMainWindow.create_std_dropdown_btn(self.themes, self.task_actions, "Select Task")
        self.dropdown_btn_task.setMinimumHeight(LINE_HEIGHT)

        # DROP DOWN BUTTON 2 - PLACEMENT SELECTION
        self.dropdown_btn_placement = SetupMainWindow.create_std_dropdown_btn(self.themes, self.placement_actions, "No Electrodes")
        self.dropdown_btn_placement.setMinimumWidth(DROPDOWN_WIDTH)

        # PUSH BUTTON 1 - FINISH
        self.finish_btn_2 = SetupMainWindow.create_std_push_btn(self.themes, text="Finish")
        self.finish_btn_2.setMinimumWidth(BUTTON_WIDTH)

        # ADD IMAGE 1 - STIMULATION PARAMETERS
        self.stim_para_image = QSvgWidget(Functions.set_svg_image("stimulation_parameters.svg"))
        self.stim_para_image.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

        # ADD IMAGE 2 - ELECTRODE PLACEMENT
        self.task_image = QSvgWidget(Functions.set_svg_image("electrode_arrangement_none.svg"))
        self.task_image.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

        # LINE EDIT 1 - BURST FREQUENCY
        self.lineEdit_burst_frequency = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_burst_frequency_tscs = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_burst_frequency_fes = SetupMainWindow.create_std_line_edit(self.themes)

        # LINE EDIT 2 - BURST DURATION
        self.lineEdit_burst_duration = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_burst_duration_tscs = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_burst_duration_fes = SetupMainWindow.create_std_line_edit(self.themes)

        # LINE EDIT 3 - PULSE DEADTIME
        self.lineEdit_pulse_deadtime = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_pulse_deadtime_tscs = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_pulse_deadtime_fes = SetupMainWindow.create_std_line_edit(self.themes)

        # LINE EDIT 4 - INTERPULSE INTERVAL
        self.lineEdit_interpulse_interval = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_interpulse_interval_tscs = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_interpulse_interval_fes = SetupMainWindow.create_std_line_edit(self.themes)

        # LINE EDIT 5 - CARRIER FREQUENCY
        self.lineEdit_carrier_frequency = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_carrier_frequency_tscs = SetupMainWindow.create_std_line_edit(self.themes)
        self.lineEdit_carrier_frequency_fes = SetupMainWindow.create_std_line_edit(self.themes)

        # ADD VALIDATORS
        self.lineEdit_burst_frequency.setValidator(QDoubleValidator(bottom=0.0003, top=1e6, decimals=3))
        self.lineEdit_burst_duration.setValidator(QIntValidator())
        self.lineEdit_pulse_deadtime.setValidator(QIntValidator())
        self.lineEdit_interpulse_interval.setValidator(QIntValidator())
        self.lineEdit_carrier_frequency.setValidator(QIntValidator())

        # FILL DICTIONARY
        self.line_edit_title_dict: dict[PyLineEdit, QLabel] = {
            self.lineEdit_burst_frequency: self.ui.load_pages.burst_frequency_label,
            self.lineEdit_burst_duration: self.ui.load_pages.burst_duration_label,
            self.lineEdit_pulse_deadtime: self.ui.load_pages.pulse_deadtime_label,
            self.lineEdit_interpulse_interval: self.ui.load_pages.interpulse_interval_label,
            self.lineEdit_carrier_frequency: self.ui.load_pages.carrier_frequency_label,
        }

        # CONNECT BUTTONS
        self.dropdown_btn_task.clicked.connect(self.dropdown_btn_task.showMenu)
        self.dropdown_btn_placement.clicked.connect(self.dropdown_btn_placement.showMenu)
        self.dropdown_btn_task.action_selected.connect(load_task)
        self.dropdown_btn_placement.action_selected.connect(load_task_image)
        self.finish_btn_2.clicked.connect(finish_btn_page3_to_setup)

        # //////////////////////////////////////////////////////////////////////////
        # Temporary stuff here to test for layout, move it to correct part later on
        # //////////////////////////////////////////////////////////////////////////

        self.imu2_radio_btn = SetupMainWindow.create_std_radio_btn(self.themes, text="2 IMUs")
        self.imu2_radio_btn.setChecked(True)
        self.imu4_radio_btn = SetupMainWindow.create_std_radio_btn(self.themes, text="4 IMUs")
        self.phase_radio_btn = SetupMainWindow.create_std_radio_btn(self.themes, text="Phases")
        self.phase_radio_btn.setChecked(True)
        self.subphase_radio_btn = SetupMainWindow.create_std_radio_btn(self.themes, text="Phases and Subphases")

        self.gait_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="Use Gait Detection")
        self.walking_speed_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="Fast Walking (3km/h)")
        self.walking_speed_toggle.setToolTip("Slow is around 1km/h, fast is around 3km/h.")
        self.imu_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="Use IMUs")
        self.fsr_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="Use FSR")
        self.phase_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="Use Phase Detection")
        self.closed_loop_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="Closed Loop")
        #self.closed_loop_toggle.setEnabled(False)
        
        # NEW: Stimulation type header + tSCS / FES toggles row (placed below gait_toggle and above the method dropdown)
        self.stim_type_label = QLabel("Stimulation type:", self.ui.load_pages.gait_detection_frame)
        self.stim_type_label.setStyleSheet("font-size: 12pt; font-weight: 600;")
        self.stim_type_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.stim_type_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.tscs_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="tSCS")
        self.fes_toggle  = SetupMainWindow.create_std_small_toggle(self.themes, text="FES")
        # keep same vertical sizing as other small toggles, allow horizontal expansion and ensure enough width
        for w in (self.tscs_toggle, self.fes_toggle):
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            w.setMinimumHeight(LINE_HEIGHT)
            w.setMinimumWidth(140)        # ensure label isn't cut off
            # defensive: re-apply text so custom widget updates layout
            if hasattr(w, "setText"):
                w.setText(w.text())
            w.updateGeometry()
            w.adjustSize()

        # Row widget to host the two toggles side-by-side
        self._tscs_fes_row = QWidget(self.ui.load_pages.gait_detection_frame)
        self._tscs_fes_layout = QHBoxLayout(self._tscs_fes_row)
        # Give the row breathing room and larger spacing between toggles
        self._tscs_fes_layout.setContentsMargins(12, 6, 12, 6)
        self._tscs_fes_layout.setSpacing(40)   # <- increased spacing
        self._tscs_fes_layout.addWidget(self.tscs_toggle)
        # extra fixed gap to guarantee separation on narrow windows
        self._tscs_fes_layout.addSpacing(24)
        self._tscs_fes_layout.addWidget(self.fes_toggle)
        self._tscs_fes_layout.addStretch(1)
        self._tscs_fes_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        
        # ---------- stimulation mode maps and safe switch handlers ----------
        
        self._tscs_target_map: dict[str, str] = {
            "Not to be used": None,
            "Left Leg": "full_leg_left",
            "Right Leg": "full_leg_right",
            "Left Proximal": "proximal_left",
            "Right Proximal": "proximal_right",
            "Left Distal": "distal_left",
            "Right Distal": "distal_right",
            "Continuous": "continuous",
        }
       
        self._fes_target_map: dict[str, str] = {
            "Not to be used": None,
            "Left Tibialis Anterior (TA)": "TA_left",
            "Right Tibialis Anterior (TA)": "TA_right",
            "Left Gastrocnemius (GA)": "GA_left",
            "Right Gastrocnemius (GA)": "GA_right",
            "Left Vastus Medialis (VM)": "VM_left",
            "Right Vastus Medialis (VM)": "VM_right",
            "Left Rectus Femoris (RF)" : "RF_left",
            "Right Rectus Femoris (RF)" : "RF_right",
            "Left Hamstrings (HAM)": "BF_left",
            "Right Hamstrings (HAM)": "BF_right",
            "Left Gluteus Maximus (GM)": "GM_left",  
            "Right Gluteus Maximus (GM)": "GM_right",
            
        }
        
        self._hybrid_target_map: dict[str, str] = {
            "Not to be used": None,
            "Left Leg": "full_leg_left",
            "Right Leg": "full_leg_right",
            "Left Proximal": "proximal_left",
            "Right Proximal": "proximal_right",
            "Left Distal": "distal_left",
            "Right Distal": "distal_right",
            "Continuous": "continuous",
            "Left Tibialis Anterior (TA)": "TA_left",
            "Right Tibialis Anterior (TA)": "TA_right",
            "Left Gastrocnemius (GA)": "GA_left",
            "Right Gastrocnemius (GA)": "GA_right",
            "Left Vastus Medialis (VM)": "VM_left",
            "Right Vastus Medialis (VM)": "VM_right",
            "Left Rectus Femoris (RF)" : "RF_left",
            "Right Rectus Femoris (RF)" : "RF_right",
            "Left Hamstrings (HAM)": "BF_left",
            "Right Hamstrings (HAM)": "BF_right",
            "Left Gluteus Maximus (GM)": "GM_left",  
            "Right Gluteus Maximus (GM)": "GM_right",
            
        }

        # single source-of-truth for mode
        # single source-of-truth for mode
        self._stimulation_mode = "tscs"

        def _update_target_options_for_mode():
            # update active map and label list used elsewhere
            if self._stimulation_mode == "hybrid":
                active = self._hybrid_target_map
            elif self._stimulation_mode == "fes":
                active = self._fes_target_map
            else:
                active = self._tscs_target_map
            self.page10_target_key_map = dict(active)  # copy
            self.page10_target_labels = list(self.page10_target_key_map.keys())
            # refresh Page10 UI safely after widgets exist
            QTimer.singleShot(0, lambda: (
                (_rebuild_page10_rows() if "_rebuild_page10_rows" in globals() else None),
                (_page10_refresh_target_options() if "_page10_refresh_target_options" in globals() else None),
                (_page10_render_labels() if "_page10_render_labels" in globals() else None)
            ))

        def _set_mode(mode: str):
            """Set stimulation mode: 'tscs' | 'fes' | 'hybrid'. Keep toggles in sync without re-emitting."""
            if mode == self._stimulation_mode:
                return
            self._stimulation_mode = mode
            # update toggles without re-emitting their signals
            try:
                if hasattr(self.fes_toggle, "blockSignals"):
                    self.fes_toggle.blockSignals(True)
                    self.tscs_toggle.blockSignals(True)
                    self.fes_toggle.setChecked(mode in ("fes", "hybrid"))
                    self.tscs_toggle.setChecked(mode in ("tscs", "hybrid"))
                    self.fes_toggle.blockSignals(False)
                    self.tscs_toggle.blockSignals(False)
                else:
                    self.fes_toggle.setChecked(mode in ("fes", "hybrid"))
                    self.tscs_toggle.setChecked(mode in ("tscs", "hybrid"))
            except Exception:
                pass
            _update_target_options_for_mode()

        def _determine_mode_from_toggles() -> str:
            """Decide mode from toggle states. If both checked => hybrid."""
            try:
                fes_on = bool(getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked())
                tscs_on = bool(getattr(self, "tscs_toggle", None) and self.tscs_toggle.isChecked())
                if fes_on and tscs_on:
                    return "hybrid"
                if fes_on and not tscs_on:
                    return "fes"
                if tscs_on and not fes_on:
                    return "tscs"
            except Exception:
                pass
            return "tscs"

        # connect toggles to central setter (defensive: only if widgets exist)
        try:
            # Use a single handler that reads both toggles to decide mode (prevents inconsistent states)
            def _on_mode_toggles_changed(_=None):
                _set_mode(_determine_mode_from_toggles())

            # wire both toggles (use toggled so user interaction triggers recalculation)
            self.fes_toggle.toggled.connect(_on_mode_toggles_changed)
            self.tscs_toggle.toggled.connect(_on_mode_toggles_changed)
        except Exception:
            pass

        # initialize labels/map once (after startup)
        QTimer.singleShot(0, lambda: _set_mode(self._stimulation_mode))

        # ---------- end stimulation mode helpers ----------


        # DROP DOWN BUTTON 3 - Gait detection METHOD SELECTION
        #Actions for IMU methods
        self.method_actions = [
            QAction("Main (norm)"),# previous "Method 2- IMU"
            QAction("Optional (gyro)"),#previous "Method 1 - IMU"
            QAction("Both"),
        ]

        def _show_hover_method_btn(selected_action: QAction):
            method = selected_action.text()
            if method == "Optional (gyro)":
                self.dropdown_btn_method.setToolTip("Original method using find peaks function.")

            elif method == "Main (norm)":
                self.dropdown_btn_method.setToolTip("Method based on gyro norm and thresholds.")
            else:
                self.dropdown_btn_method.setToolTip("Use both methods for combined detection.")


        # Add tooltips for each method
        self.method_actions[0].setToolTip("Original method using find peaks function.")
        self.method_actions[1].setToolTip("Method based on gyro norm and thresholds.")
        self.method_actions[2].setToolTip("Use both methods for combined detection.")

        self.dropdown_btn_method = SetupMainWindow.create_std_dropdown_btn(self.themes, self.method_actions, "Select Method")
        self.dropdown_btn_method.setToolTip("Original method using find peaks function.")
        self.dropdown_btn_method.setMinimumWidth(DROPDOWN_WIDTH)
        # Ensure the menu opens on click
        self.dropdown_btn_method.clicked.connect(self.dropdown_btn_method.showMenu)
        self.dropdown_btn_method.action_selected.connect(_show_hover_method_btn)
        self.dropdown_btn_method.setText("Main (norm)")

        # LINE EDIT 6 - WALKING SPEED
        # create the walking speed line edit (was missing)
        self.lineEdit_walking_speed = SetupMainWindow.create_std_line_edit(self.themes)

        self.lineEdit_walking_speed.setPlaceholderText("Walking speed (km/h)")
        self.lineEdit_walking_speed.setToolTip("Walking speed in kilometers per hour. Example: 0.8")
        # Accept 0.00–5.00 km/h with 1 decimals; adjust bounds as you want
        regex = QRegularExpression(r"^\s*(?:[0-5](?:[.,]\d)?)\s*$")
        self.lineEdit_walking_speed.setValidator(QRegularExpressionValidator(regex))
        self.lineEdit_walking_speed.setMaximumWidth(DROPDOWN_WIDTH)
        self.lineEdit_walking_speed.setText("0.4")
        
        # --- Helpers to parse and normalize walking speed ---
        def _parse_decimal(txt: str) -> float | None:
            s = (txt or "").strip().replace(" ", "")
            if not s:
                return None
            # If both separators present, assume the rightmost is the decimal separator
            if "," in s and "." in s:
                if s.rfind(",") > s.rfind("."):
                    s = s.replace(".", "")
                    s = s.replace(",", ".")
                else:
                    s = s.replace(",", "")
            else:
                s = s.replace(",", ".")
            try:
                return float(s)
            except ValueError:
                return None

        def _normalize_walking_speed():
            val = _parse_decimal(self.lineEdit_walking_speed.text())
            if val is None:
                return
            # Clamp and write back as fixed one-decimal (avoids scientific notation)
            val = min(5.0, max(0.0, val))
            self.lineEdit_walking_speed.setText(f"{val:.1f}")

        self.lineEdit_walking_speed.editingFinished.connect(_normalize_walking_speed)

        def get_walking_speed() -> float:
            _normalize_walking_speed()
            val = _parse_decimal(self.lineEdit_walking_speed.text())
            return float(val) if val is not None else 0.0

        # Expose helper for other components (e.g., stimulation setup)
        self.get_walking_speed = get_walking_speed
        # Enable/disable with IMU toggle
        def activate_frame(frame: QFrame, state: Qt.CheckState):
            if state == Qt.CheckState.Checked:
                frame.setEnabled(True)
                # enable/disable the method dropdown and walking speed input
                self.dropdown_btn_method.setEnabled(True)
                self.lineEdit_walking_speed.setEnabled(True)
            elif state == Qt.CheckState.Unchecked:
                frame.setEnabled(False)
                # enable/disable the method dropdown and walking speed input
                self.dropdown_btn_method.setEnabled(False)
                self.lineEdit_walking_speed.setEnabled(False)

        # start disabled until IMU toggle is checked
        self.dropdown_btn_method.setEnabled(False)
        self.lineEdit_walking_speed.setEnabled(False)

        self.gait_toggle.checkStateChanged.connect(lambda state: activate_frame(self.ui.load_pages.gait_detection_frame, state))
        self.imu_toggle.checkStateChanged.connect(lambda state: activate_frame(self.ui.load_pages.imu_frame, state))
        self.phase_toggle.checkStateChanged.connect(lambda state: activate_frame(self.ui.load_pages.phase_detection_frame, state))

        #self.imu4_radio_btn.toggled.connect(lambda state: self.closed_loop_toggle.setEnabled(state))

        # Row 0: Method label + dropdown
        method_row = QWidget(self.ui.load_pages.gait_detection_frame)
        method_layout = QHBoxLayout(method_row)
        method_layout.setContentsMargins(0, 0, 0, 0)
        method_layout.setSpacing(6)
        method_label = QLabel("Gait Detection IMU Method:")
        method_label.setMinimumWidth(160)
        method_layout.addWidget(method_label)
        method_layout.addWidget(self.dropdown_btn_method, 1)
        # keep row compact vertically
        method_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Insert method and speed rows after the stimulation type row,
        # then place the header at the very top so it appears above everything.
        self.ui.load_pages.gait_detection_layout.insertWidget(1, method_row)


        # Row 1: Walking speed label + line edit
        speed_row = QWidget(self.ui.load_pages.gait_detection_frame)
        speed_layout = QHBoxLayout(speed_row)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.setSpacing(6)
        speed_label = QLabel("Walking Speed (km/h):")
        speed_label.setMinimumWidth(160)
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.lineEdit_walking_speed, 1)
        # keep row compact vertically
        speed_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.ui.load_pages.gait_detection_layout.insertWidget(2, speed_row)

        # Insert stimulation header and toggles at the top of the gait settings area
        # Header first, then the two-toggle row directly under it.
        self.ui.load_pages.gait_detection_layout.insertWidget(0, self.stim_type_label)
        self.ui.load_pages.gait_detection_layout.insertWidget(1, self._tscs_fes_row)


        self.ui.load_pages.task_option_layout.insertWidget(0, self.gait_toggle)
        # Insert toggles relative to frames so order is:
        # [Method row] [Speed row] [IMU toggle] [IMU frame] [FSR toggle] [Phase toggle] [Phase frame]
        l = self.ui.load_pages.gait_detection_layout
        # IMU toggle just before IMU frame
        imu_frame_idx = l.indexOf(self.ui.load_pages.imu_frame)
        if imu_frame_idx != -1:
            l.insertWidget(imu_frame_idx, self.imu_toggle)
        else:
            # fallback
            l.addWidget(self.imu_toggle)
        # FSR and Phase toggles just before Phase Detection frame
        # FSR toggle + FSR method label + dropdown
        phase_frame_idx = l.indexOf(self.ui.load_pages.phase_detection_frame)
        if phase_frame_idx == -1:
            phase_frame_idx = l.count()
        l.insertWidget(phase_frame_idx, self.fsr_toggle)

        # Build a small row widget for the FSR method label + dropdown and place it to the right
        fsr_method_row = QWidget(self.ui.load_pages.gait_detection_frame)
        fsr_method_layout = QHBoxLayout(fsr_method_row)
        fsr_method_layout.setContentsMargins(0, 0, 0, 0)
        fsr_method_layout.setSpacing(6)
        method_fsr_label = QLabel("Gait Detection FSR Method:")
        method_fsr_label.setMinimumWidth(160)
        fsr_method_layout.addWidget(method_fsr_label)
        # create/attach dropdown if not already created
        self.fsr_method_actions = getattr(self, "fsr_method_actions", [
            QAction("Main (ST, SW)"), #previous "Method 2 - FSR"
            QAction("Optional (ST, MST, SW)"), #previous "Method 1 - FSR"
        ])

        def _show_hover_fsr_method_btn(selected_action: QAction):
            method = selected_action.text()
            if method == "Optional (ST, MST, SW)":
                self.dropdown_btn_fsr_method.setToolTip("Detects mid-stance does not estimate pre-swing")
            else:
                self.dropdown_btn_fsr_method.setToolTip("Estimates mid-stance, and pre-swing phases.")

        # Add tooltips for each method
        self.fsr_method_actions[1].setToolTip("Detects mid-stance does not estimate pre-swing.")
        self.fsr_method_actions[0].setToolTip("Estimates mid-stance, and pre-swing phases.")

        self.dropdown_btn_fsr_method = getattr(self, "dropdown_btn_fsr_method", 
                                               SetupMainWindow.create_std_dropdown_btn(self.themes, self.fsr_method_actions, "Main (ST, SW)"))
        self.dropdown_btn_fsr_method.setMinimumWidth(DROPDOWN_WIDTH)
        self.dropdown_btn_fsr_method.clicked.connect(self.dropdown_btn_fsr_method.showMenu)
        self.dropdown_btn_fsr_method.action_selected.connect(_show_hover_fsr_method_btn)
        fsr_method_layout.addWidget(self.dropdown_btn_fsr_method, 1)
        fsr_method_row.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        l.insertWidget(phase_frame_idx + 1, fsr_method_row)
        # finally insert the phase toggle
        l.insertWidget(phase_frame_idx + 2, self.phase_toggle)


        # Enable/disable dropdown depending on the FSR toggle state
        try:
            self.dropdown_btn_fsr_method.setEnabled(self.fsr_toggle.isChecked())
            self.fsr_toggle.checkStateChanged.connect(lambda state: self.dropdown_btn_fsr_method.setEnabled(state == Qt.CheckState.Checked))
        except Exception:
            # guard if widget missing during early init
            pass

        # Handler: set thresholds when Method 2 selected, else restore default (20)
        def _on_fsr_method_selected(activated_button: PyDropDownButton | None, selected_action: QAction):
            txt = selected_action.text() if selected_action is not None else ""
            # Guard existence of threshold spin boxes
            if hasattr(self, "fsr_threshold_left_spin_box") and hasattr(self, "fsr_threshold_right_spin_box"):
                try:

                    if "Main (ST, SW)" in txt:
                        self.fsr_threshold_left_spin_box.setValue(5)
                        self.fsr_threshold_right_spin_box.setValue(5)
                        
                        # remove restriction if switching back
                        self._restrict_gait_model = False
                        if hasattr(self, "dropdown_btn_gait_model") and hasattr(self, "gait_model_actions"):
                            for act in self.gait_model_actions:
                                act.setEnabled(True)
                            self.dropdown_btn_gait_model.setEnabled(True)
                            self.dropdown_btn_gait_model.setToolTip("Select gait model. 'Without Distal' includes pre-swing for Distal targets.")
                    else:
                        # restore default used elsewhere (20)
                        self.fsr_threshold_left_spin_box.setValue(20)
                        self.fsr_threshold_right_spin_box.setValue(20)

                        #disable possibility to choose gait model with distal 
                        # store flag in case Page 10 not yet created
                        self._restrict_gait_model = True
                        # if Page 10 widgets already exist, apply immediately
                        if hasattr(self, "dropdown_btn_gait_model") and hasattr(self, "gait_model_actions"):
                            for act in self.gait_model_actions:
                                if act.text() == "Gait Model with Distal":
                                    act.setEnabled(False)
                            self.dropdown_btn_gait_model.setText("Gait Model without Distal")
                            self.dropdown_btn_gait_model.setEnabled(False)
                            self.dropdown_btn_gait_model.setToolTip("Locked to 'Gait Model without Distal'.")
                except Exception:
                    pass

        self.dropdown_btn_fsr_method.action_selected.connect(_on_fsr_method_selected)

         # ensure toggles don't expand vertically
        for w in (self.gait_toggle, self.imu_toggle, self.fsr_toggle, self.phase_toggle):
            w.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # normalize spacing across the whole panel
        _tighten_gait_spacing()

        self.ui.load_pages.nb_imu_layout.addWidget(self.imu2_radio_btn)
        self.ui.load_pages.nb_imu_layout.addWidget(self.imu4_radio_btn)
        # Keep imu4_radio_btn present for logic but hide it from the UI
        try:
            self.imu2_radio_btn.setVisible(False)
            self.imu2_radio_btn.setEnabled(False)
            self.imu4_radio_btn.setVisible(False)
            self.imu4_radio_btn.setEnabled(True)
        except Exception:
            pass
        self.ui.load_pages.imu_layout.addWidget(self.closed_loop_toggle)
        self.ui.load_pages.phase_detection_layout.addWidget(self.phase_radio_btn)
        self.ui.load_pages.phase_detection_layout.addWidget(self.subphase_radio_btn)

        self.ui.load_pages.task_option_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.gait_detection_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.imu_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.phase_detection_frame.setStyleSheet(self.frame_stylesheet)

        self.ui.load_pages.gait_detection_frame.setEnabled(False)
        self.ui.load_pages.imu_frame.setEnabled(False)
        self.ui.load_pages.phase_detection_frame.setEnabled(False)

        # CONNECT LINE EDITS
        self.lineEdit_burst_frequency.returnPressed.connect(self.lineEdit_burst_duration.setFocus)
        self.lineEdit_burst_duration.returnPressed.connect(self.lineEdit_pulse_deadtime.setFocus)
        self.lineEdit_pulse_deadtime.returnPressed.connect(self.lineEdit_interpulse_interval.setFocus)
        self.lineEdit_interpulse_interval.returnPressed.connect(self.lineEdit_carrier_frequency.setFocus)
        self.lineEdit_carrier_frequency.returnPressed.connect(self.lineEdit_burst_frequency.setFocus)

        self.lineEdit_burst_frequency.focused.connect(line_edit_focused)
        self.lineEdit_burst_duration.focused.connect(line_edit_focused)
        self.lineEdit_pulse_deadtime.focused.connect(line_edit_focused)
        self.lineEdit_interpulse_interval.focused.connect(line_edit_focused)
        self.lineEdit_carrier_frequency.focused.connect(line_edit_focused)

        self.lineEdit_burst_frequency.editingFinished.connect(calculate_stimulation_parameters)
        self.lineEdit_burst_duration.editingFinished.connect(calculate_stimulation_parameters)
        self.lineEdit_pulse_deadtime.editingFinished.connect(calculate_stimulation_parameters)
        self.lineEdit_interpulse_interval.editingFinished.connect(calculate_stimulation_parameters)
        self.lineEdit_carrier_frequency.editingFinished.connect(calculate_stimulation_parameters)

        # ADD WIDGETS
        self.ui.load_pages.task_selection_layout.addWidget(self.dropdown_btn_task, alignment=Qt.AlignmentFlag.AlignHCenter)
        #self.ui.load_pages.para_image_layout.addWidget(self.stim_para_image)
        self.ui.load_pages.back_image_layout.addWidget(self.dropdown_btn_placement, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.ui.load_pages.back_image_layout.addWidget(self.task_image)
        """ self.ui.load_pages.stim_para_layout.addWidget(self.lineEdit_burst_frequency, 0, 1)
        self.ui.load_pages.stim_para_layout.addWidget(self.lineEdit_burst_duration, 1, 1)
        self.ui.load_pages.stim_para_layout.addWidget(self.lineEdit_pulse_deadtime, 3, 1)
        self.ui.load_pages.stim_para_layout.addWidget(self.lineEdit_interpulse_interval, 4, 1)
        self.ui.load_pages.stim_para_layout.addWidget(self.lineEdit_carrier_frequency, 2, 1) """
        self.ui.load_pages.page_3_layout.addWidget(self.finish_btn_2, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Change frame color
        self.ui.load_pages.stim_para_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.back_image_frame.setStyleSheet(self.frame_stylesheet)
        # Hide the whole stimulation parameter frame from the user
        self.ui.load_pages.stim_para_frame.setVisible(False)

        # Place electrode selector + image aside the gait settings (Page 3)
        # Hide empty placeholder column
        self.ui.load_pages.para_image_widget.setVisible(False)
        # Move the back_image_frame to column 1, same row as the gait settings (task_option_frame)
        # Insert Study Phase frame at column 0, shift gait settings to column 1
        l = self.ui.load_pages.task_frame_layout
        # Remove existing widgets we want to re-place
        l.removeWidget(self.ui.load_pages.task_option_frame)

        # Add left -> right: Study Phase | Gait settings | (optional) Electrode/Image
        l.addWidget(self.study_phase_frame, 0, 0, 2, 1)
        l.addWidget(self.ui.load_pages.task_option_frame, 0, 1, 2, 1)
        l.addWidget(self.ui.load_pages.back_image_frame, 0, 2, 2, 1)
        self.ui.load_pages.back_image_frame.setMaximumSize(QSize(16777215, 16777215))

        # Column stretches to balance widths
        l.setColumnStretch(0, 1)  # Study phase
        l.setColumnStretch(1, 2)  # Gait settings
        l.setColumnStretch(2, 2)  # Electrode/image (if shown)

         # Initialize after all Page 3 widgets exist
        QTimer.singleShot(0, lambda: _apply_study_phase_to_task("phase_1"))
        _tighten_gait_spacing()

        # PAGE 4 - SAVE INFORMATION
        # ///////////////////////////////////////////////////////////////
        # MENU ACTIONS
        def adapt_layout(activated_button: QToolButton, selected_action: QAction):
            activated_button.setText(selected_action.text())
            # Hide frame and buttons
            self.ui.load_pages.custom_frame.setVisible(False)
            self.ui.load_pages.custom_selection_widget.setVisible(False)

            if selected_action.text() == "CustomText-SubjID-Time" or selected_action.text() == "CustomText-SubjID":
                # Show frame without buttons
                self.ui.load_pages.custom_frame.setVisible(True)

            if selected_action.text() == "CustomLayout":
                # Show frame and buttons
                self.ui.load_pages.custom_frame.setVisible(True)
                self.ui.load_pages.custom_selection_widget.setVisible(True)

            file_name = SetupMainWindow.create_file_name(selected_action.text(), self.subject_info_dict, self.name_format_list)
            self.lineEdit_file_name.setText(file_name)

        def change_text(activated_button: PyPushButton, selected_action: QAction):
            activated_button.setText(selected_action.text())
            self.lineEdit_file_name.setText(SetupMainWindow.create_file_name("CustomLayout", self.subject_info_dict, self.name_format_list))

        self.main_actions = [
            QAction("SubjID-Time"),
            QAction("Task-SubjID-Time"),
            QAction("Initials-Task-SubjID-Time"),
            QAction("CustomText-SubjID-Time"),
            QAction("CustomText-SubjID"),
            QAction("CustomLayout"),
        ]

        self.option_actions = [
            QAction("---"),
            QAction("Subject ID"),
            QAction("Task"),
            QAction("Initials"),
            QAction("Time"),
            QAction("Custom Text"),
        ]

        # LINE EDIT 1 - FILE NAME
        self.lineEdit_file_name = PyLineEdit(
            text="",
            place_holder_text="File Name",
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            adjust_size=True,
            constraints=[LINE_WIDTH_MID, LINE_HEIGHT, 3 * LINE_WIDTH_MID, LINE_HEIGHT],
        )
        self.lineEdit_file_name.adjust_size()
        self.lineEdit_file_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_file_name.setReadOnly(True)
        self.lineEdit_file_name.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # LINE EDIT 2 - CUSTOM TEXT
        self.lineEdit_custom_text: PyLineEdit = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Custom Text")
        self.lineEdit_custom_text.setMaximumWidth(LINE_WIDTH_MID)

        # DROPDOWN BUTTON MAIN
        self.dropdown_btn_format = SetupMainWindow.create_std_dropdown_btn(self.themes, self.main_actions, "File Name Format")
        self.dropdown_btn_format.setMinimumHeight(LINE_HEIGHT)

        # DROPDOWN BUTTON 1
        self.dropdown_btn_format_1 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.option_actions, "---")
        self.dropdown_btn_format_1.setMinimumWidth(DROPDOWN_WIDTH)
        self.dropdown_btn_format_1.setMinimumHeight(0)

        # DROPDOWN BUTTON 2
        self.dropdown_btn_format_2 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.option_actions, "---")
        self.dropdown_btn_format_2.setMinimumWidth(DROPDOWN_WIDTH)
        self.dropdown_btn_format_2.setMinimumHeight(0)

        # DROPDOWN BUTTON 3
        self.dropdown_btn_format_3 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.option_actions, "---")
        self.dropdown_btn_format_3.setMinimumWidth(DROPDOWN_WIDTH)
        self.dropdown_btn_format_3.setMinimumHeight(0)

        # DROPDOWN BUTTON 4
        self.dropdown_btn_format_4 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.option_actions, "---")
        self.dropdown_btn_format_4.setMinimumWidth(DROPDOWN_WIDTH)
        self.dropdown_btn_format_4.setMinimumHeight(0)

        # DROPDOWN BUTTON 5
        self.dropdown_btn_format_5 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.option_actions, "---")
        self.dropdown_btn_format_5.setMinimumWidth(DROPDOWN_WIDTH)
        self.dropdown_btn_format_5.setMinimumHeight(0)

        # PUSH BUTTON 1
        self.browser_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Browse")
        self.browser_btn.setMaximumHeight(LINE_HEIGHT)
        # Add icon to button
        self.browser_btn.setIcon(QIcon(Functions.set_svg_icon("icon_folder_open.svg")))

        # PUSH BUTTON 2
        self.finish_btn_3 = SetupMainWindow.create_std_push_btn(self.themes, text="Finish")
        self.finish_btn_3.setAutoDefault(True)

        # FILL LIST
        self.name_format_list: list[PyDropDownButton] = [
            self.dropdown_btn_format_1,
            self.dropdown_btn_format_2,
            self.dropdown_btn_format_3,
            self.dropdown_btn_format_4,
            self.dropdown_btn_format_5,
        ]

        # FILL DICTIONARY
        self.subject_info_dict["custom_text"] = self.lineEdit_custom_text

        # BUTTON CLICKED
        def browse_folder():
            path = QFileDialog.getExistingDirectory(self, "Select Directory", self.lineEdit_safe_path.text())
            self.lineEdit_safe_path.setText(path)

        # CONNECT BUTTONS
        self.dropdown_btn_format.clicked.connect(self.dropdown_btn_format.showMenu)
        self.dropdown_btn_format_1.clicked.connect(self.dropdown_btn_format_1.showMenu)
        self.dropdown_btn_format_2.clicked.connect(self.dropdown_btn_format_2.showMenu)
        self.dropdown_btn_format_3.clicked.connect(self.dropdown_btn_format_3.showMenu)
        self.dropdown_btn_format_4.clicked.connect(self.dropdown_btn_format_4.showMenu)
        self.dropdown_btn_format_5.clicked.connect(self.dropdown_btn_format_5.showMenu)
        self.browser_btn.clicked.connect(browse_folder)
        self.finish_btn_3.clicked.connect(finish_btn_clicked)

        self.dropdown_btn_format.action_selected.connect(adapt_layout)
        self.dropdown_btn_format_1.action_selected.connect(change_text)
        self.dropdown_btn_format_2.action_selected.connect(change_text)
        self.dropdown_btn_format_3.action_selected.connect(change_text)
        self.dropdown_btn_format_4.action_selected.connect(change_text)
        self.dropdown_btn_format_5.action_selected.connect(change_text)

        # CONNECT LINE EDITS
        self.lineEdit_custom_text.textChanged.connect(
            lambda: self.lineEdit_file_name.setText(
                SetupMainWindow.create_file_name(self.dropdown_btn_format.text(), self.subject_info_dict, self.name_format_list)
            )
        )

        # ADD WIDGETS
        self.ui.load_pages.dropdown_layout.addWidget(self.dropdown_btn_format, Qt.AlignmentFlag.AlignCenter, Qt.AlignmentFlag.AlignCenter)
        self.ui.load_pages.custom_selection_layout.addWidget(self.dropdown_btn_format_1)
        self.ui.load_pages.custom_selection_layout.addWidget(self.dropdown_btn_format_2)
        self.ui.load_pages.custom_selection_layout.addWidget(self.dropdown_btn_format_3)
        self.ui.load_pages.custom_selection_layout.addWidget(self.dropdown_btn_format_4)
        self.ui.load_pages.custom_selection_layout.addWidget(self.dropdown_btn_format_5)
        self.ui.load_pages.custom_text_layout.addWidget(self.lineEdit_custom_text)
        self.ui.load_pages.file_name_layout.addWidget(self.lineEdit_file_name)
        #self.ui.load_pages.browse_layout.addWidget(self.browser_btn, 0, 0, Qt.AlignmentFlag.AlignRight)
        #self.ui.load_pages.browse_layout.addWidget(self.lineEdit_safe_path)
        self.ui.load_pages.finish_btn_layout_2.addWidget(self.finish_btn_3)

        # Hide frame and buttons
        self.ui.load_pages.custom_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.custom_frame.setVisible(False)
        self.ui.load_pages.custom_selection_widget.setVisible(False)

         # Hide Page 4 completely
        if hasattr(self.ui.load_pages, "page_04"):
            self.ui.load_pages.page_04.setVisible(False)



        # --------------------------------------------------------------------
        # PAGE 10 - New Stimulation page (title + Carrier Frequency selection)
        # --------------------------------------------------------------------
        # Create Page 10 at runtime (so we don't touch the generated UI)
        self.ui.load_pages.page_10 = QWidget(self.ui.load_pages.pages)
        self.ui.load_pages.page_10.setObjectName("page_10")
        self.ui.load_pages.page_10_layout = QVBoxLayout(self.ui.load_pages.page_10)
        self.ui.load_pages.page_10_layout.setContentsMargins(6, 6, 6, 6)
        self.ui.load_pages.page_10_layout.setSpacing(8)

        # Title
        self.stim_params_title_10 = QLabel("Stimulation Parameters", self.ui.load_pages.page_10)
        self.stim_params_title_10.setStyleSheet("font-size: 16pt;")
        self.stim_params_title_10.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.load_pages.page_10_layout.addWidget(self.stim_params_title_10)

        # First row: Carrier Frequency with exclusive checkboxes
        self.cf_row_10 = QWidget(self.ui.load_pages.page_10)
        self.cf_row_10_layout = QHBoxLayout(self.cf_row_10)
        self.cf_row_10_layout.setContentsMargins(9, 6, 9, 6)
        self.cf_row_10_layout.setSpacing(12)

        self.cf_label_10 = QLabel("tSCS Carrier Frequency:", self.cf_row_10)
        self.cf_label_10.setStyleSheet("font-size: 12pt;")
        self.cf_0khz_cb = QCheckBox("0 kHz", self.cf_row_10)
        self.cf_5khz_cb = QCheckBox("5 kHz", self.cf_row_10)
        self.cf_10khz_cb = QCheckBox("10 kHz", self.cf_row_10)

        # New: Other option with entry (kHz)
        self.cf_other_cb = QCheckBox("Other", self.cf_row_10)
        self.cf_other_edit = PyLineEdit(
            text="2.5",  # preset to 2.5 kHz
            place_holder_text="kHz",
            radius=8,
            border_size=2,
            color=self.themes["app_color"]["text_foreground"],
            selection_color=self.themes["app_color"]["white"],
            bg_color=self.themes["app_color"]["dark_one"],
            bg_color_active=self.themes["app_color"]["dark_three"],
            context_color=self.themes["app_color"]["context_color"],
            adjust_size=True,
            constraints=[80, 26, 120, 26],
        )
        self.cf_other_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Accept 0.00 .. 100.00 kHz
        self.cf_other_edit.setValidator(QDoubleValidator(0.0, 100.0, 2))
        self.cf_other_edit.setEnabled(False)

        self.cf_group_10 = QButtonGroup(self.cf_row_10)
        self.cf_group_10.setExclusive(True)
        self.cf_group_10.addButton(self.cf_0khz_cb)
        self.cf_group_10.addButton(self.cf_5khz_cb)
        self.cf_group_10.addButton(self.cf_10khz_cb)
        self.cf_group_10.addButton(self.cf_other_cb)


        self.cf_row_10_layout.addWidget(self.cf_label_10)
        self.cf_row_10_layout.addWidget(self.cf_0khz_cb)
        self.cf_row_10_layout.addWidget(self.cf_5khz_cb)
        self.cf_row_10_layout.addWidget(self.cf_10khz_cb)
        self.cf_row_10_layout.addWidget(self.cf_other_cb)
        self.cf_row_10_layout.addWidget(self.cf_other_edit)
        self.cf_row_10_layout.addStretch(1)
        
        # FES Frequency (Hz) - appears to the left of burst Width for FES-only / hybrid
        self.burst_freq_fes_label = QLabel("FES Frequency [Hz]:", self.cf_row_10)
        self.burst_freq_fes_label.setStyleSheet("font-size: 12pt;")
        self.lineEdit_burst_frequency_fes = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="50")
        self.lineEdit_burst_frequency_fes.setMaximumWidth(100)
        self.lineEdit_burst_frequency_fes.setValidator(QIntValidator(1, 100000, self))
        # Default hidden; visibility updated by toggles below (same logic used for pulse width)
        self.burst_freq_fes_label.setVisible(False)
        self.lineEdit_burst_frequency_fes.setVisible(False)
        # Insert frequency widget before burst width so it appears on the left
        self.cf_row_10_layout.addWidget(self.burst_freq_fes_label)
        self.cf_row_10_layout.addWidget(self.lineEdit_burst_frequency_fes)

        
        # FES Pulse Width (μs) - appears in place of Carrier for FES-only, and alongside Carrier for hybrid
        self.pulse_width_fes_label = QLabel("FES Pulse Width [\u03bcs]:", self.cf_row_10)
        self.pulse_width_fes_label.setStyleSheet("font-size: 12pt;")
        self.lineEdit_pulse_width_fes = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="280")
        self.lineEdit_pulse_width_fes.setMaximumWidth(120)
        self.lineEdit_pulse_width_fes.setValidator(QIntValidator(1, 10000, self))
        # Default hidden; visibility updated by toggles below
        self.pulse_width_fes_label.setVisible(False)
        self.lineEdit_pulse_width_fes.setVisible(False)
        self.cf_row_10_layout.addWidget(self.pulse_width_fes_label)
        self.cf_row_10_layout.addWidget(self.lineEdit_pulse_width_fes)
        
        
        # Show/Hide carrier / FES pulse-width depending on toggles
        def _update_carrier_and_pulse_width_visibility(_=None):
            try:
                fes_on = bool(getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked())
                tscs_on = bool(getattr(self, "tscs_toggle", None) and self.tscs_toggle.isChecked())
                # tSCS-only: show carrier, hide FES pulse width
                if tscs_on and not fes_on:
                    for w in (self.cf_label_10, self.cf_0khz_cb, self.cf_5khz_cb, self.cf_10khz_cb, self.cf_other_cb, self.cf_other_edit):
                        try: w.setVisible(True)
                        except Exception: pass
                    self.pulse_width_fes_label.setVisible(False)
                    self.lineEdit_pulse_width_fes.setVisible(False)
                    self.burst_freq_fes_label.setVisible(False)
                    self.lineEdit_burst_frequency_fes.setVisible(False)
                # FES-only: hide carrier controls, show pulse width
                elif fes_on and not tscs_on:
                    for w in (self.cf_label_10, self.cf_0khz_cb, self.cf_5khz_cb, self.cf_10khz_cb, self.cf_other_cb, self.cf_other_edit):
                        try: w.setVisible(False)
                        except Exception: pass
                    self.pulse_width_fes_label.setVisible(True)
                    self.lineEdit_pulse_width_fes.setVisible(True)
                    self.burst_freq_fes_label.setVisible(True)
                    self.lineEdit_burst_frequency_fes.setVisible(True)   
                    # Hybrid: show both
                else:
                    for w in (self.cf_label_10, self.cf_0khz_cb, self.cf_5khz_cb, self.cf_10khz_cb, self.cf_other_cb, self.cf_other_edit):
                        try: w.setVisible(True)
                        except Exception: pass
                    self.pulse_width_fes_label.setVisible(True)
                    self.lineEdit_pulse_width_fes.setVisible(True)
                    self.burst_freq_fes_label.setVisible(True)
                    self.lineEdit_burst_frequency_fes.setVisible(True)
            except Exception:
                pass
        # initialize and wire toggles
        _update_carrier_and_pulse_width_visibility()
        try:
            self.tscs_toggle.toggled.connect(_update_carrier_and_pulse_width_visibility)
            self.fes_toggle.toggled.connect(_update_carrier_and_pulse_width_visibility)
        except Exception:
            pass
        # Recompute preview when user edits FES pulse-width
        try:
            self.lineEdit_pulse_width_fes.editingFinished.connect(calculate_stimulation_parameters)
            self.lineEdit_burst_frequency_fes.editingFinished.connect(calculate_stimulation_parameters)
        except Exception:
            pass
 
        #Function to get Burst duration from Pulse width 
        def calculate_burst_duration_FES() -> float :
            tscs_on = bool(getattr(self, "tscs_toggle", None) and self.tscs_toggle.isChecked())
            fes_on = bool(getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked())
            
            
            pw = float(self.lineEdit_pulse_width_fes.text()) if getattr(self, "lineEdit_pulse_width_fes", None) and self.lineEdit_pulse_width_fes.text().strip() else 0

            if fes_on and not tscs_on:
                if pw == 0: 
                    bd = self.lineEdit_burst_duration.as_value()
                else:
                    bd = 2*pw
            
            elif fes_on and tscs_on: 
                if pw == 0: 
                    bd = self.lineEdit_burst_duration_fes.as_value()
                else:
                    bd = 2*pw
                    
            else: 
                bd=0
            
            return bd
        
        #Function to get Burst frequency
        def return_frequency_FES() -> float :
            tscs_on = bool(getattr(self, "tscs_toggle", None) and self.tscs_toggle.isChecked())
            fes_on = bool(getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked())
            
            
            freq = float(self.lineEdit_burst_frequency_fes.text()) if getattr(self, "lineEdit_burst_frequency_fes", None) and self.lineEdit_burst_frequency_fes.text().strip() else 0

            if fes_on and not tscs_on:
                if freq == 0: 
                    freq_fes = self.lineEdit_burst_frequency.as_value()
                else:
                    freq_fes = freq
            
            elif fes_on and tscs_on: 
                if freq == 0: 
                    freq_fes = self.lineEdit_burst_frequency_fes.as_value()
                else:
                    freq_fes = freq
                    
            else: 
                freq_fes=0
            
            return freq_fes
                    
        # -- New: Personalize channels toggle (Page 10) --
        self.page10_personalize_channels_cb = QCheckBox("Personalize channels", self.cf_row_10)
        self.page10_personalize_channels_cb.setToolTip("Enable manual mapping of hardware channels to each electrode row")
        self.page10_personalize_channels_cb.setMinimumHeight(28)
        # NEW: Personalize gait model toggle (Page 10)
        self.page10_personalize_gait_cb = QCheckBox("Personalize gait model", self.cf_row_10)
        self.page10_personalize_gait_cb.setToolTip("Customize which gait phases trigger each target")
        self.page10_personalize_gait_cb.setMinimumHeight(28)
        
        self.ui.load_pages.page_10_layout.addWidget(self.cf_row_10)

        # --- Page 10: Selected Task (read-only) + Electrode Image ---
        # Frame for task display and image, similar to Page 5 layout (but simpler)
        self.task_view_frame_10 = QFrame(self.ui.load_pages.page_10)
        self.task_view_frame_10.setObjectName("task_view_frame_10")
        self.task_view_frame_10.setStyleSheet(self.frame_stylesheet)
        self.task_view_layout_10 = QVBoxLayout(self.task_view_frame_10)
        self.task_view_layout_10.setContentsMargins(9, 6, 9, 6)
        self.task_view_layout_10.setSpacing(6)

        # Selected Task (read-only, centered)
        self.selected_task_widget_10 = QWidget(self.task_view_frame_10)
        self.selected_task_layout_10 = QHBoxLayout(self.selected_task_widget_10)
        self.selected_task_layout_10.setContentsMargins(0, 0, 0, 0)
        self.selected_task_layout_10.setSpacing(0)
        self.lineEdit_selected_task_10 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="No Task Selected")
        self.lineEdit_selected_task_10.setReadOnly(True)
        self.lineEdit_selected_task_10.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_selected_task_10.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_task_layout_10.addWidget(self.lineEdit_selected_task_10)
        self.task_view_layout_10.addWidget(self.selected_task_widget_10)

        # NEW: Top-left controls row inside the task_view_frame_10
        self.page10_controls_row = QWidget(self.task_view_frame_10)
        self.page10_controls_row_layout = QHBoxLayout(self.page10_controls_row)
        self.page10_controls_row_layout.setContentsMargins(0, 0, 0, 0)
        self.page10_controls_row_layout.setSpacing(6)
        # Show gait-model selector only when tSCS mode is active (tSCS-only)
        def _update_gait_model_visibility(_=None):
            try:
                visible = bool(getattr(self, "tscs_toggle", None) and self.tscs_toggle.isChecked()) 
                self.gait_model_label.setVisible(visible)
                self.dropdown_btn_gait_model.setVisible(visible)
            except Exception:
                pass

        # initialize visibility now and whenever toggles change
        _update_gait_model_visibility()
        try:
            self.tscs_toggle.toggled.connect(_update_gait_model_visibility)
            self.fes_toggle.toggled.connect(_update_gait_model_visibility)
        except Exception:
            pass
        
        # --- INSERT: Gait Model label + dropdown (left-most) ---
        self.gait_model_actions = [
            QAction("Gait Model with Distal"),
            QAction("Gait Model without Distal"),
       ]
        self.dropdown_btn_gait_model = SetupMainWindow.create_std_dropdown_btn(self.themes, self.gait_model_actions, "Gait Model with Distal")
        self.dropdown_btn_gait_model.setMinimumWidth(DROPDOWN_WIDTH)
        self.dropdown_btn_gait_model.clicked.connect(self.dropdown_btn_gait_model.showMenu)
        # Optional tooltip
        self.dropdown_btn_gait_model.setToolTip("Select gait model. 'With Distal' includes pre-swing for Distal targets.")
        # Disable 'without Distal' if FSR Optional method selected
        if getattr(self, "_restrict_gait_model", False):
            for act in self.gait_model_actions:
                if act.text() == "Gait Model with Distal":
                    act.setEnabled(False)
            self.dropdown_btn_gait_model.setText("Gait Model without Distal")
            self.dropdown_btn_gait_model.setEnabled(False)
            self.dropdown_btn_gait_model.setToolTip("Locked to 'Gait Model without Distal'.")
        self.gait_model_label = QLabel("Gait Model:")
        self.gait_model_label.setMinimumWidth(90)
        self.page10_controls_row_layout.addWidget(self.gait_model_label)
        self.page10_controls_row_layout.addWidget(self.dropdown_btn_gait_model)
        # small spacer so subsequent controls don't stick to the dropdown
        self.page10_controls_row_layout.addSpacing(6)

        # Reparent and place the 'Personalize channels' checkbox here (upper-left)
        try:
            self.cf_row_10_layout.removeWidget(self.page10_personalize_channels_cb)
        except Exception:
            pass
        self.page10_personalize_channels_cb.setParent(self.page10_controls_row)
        self.page10_controls_row_layout.addWidget(self.page10_personalize_channels_cb)
        # Add the new gait toggle
        self.page10_controls_row_layout.addWidget(self.page10_personalize_gait_cb)
        self.page10_controls_row_layout.addStretch(1)
        

        # --- PRE-SWING PERCENTAGE CONTROLS (right side) ---
        self.page10_pre_swing_label = QLabel("Pre-swing Percentage:")
        self.page10_pre_swing_label.setStyleSheet("font-size: 12pt;")
        tip = "Varying the percentage of Pre-swing will vary the duration of Hamstring stimulation"

        self.page10_pre_swing_15_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="15%")
        self.page10_pre_swing_15_toggle.setToolTip(tip)
        self.page10_pre_swing_15_toggle.setMinimumHeight(LINE_HEIGHT)

        self.page10_pre_swing_10_toggle = SetupMainWindow.create_std_small_toggle(self.themes, text="10%")
        self.page10_pre_swing_10_toggle.setToolTip(tip)
        self.page10_pre_swing_10_toggle.setMinimumHeight(LINE_HEIGHT)

        # default to 15%
        self.page10_pre_swing_15_toggle.setChecked(True)

        # Make them exclusive
        self.page10_pre_swing_group = QButtonGroup(self.page10_controls_row)
        self.page10_pre_swing_group.setExclusive(True)
        self.page10_pre_swing_group.addButton(self.page10_pre_swing_15_toggle)
        self.page10_pre_swing_group.addButton(self.page10_pre_swing_10_toggle)

        # Put them in a right-aligned container and add to controls row
        right_ps_widget = QWidget(self.page10_controls_row)
        right_ps_layout = QHBoxLayout(right_ps_widget)
        right_ps_layout.setContentsMargins(0, 0, 0, 0)
        right_ps_layout.setSpacing(6)
        right_ps_layout.addWidget(self.page10_pre_swing_label)
        right_ps_layout.addWidget(self.page10_pre_swing_15_toggle)
        right_ps_layout.addWidget(self.page10_pre_swing_10_toggle)
        self.page10_controls_row_layout.addWidget(right_ps_widget)

        # Default reversed mapping: target -> set(phases)
        def _default_gait_model_map() -> dict[str, set[Phase]]:
            m: dict[str, set[Phase]] = {}
            def _iter_targets(side_targets):
                for item in side_targets:
                    if isinstance(item, (list, tuple)):
                        for t in item:
                            if t and t != "unknown":
                                yield t
                    else:
                        if item and item != "unknown":
                            yield item
            for phase, (left_targets, right_targets) in MUSCULAR_GROUP_SELECTION.items():
                if phase == Phase.UNKNOWN:
                    continue
                for tgt in _iter_targets(left_targets):
                    m.setdefault(tgt, set()).add(phase)
                for tgt in _iter_targets(right_targets):
                    m.setdefault(tgt, set()).add(phase)
            return m

        # Store per-target phases; initialize once
        self.page10_gait_model_map = getattr(self, "page10_gait_model_map", _default_gait_model_map())
        self._page10_gait_default_inited = getattr(self, "_page10_gait_default_inited", False)

        # Per-row widget refs to clean up on rebuild
        self.page10_gait_sel: dict[int, QToolButton] = {}
        # Track last chosen targets per row (used by _target_text_for_row)
        self._page10_prev_target_text = getattr(self, "_page10_prev_target_text", {})

        #Mutually exclusive toggles; rebuild on change
        def _on_channels_personalize_toggled(checked: bool):
            if checked and self.page10_personalize_gait_cb.isChecked():
                self.page10_personalize_gait_cb.blockSignals(True)
                self.page10_personalize_gait_cb.setChecked(False)
                self.page10_personalize_gait_cb.blockSignals(False)
            try:
                _rebuild_page10_rows()
            except Exception:
                pass

        def _on_gait_personalize_toggled(checked: bool):
            if checked and self.page10_personalize_channels_cb.isChecked():
                self.page10_personalize_channels_cb.blockSignals(True)
                self.page10_personalize_channels_cb.setChecked(False)
                self.page10_personalize_channels_cb.blockSignals(False)
            # Initialize defaults on first enable, or if map empty
            if checked and (not self._page10_gait_default_inited or not any(self.page10_gait_model_map.values())):
                self.page10_gait_model_map = _default_gait_model_map()
                self._page10_gait_default_inited = True
            try:
                _rebuild_page10_rows()
            except Exception:
                pass

        # add mutually exclusive functionnality
        self.page10_personalize_channels_cb.toggled.connect(_on_channels_personalize_toggled)
        self.page10_personalize_gait_cb.toggled.connect(_on_gait_personalize_toggled)


        # Insert just under the Selected Task (before the image+grids row)
        self.task_view_layout_10.addWidget(self.page10_controls_row, 0, Qt.AlignmentFlag.AlignLeft)

        # Center row with Left grid | Image | Right grid
        self.page10_center_row = QWidget(self.task_view_frame_10)
        self.page10_center_row_layout = QHBoxLayout(self.page10_center_row)
        self.page10_center_row_layout.setContentsMargins(0, 0, 0, 0)
        self.page10_center_row_layout.setSpacing(8)

        # Left side grid (Target | Current | Electrode)
        self.page10_left_widget = QWidget(self.task_view_frame_10)
        self.page10_left_grid = QGridLayout(self.page10_left_widget)
        self.page10_left_grid.setContentsMargins(0, 0, 0, 0)
        self.page10_left_grid.setHorizontalSpacing(8)
        self.page10_left_grid.setVerticalSpacing(4)
        # Styled header labels (bigger + bold)
        header_css = "font-size: 16pt;"


        self.page10_left_hdr_target = QLabel("Target")
        self.page10_left_hdr_target.setStyleSheet(header_css)
        self.page10_left_hdr_current_label = QLabel("Current [mA]")
        #self.page10_left_hdr_current_label.setStyleSheet(header_css)
        self.page10_left_hdr_max_label = QLabel("Max current [mA]")
        #self.page10_left_hdr_max_label.setStyleSheet(header_css)
        self.page10_left_hdr_max_label.setVisible(False)
        # Pack both into a small widget so they occupy the same header cell
        hdr_left_widget = QWidget()
        hdr_left_layout = QHBoxLayout(hdr_left_widget)
        hdr_left_layout.setContentsMargins(0, 0, 0, 0)
        hdr_left_layout.setSpacing(6)
        hdr_left_layout.addWidget(self.page10_left_hdr_current_label)
        hdr_left_layout.addWidget(self.page10_left_hdr_max_label)
        self.page10_left_hdr_current = hdr_left_widget
        
        self.page10_left_hdr_electrode = QLabel("Electrode")
        self.page10_left_hdr_electrode.setStyleSheet(header_css)
        # New header for Channel (hidden by default)
        self.page10_left_hdr_channel = QLabel("Channel")
        self.page10_left_hdr_channel.setStyleSheet(header_css)
        self.page10_left_hdr_channel.setVisible(False)
        # New header for Gait Phases (hidden by default)
        self.page10_left_hdr_gait_phases = QLabel("Gait Phases")
        self.page10_left_hdr_gait_phases.setStyleSheet(header_css)
        self.page10_left_hdr_gait_phases.setVisible(False)

        self.page10_left_grid.addWidget(self.page10_left_hdr_gait_phases,   0, 0, Qt.AlignmentFlag.AlignCenter)
        self.page10_left_grid.addWidget(self.page10_left_hdr_target,   0, 1, Qt.AlignmentFlag.AlignCenter)
        self.page10_left_grid.addWidget(self.page10_left_hdr_current,  0, 2, Qt.AlignmentFlag.AlignCenter)
        self.page10_left_grid.addWidget(self.page10_left_hdr_electrode,0, 3, Qt.AlignmentFlag.AlignCenter)
        self.page10_left_grid.addWidget(self.page10_left_hdr_channel,  0, 4, Qt.AlignmentFlag.AlignCenter)

        # Add left grid aligned to top so headers line up horizontally
        self.page10_center_row_layout.addWidget(self.page10_left_widget, 0, Qt.AlignmentFlag.AlignVCenter)


        # Electrode image (separate instance for Page 10)
        self.back_image_10 = QSvgWidget()
        SetupMainWindow.load_back_image_page10("No Electrodes", self.back_image_10)
        self.page10_center_row_layout.addWidget(self.back_image_10, 1, Qt.AlignmentFlag.AlignCenter)

        # Right side grid (Electrode | Current | Target) - mirrored
        self.page10_right_widget = QWidget(self.task_view_frame_10)
        self.page10_right_grid = QGridLayout(self.page10_right_widget)
        self.page10_right_grid.setContentsMargins(0, 0, 0, 0)
        self.page10_right_grid.setHorizontalSpacing(8)
        self.page10_right_grid.setVerticalSpacing(4)

        self.page10_right_hdr_electrode = QLabel("Electrode")
        self.page10_right_hdr_electrode.setStyleSheet(header_css)
        # Right header: same composite as left
        self.page10_right_hdr_current_label = QLabel("Current [mA]")
        #self.page10_right_hdr_current_label.setStyleSheet(header_css)
        self.page10_right_hdr_max_label = QLabel("Max current [mA]")
        #self.page10_right_hdr_max_label.setStyleSheet(header_css)
        self.page10_right_hdr_max_label.setVisible(False)
        hdr_right_widget = QWidget()
        hdr_right_layout = QHBoxLayout(hdr_right_widget)
        hdr_right_layout.setContentsMargins(0, 0, 0, 0)
        hdr_right_layout.setSpacing(6)
        hdr_right_layout.addWidget(self.page10_right_hdr_current_label)
        hdr_right_layout.addWidget(self.page10_right_hdr_max_label)
        self.page10_right_hdr_current = hdr_right_widget
        self.page10_right_hdr_target = QLabel("Target")
        self.page10_right_hdr_target.setStyleSheet(header_css)
        
        # New header for Channel (hidden by default)
        self.page10_right_hdr_channel = QLabel("Channel")
        self.page10_right_hdr_channel.setStyleSheet(header_css)
        self.page10_right_hdr_channel.setVisible(False)
        # New header for Gait Phases (hidden by default)
        self.page10_right_hdr_gait_phases = QLabel("Gait Phases")
        self.page10_right_hdr_gait_phases.setStyleSheet(header_css)
        self.page10_right_hdr_gait_phases.setVisible(False)

        self.page10_right_grid.addWidget(self.page10_right_hdr_channel, 0, 0, Qt.AlignmentFlag.AlignCenter)
        # Insert Channel header between Electrode and Current on right-side grid
        self.page10_right_grid.addWidget(self.page10_right_hdr_electrode,   0, 1, Qt.AlignmentFlag.AlignCenter)
        self.page10_right_grid.addWidget(self.page10_right_hdr_current,   0, 2, Qt.AlignmentFlag.AlignCenter)
        self.page10_right_grid.addWidget(self.page10_right_hdr_target,    0, 3, Qt.AlignmentFlag.AlignCenter)
        self.page10_right_grid.addWidget(self.page10_right_hdr_gait_phases, 0, 4, Qt.AlignmentFlag.AlignCenter)

        
        # Add right grid aligned to top so headers line up horizontally
        self.page10_center_row_layout.addWidget(self.page10_right_widget, 0, Qt.AlignmentFlag.AlignVCenter)

        # Add the center row (grids + image) to the frame
        self.task_view_layout_10.addWidget(self.page10_center_row)
        # Let the image row take available vertical space
        self.ui.load_pages.page_10_layout.addWidget(self.task_view_frame_10)
        self.ui.load_pages.page_10_layout.setStretchFactor(self.task_view_frame_10, 1)

        """ # Electrode image (separate instance for Page 10)
        # ADD IMAGE
        self.back_image_10 = QSvgWidget()
        SetupMainWindow.load_back_image_page10("No Electrodes", self.back_image_10)

        self.task_view_layout_10.addWidget(self.back_image_10, alignment=Qt.AlignmentFlag.AlignCenter)
        # Let the image row take available vertical space
        self.ui.load_pages.page_10_layout.setStretchFactor(self.task_view_frame_10, 1) """

        # Add the frame to Page 10
        self.ui.load_pages.page_10_layout.addWidget(self.task_view_frame_10)

        # ------- Page 10: Current/Target column cells (mirror Page 5 currents) -------
        # Current editors mirror Page 5 per-channel optimal edits; Target dropdowns are selected per channel here
        self.page10_curr_opt: dict[int, PyLineEdit] = {}
        self.page10_target_sel: dict[int, PyDropDownButton] = {}
        # New: per-electrode channel selector buttons
        self.page10_channel_sel: dict[int, PyDropDownButton] = {}
        # Keep previous channel selections across rebuilds
        self._page10_prev_channel_text: dict[int, str] = {}
        # Keep previous target selections across rebuilds (row index -> target label)
        self._page10_prev_target_text: dict[int, str] = {}
        # NEW: Persisted row -> hardware channel mapping (survives toggle)
        self.page10_row_channel_map: dict[int, int] = {}
        # Target label map: UI label -> internal key used in create_dict / StimulatorParameters
        # Set active Page10 target map according to current stimulation mode.
        # The actual maps are defined earlier (_tscs_target_map / _fes_target_map).
        # Choose the active target map according to current stimulation mode (supports 'tscs', 'fes', 'hybrid')
        mode = getattr(self, "_stimulation_mode", "tscs")
        if mode == "hybrid":
            active = self._hybrid_target_map
        elif mode == "fes":
            active = self._fes_target_map
        else:
            active = self._tscs_target_map
        self.page10_target_key_map = dict(active)            
        
        # Keep a flat list of label strings for dynamic menus
        self.page10_target_labels: list[str] = list(self.page10_target_key_map.keys())

        # Persist per-row current values across UI rebuilds (independent of personalize toggle)
        self.page10_row_current_map: dict[int, str] = {}

        def _extract_text(w: QWidget) -> str:
            try:
                if hasattr(w, "text"):
                    return w.text()
                le = w.findChild(QLineEdit)
                return le.text() if le else ""
            except Exception:
                return ""

        # --- Helpers to mirror Page 10 into confirmation page (Channel 0..7) ---
        def _page10_row_to_hw_channel(row_idx: int) -> int:
            # Always prefer the persisted mapping, independent of checkbox visibility
            try:
                if row_idx in self.page10_row_channel_map:
                    return int(self.page10_row_channel_map[row_idx])
            except Exception:
                pass
            # If a dropdown exists (when personalize is shown), capture the value into the mapping
            try:
                btn = self.page10_channel_sel.get(row_idx)
                txt = btn.text() if btn else ""
                if txt and txt.startswith("Channel"):
                    ch = int(txt.split()[-1])
                    self.page10_row_channel_map[row_idx] = ch
                    return ch
            except Exception:
                pass
            # Fallback default: Channel == row index
            return row_idx

        def _page10_electrode_row_count() -> int:
            # Infer number of rows from current placement
            try:
                arrangement = self.dropdown_btn_placement.text()
            except Exception:
                arrangement = "No Electrodes" or "FES - No Stimulation"
            if arrangement == "Singlesite":
                return 1
            if arrangement == "Multisite - Six Electrodes":
                return 6
            if arrangement == "Combination - Seven Electrodes":
                return 7
            if arrangement == "Multisite - Eight Electrodes":
                return 8
            
            # Accept the FES placement label as an explicit 8-electrode option
            if arrangement == "FES - 8 Electrodes" or arrangement.strip().lower() == "fes - 8 electrodes":
                return 8

            if arrangement == "Three Electrodes":
                return 3
            if arrangement == "Four Electrodes":
                return 4
            return 0

        def _page10_build_channel_current_map() -> dict[int, str]:
            # Build Channel N -> current string from Page 10 rows
            m: dict[int, str] = {}
            n_rows = max(_page10_electrode_row_count(), len(self.page10_curr_opt))
            for row in range(n_rows):
                try:
                    ch = _page10_row_to_hw_channel(row)
                    editor = self.page10_curr_opt.get(row)
                    val = editor.text().strip() if editor else ""
                    if val and ch not in m:
                        m[ch] = val
                except Exception:
                    continue
            return m

        def _apply_page10_to_confirmation():
            # 1) Currents
            mapping = _page10_build_channel_current_map()

            # 2) Targets per hardware channel (from Page 10 target selections)
            ch_to_target: dict[int, str] = {}
            try:
                for row_idx, btn in getattr(self, "page10_target_sel", {}).items():
                    if not btn:
                        continue
                    lbl = btn.text().strip()
                    if not lbl or lbl == "Not to be used":
                        continue
                    ch = _page10_row_to_hw_channel(row_idx)
                    ch_to_target[ch] = lbl
            except Exception:
                ch_to_target = {}

            for ch in range(8):
                try:
                    # Current
                    le_curr: PyLineEdit = getattr(self, f"lineEdit_channel_{ch}_confirm")
                    le_curr.setText(mapping.get(ch, ""))
                except Exception:
                    pass
                try:
                    # Target
                    le_tgt: PyLineEdit = getattr(self, f"lineEdit_channel_{ch}_target_confirm", None)
                    if le_tgt:
                        le_tgt.setText(ch_to_target.get(ch, ""))
                except Exception:
                    pass

        def _make_target_cell(ch_idx: int) -> PyDropDownButton:
            # Create Page 10 target dropdown for a given channel
            btn = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
            btn.setMinimumHeight(LINE_HEIGHT)
            self.page10_target_sel[ch_idx] = btn
            # Ensure the menu opens on click
            btn.clicked.connect(btn.showMenu)
            return btn


        # def _make_current_cell(ch_idx: int) -> QWidget:
        #     # Create a current QLineEdit with persisted/default value
        #     edit = SetupMainWindow.create_std_line_edit(self.themes)
        #     edit.setMinimumHeight(LINE_HEIGHT)
        #     edit.setMaximumWidth(LINE_WIDTH_MID)
        #     edit.setPlaceholderText("Optimal current [mA]")
        #     edit.setValidator(QIntValidator(0, 220, self))  # adapt bounds as needed

        #     # Default text priority: previous UI value -> persisted map -> keep existing -> "0"
        #     prev = getattr(self, "_page10_prev_current_text", {}).get(ch_idx)
        #     persisted = self.page10_row_current_map.get(ch_idx)
        #     if prev is not None and prev != "":
        #         edit.setText(prev)
        #     elif persisted is not None and persisted != "":
        #         edit.setText(persisted)
        #     elif edit.text().strip() == "":
        #         edit.setText("0")

        #     # Persist on change and refresh confirmation page
        #     def _persist_current():
        #         try:
        #             self.page10_row_current_map[ch_idx] = edit.text()
        #             try:
        #                 _apply_page10_to_confirmation()
        #             except Exception:
        #                 pass
        #         except Exception:
        #             pass
        #     edit.editingFinished.connect(_persist_current)
        #     edit.textChanged.connect(lambda _: _persist_current())

        #     # Keep a handle to restore on next rebuild
        #     self.page10_curr_opt[ch_idx] = edit
        #     return edit

        # Composite widget: Optimal current + Max current (Max visible only when closed-loop enabled)
        def _make_current_cell(ch_idx: int) -> QWidget:
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)

            # Optimal current (left)
            opt = SetupMainWindow.create_std_line_edit(self.themes)
            opt.setMinimumHeight(LINE_HEIGHT)
            opt.setMaximumWidth(LINE_WIDTH_MID)
            opt.setPlaceholderText("Optimal current [mA]")
            opt.setValidator(QIntValidator(0, 220, self))

            # Max current (right) — mirror Page 5 max field when present
            max_le = SetupMainWindow.create_std_line_edit(self.themes)
            max_le.setMinimumHeight(LINE_HEIGHT)
            max_le.setMaximumWidth(LINE_WIDTH_MID // 1)  # slightly smaller
            max_le.setPlaceholderText("Max current [mA]")
            max_le.setValidator(QIntValidator(0, 220, self))

            # Populate values: previous UI -> persisted -> Page5 master -> default "0"
            prev_opt = getattr(self, "_page10_prev_current_text", {}).get(ch_idx)
            persisted_opt = self.page10_row_current_map.get(ch_idx)
            if prev_opt is not None and prev_opt != "":
                opt.setText(prev_opt)
            elif persisted_opt is not None and persisted_opt != "":
                opt.setText(persisted_opt)
            elif opt.text().strip() == "":
                opt.setText("0")

            # Max initial value - prefer persisted page10 map, else Page5 master (channel_max_dict), else same as opt
            persisted_max = getattr(self, "page10_row_max_map", {}).get(ch_idx)
            page5_max = None
            try:
                page5_max = self.channel_max_dict.get(f"Channel {ch_idx}", None)
                page5_max = page5_max.text().strip() if page5_max is not None else None
            except Exception:
                page5_max = None
            if persisted_max:
                max_le.setText(persisted_max)
            elif page5_max:
                max_le.setText(page5_max)
            else:
                max_le.setText(opt.text().strip() or "0")

            # Persist functions
            def _persist_opt():
                try:
                    self.page10_row_current_map[ch_idx] = opt.text().strip()
                except Exception:
                    pass
                QTimer.singleShot(0, _apply_page10_to_confirmation)

            def _persist_max():
                try:
                    # keep a small per-row map for max values
                    if not hasattr(self, "page10_row_max_map"):
                        self.page10_row_max_map = {}
                    self.page10_row_max_map[ch_idx] = max_le.text().strip()
                    # Mirror to Page5 master max field so other code reads it from the canonical location
                    try:
                        main_le = self.channel_max_dict.get(f"Channel {ch_idx}", None)
                        if main_le is not None:
                            main_le.setText(max_le.text().strip())
                    except Exception:
                        pass
                except Exception:
                    pass
                QTimer.singleShot(0, _apply_page10_to_confirmation)

            opt.editingFinished.connect(_persist_opt)
            opt.textChanged.connect(lambda _: _persist_opt())
            max_le.editingFinished.connect(_persist_max)
            max_le.textChanged.connect(lambda _: _persist_max())

            # Keep handles for restore and external toggles
            self.page10_curr_opt[ch_idx] = opt
            if not hasattr(self, "page10_curr_max"):
                self.page10_curr_max = {}
            self.page10_curr_max[ch_idx] = max_le

            h.addWidget(opt, 1)
            h.addWidget(max_le, 0)

            # Show/hide max depending on closed-loop toggle initially and on changes
            def _sync_max_visibility(checked: bool):
                try:
                    max_le.setVisible(bool(checked))
                    # also toggle the small header max label on both sides
                    try:
                        self.page10_left_hdr_max_label.setVisible(bool(checked))
                    except Exception:
                        pass
                    try:
                        self.page10_right_hdr_max_label.setVisible(bool(checked))
                    except Exception:
                        pass
                except Exception:
                    pass

            try:
                # set initial visibility and connect toggle
                initial = bool(getattr(self, "closed_loop_toggle", None) and self.closed_loop_toggle.isChecked())
                _sync_max_visibility(initial)
                if hasattr(self, "closed_loop_toggle"):
                    self.closed_loop_toggle.toggled.connect(_sync_max_visibility)
            except Exception:
                pass

            return w
        
        # Helper: clear grid rows below header
        def _clear_grid_rows(grid: QGridLayout):
            # Remove all items below header row (row 0) safely
            for r in reversed(range(1, grid.rowCount())):
                for c in range(grid.columnCount()):
                    item = grid.itemAtPosition(r, c)
                    if not item:
                        continue
                    w = item.widget()
                    if w is not None:
                        grid.removeWidget(w)
                        w.deleteLater()

    # Build a dropdown cell to pick a hardware channel for a given row
        def _available_page10_channels() -> list[int]:
            # Try to use the channels assigned on Page 5; fall back to 0..7
            channels: list[int] = []
            try:
                for btn in getattr(self, "btn_chan_connection", []):
                    t = btn.text()
                    if t and t.startswith("Channel"):
                        try:
                            channels.append(int(t.split(" ")[-1]))
                        except Exception:
                            pass
                channels = sorted(set(channels))
            except Exception:
                channels = []
            if not channels:
                channels = list(range(8))
            return channels

        def _make_channel_cell(ch_idx: int) -> Optional[PyDropDownButton]:
            # Only show when personalization is enabled
            if not self.page10_personalize_channels_cb.isChecked():
                return None
            chan_nums = _available_page10_channels()
            actions = [QAction(f"Channel {n}") for n in chan_nums]
            valid = {f"Channel {n}" for n in chan_nums}

            # Default label: previous UI label, else persisted mapping, else sequential
            persisted = self.page10_row_channel_map.get(ch_idx, ch_idx)
            default_text = self._page10_prev_channel_text.get(ch_idx, f"Channel {persisted}")
            if default_text not in valid:
                fallback = f"Channel {persisted}"
                default_text = fallback if fallback in valid else (next(iter(valid)) if valid else "Select Channel")

            btn = SetupMainWindow.create_std_dropdown_btn(self.themes, actions, default_text)
            btn.setMinimumHeight(LINE_HEIGHT)
            self.page10_channel_sel[ch_idx] = btn
            # Open channel menu on click
            btn.clicked.connect(btn.showMenu)

            def _apply_channel_selection(new_label: str, row=ch_idx):
                try:
                    self._page10_prev_channel_text[row] = new_label
                    if new_label.startswith("Channel"):
                        new_ch = int(new_label.split(" ")[-1])
                        # Persist mapping regardless of checkbox state
                        self.page10_row_channel_map[row] = new_ch
                        # Optionally refresh confirmation now
                        try:
                            _apply_page10_to_confirmation()
                        except Exception:
                            pass
                except Exception:
                    pass

            for act in btn._menu.actions():
                act.triggered.connect(lambda _, a=act, b=btn: b.on_action_triggered(a))
                act.triggered.connect(lambda _, a=act: _apply_channel_selection(a.text()))

            # Apply default to ensure mapping is persisted on first build
            _apply_channel_selection(default_text)
            return btn
        
        # Build rows around the image based on electrode count
        def _rebuild_page10_rows():

             # --- SNAPSHOT CURRENT TARGET TEXTS BEFORE CLEARING ---
            try:
                if hasattr(self, "page10_target_sel"):
                    for r, btn in getattr(self, "page10_target_sel", {}).items():
                        if btn:
                            self._page10_prev_target_text[r] = btn.text()
            except Exception:
                pass
            
            # Preserve previous selections (targets and channels) before clearing
            try:
                self._page10_prev_target_text = {
                    idx: btn.text() for idx, btn in self.page10_target_sel.items() if btn
                }
            except Exception:
                self._page10_prev_target_text = {}
            # Preserve previous channel texts before clearing
            try:
                self._page10_prev_channel_text = {idx: btn.text() for idx, btn in self.page10_channel_sel.items() if btn}
            except Exception:
                self._page10_prev_channel_text = {}
            
             # Preserve previous current texts and update the persisted map
            try:
                self._page10_prev_current_text = {
                    idx: _extract_text(w) for idx, w in self.page10_curr_opt.items() if w
                }
                # Write-through to the persistent store
                for idx, val in self._page10_prev_current_text.items():
                    if val is not None and val != "":
                        self.page10_row_current_map[idx] = val
            except Exception:
                self._page10_prev_current_text = {}

            # Dispose any previous per-row widgets we reference and clear maps
            for btn in list(self.page10_target_sel.values()):
                try:
                    btn.deleteLater()
                except Exception:
                    pass
            for edit in list(self.page10_curr_opt.values()):
                try:
                    edit.deleteLater()
                except Exception:
                    pass
            for btn in list(self.page10_channel_sel.values()):
                try:
                    btn.deleteLater()
                except Exception:
                    pass
            for btn in list(self.page10_gait_sel.values()):
                try:
                    btn.deleteLater()
                except Exception:
                    pass
            self.page10_gait_sel.clear()
            self.page10_target_sel.clear()
            self.page10_curr_opt.clear()
            self.page10_channel_sel.clear()

            _clear_grid_rows(self.page10_left_grid)
            _clear_grid_rows(self.page10_right_grid)

            # Show/hide Channel headers depending on toggle
            personalize_channels = self.page10_personalize_channels_cb.isChecked()
            personalize_gait = self.page10_personalize_gait_cb.isChecked()

            # Header visibility (fixed positions)
            self.page10_left_hdr_channel.setVisible(personalize_channels)
            self.page10_right_hdr_channel.setVisible(personalize_channels)
            self.page10_left_hdr_gait_phases.setVisible(personalize_gait)
            self.page10_right_hdr_gait_phases.setVisible(personalize_gait)

            # Determine L/R split
            n = _page10_electrode_row_count()
            if n == 1:
                left_rows, right_rows = (1, 0)
            elif n == 6:
                left_rows, right_rows = (3, 3)
            elif n == 7:
                left_rows, right_rows = (4, 3)
            elif n == 8:
                left_rows, right_rows = (4, 4)
            elif n == 3:
                left_rows, right_rows = (2, 1)
            elif n == 4:
                left_rows, right_rows = (2, 2)
            else:
                left_rows, right_rows = (0, 0)

            # Helper: get selected target text for a row (fallback to previous)
            def _target_text_for_row(row_idx: int) -> str:
                btn = self.page10_target_sel.get(row_idx)
                t = btn.text() if btn else None
                if t and len(t.strip()) > 0:
                    return t
                return (self._page10_prev_target_text or {}).get(row_idx, "Not to be used")

            # Phase short codes for compact text (order we display)
            all_phases = [
                Phase.LOADING_RESPONSE, Phase.MID_STANCE, Phase.PRE_SWING,
                Phase.MID_SWING, Phase.TERMINAL_SWING, Phase.STANCE, Phase.SWING
            ]
            phase_short = {
                Phase.LOADING_RESPONSE: "LR",
                Phase.MID_STANCE: "MST",
                Phase.PRE_SWING: "PS",
                Phase.MID_SWING: "MSW",
                Phase.TERMINAL_SWING: "TSW",
                Phase.STANCE: "ST",
                Phase.SWING: "SW",
            }

            # Helper: selected target text for a row
            def _target_text_for_row(row_idx: int) -> str:
                btn = self.page10_target_sel.get(row_idx)
                t = btn.text() if btn else None
                return t if t and t.strip() else (self._page10_prev_target_text or {}).get(row_idx, "Not to be used")

            # 2) FIX: Gait cell shows ALL selected phases; styled and fixed-size; no factory dropdown used
            def _make_gait_cell(row_idx: int) -> QWidget | None:
                display_tgt = _target_text_for_row(row_idx)
                if not display_tgt or display_tgt == "Not to be used":
                    return None

                # Map GUI label to internal key
                tgt_key = self.page10_target_key_map.get(display_tgt, display_tgt)

                # Ensure defaults for new targets
                if tgt_key not in self.page10_gait_model_map:
                    defaults = _default_gait_model_map()
                    self.page10_gait_model_map[tgt_key] = set(defaults.get(tgt_key, set()))

                btn = QToolButton()
                btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                btn.setFixedHeight(LINE_HEIGHT)
                btn.setFixedWidth(200)
                # Match themed style of other cells
                btn.setStyleSheet(f"""
                    QToolButton {{
                        background-color: {self.themes['app_color']['dark_one']};
                        color: {self.themes['app_color']['text_foreground']};
                        border-radius: 8px;
                        padding: 4px 8px;
                        font-size: 12pt;
                    }}
                    QToolButton::menu-indicator {{ image: none; width: 0px; height: 0px; }}
                """)

                menu = QMenu(btn)

                # Update button text to show selection summary
                def _update_btn_text():
                    sel_set = self.page10_gait_model_map.get(tgt_key, set())
                    # Show ALL selected (compact codes), keep full names as tooltip
                    codes = [phase_short[p] for p in all_phases if p in sel_set]
                    full = [p.name.replace("_", " ").title() for p in all_phases if p in sel_set]
                    btn.setText(", ".join(codes) if codes else "None")
                    btn.setToolTip(", ".join(full) if full else "None")

                # Build actions
                for p in all_phases:
                    act = QAction(p.name.replace("_", " ").title(), menu)
                    act.setCheckable(True)
                    act.setChecked(p in self.page10_gait_model_map[tgt_key])

                    def _toggle(checked: bool, phase=p, target=tgt_key):
                        if checked:
                            self.page10_gait_model_map.setdefault(target, set()).add(phase)
                        else:
                            self.page10_gait_model_map.setdefault(target, set()).discard(phase)
                        _update_btn_text()

                    act.toggled.connect(_toggle)
                    menu.addAction(act)

                btn.setMenu(menu)
                # Open the menu on click (same UX as other dropdowns)
                btn.clicked.connect(btn.showMenu)

                _update_btn_text()
                self.page10_gait_sel[row_idx] = btn
                return btn

            # Left side rows
            for i in range(left_rows):
                row = i
                # fixed columns
                if personalize_gait:
                    gait_cell = _make_gait_cell(row)
                    if gait_cell is not None:
                        self.page10_left_grid.addWidget(gait_cell, i + 1, 0)

                # Restore target cell text from snapshot
                t_btn = _make_target_cell(row)
                if t_btn is not None:
                    restore_txt = (self._page10_prev_target_text or {}).get(row)
                    if restore_txt:
                        t_btn.setText(restore_txt)
                    self.page10_left_grid.addWidget(t_btn, i + 1, 1)

                self.page10_left_grid.addWidget(_make_current_cell(row), i + 1, 2)
                # Electrode label logic
                if left_rows == 1:
                    label = "M1"
                elif left_rows == 3:
                    label = f"L{i+1}"
                elif left_rows == 4:
                    label = ["L1", "L2", "L3", "M1"][i]
                else:
                    label = ""
                self.page10_left_grid.addWidget(QLabel(label), i + 1, 3, Qt.AlignmentFlag.AlignCenter)
                if personalize_channels:
                    ch_cell = _make_channel_cell(row)
                    if ch_cell is not None:
                        self.page10_left_grid.addWidget(ch_cell, i + 1, 4)

            # Right grid: Electrode | [Channel] | Current | Target
            for i in range(right_rows):
                row = left_rows + i
                if personalize_channels:
                    ch_cell = _make_channel_cell(row)
                    if ch_cell is not None:
                        self.page10_right_grid.addWidget(ch_cell, i + 1, 0)
                self.page10_right_grid.addWidget(QLabel(f"R{i+1}"), i + 1, 1, Qt.AlignmentFlag.AlignCenter)
                self.page10_right_grid.addWidget(_make_current_cell(row), i + 1, 2)

                # Restore target cell text from snapshot
                t_btn = _make_target_cell(row)
                if t_btn is not None:
                    restore_txt = (self._page10_prev_target_text or {}).get(row)
                    if restore_txt:
                        t_btn.setText(restore_txt)
                    self.page10_right_grid.addWidget(t_btn, i + 1, 3)

                if personalize_gait:
                    gait_cell = _make_gait_cell(row)
                    if gait_cell is not None:
                        self.page10_right_grid.addWidget(gait_cell, i + 1, 4)
            
            # After creating target cells, hook their menus so selecting a target refreshes gait cells
            def _hook_target_menu_for_row(row_idx: int):
                btn = self.page10_target_sel.get(row_idx)
                if not btn:
                    return
                # Get the menu from the target dropdown
                try:
                    menu = btn.menu()
                except Exception:
                    menu = getattr(btn, "_menu", None)
                if not menu:
                    return

                # Defer UI rebuild until after the menu fully closes to avoid destroying the button mid-trigger
                def _apply_target_and_refresh(chosen: str, r: int):
                    self._page10_prev_target_text[r] = chosen
                    if self.page10_personalize_gait_cb.isChecked():
                        tgt_key = self.page10_target_key_map.get(chosen, chosen)
                        if tgt_key not in self.page10_gait_model_map:
                            defaults = _default_gait_model_map()
                            self.page10_gait_model_map[tgt_key] = set(defaults.get(tgt_key, set()))
                        _rebuild_page10_rows()
                def _on_choose(action: QAction, r=row_idx):
                    chosen = action.text()
                    QTimer.singleShot(0, lambda c=chosen, rr=r: _apply_target_and_refresh(c, rr))

                # Connect on each rebuild (fresh buttons)
                try:
                    menu.triggered.connect(_on_choose)
                except Exception:
                    pass

            # Hook only when personalize gait is ON to avoid unintended rebuilds
            if personalize_gait:
                total_rows = left_rows + right_rows
                for r in range(total_rows):
                    _hook_target_menu_for_row(r)

            # 2) Restore previous target selections per row if still valid
            try:
                for ch, prev in self._page10_prev_target_text.items():
                    btn = self.page10_target_sel.get(ch)
                    if not btn or not prev:
                        continue
                    # If the previous selection exists, trigger it
                    for act in getattr(btn, "_menu", QListWidget()).actions():
                        if act.text() == prev:
                            btn.on_action_triggered(act)
                            break
            except Exception:
                pass

            # 3) Now enforce uniqueness and render labels
            try:
                _page10_refresh_target_options()
                _page10_render_labels()
            except Exception:
                pass

            # Update confirmation with current mapping
            QTimer.singleShot(0, _apply_page10_to_confirmation)

        # Rebuild when toggling personalization
        self.page10_personalize_channels_cb.toggled.connect(lambda _: _rebuild_page10_rows())


        # Initial build
        QTimer.singleShot(0, _rebuild_page10_rows)
        # Also render labels once Page 10 is ready
        QTimer.singleShot(0, _page10_render_all_labels_for_arrangement)

        # After adding other start_btn connections:
        # Ensure confirmation page shows Page 10 values when user clicks "Confirm and Start"
        self.start_btn.clicked.connect(lambda: QTimer.singleShot(0, _apply_page10_to_confirmation))

        # Enforce unique targets across channels on Page 10
        def _set_actions_for_channel(ch_idx: int, labels: list[str]):
            btn = self.page10_target_sel[ch_idx]
            prev = btn.text()
            # Fallback: never leave the menu empty
            if not labels:
                labels = ["Not to be used"]
            btn.set_actions([QAction(lbl) for lbl in labels])

            # Wire actions to select and then refresh all dropdowns
            for act in btn._menu.actions():
                # Ensure the button updates its label/state
                act.triggered.connect(lambda _, a=act, b=btn: b.on_action_triggered(a))
                # Recompute menus across all channels after any selection
                act.triggered.connect(lambda _: _page10_refresh_target_options())
                # render labels of selected electrode on the back image
                act.triggered.connect(lambda _: _page10_render_labels())


            # Keep previous selection if still allowed; otherwise default to "Not to be used"
            if prev in labels:
                for act in btn._menu.actions():
                    if act.text() == prev:
                        btn.on_action_triggered(act)
                        break
            else:
                for act in btn._menu.actions():
                    if act.text() == "Not to be used":
                        btn.on_action_triggered(act)
                        break
        # Helper: check if a Qt object is still valid (not deleted)
        def _is_valid(obj) -> bool:
            try:
                import shiboken6
                return shiboken6.isValid(obj)
            except Exception:
                return obj is not None

        def _page10_refresh_target_options():
            # Collect targets already used by other channels (ignore "Not to be used")
            used = set()
            for ch, btn in self.page10_target_sel.items():
                if not _is_valid(btn):
                    continue
                t = btn.text()
                if t in self.page10_target_labels:
                    used.add(t)

            for ch, btn in self.page10_target_sel.items():
                if not _is_valid(btn):
                    continue
                current = btn.text()
                # Allow current selection even if used (to keep it selectable for this channel)
                available = ["Not to be used"] + [lbl for lbl in self.page10_target_labels if lbl not in used or lbl == current]
                _set_actions_for_channel(ch, available)
        
        # Render numeric labels on the Page 10 image for channels with selected targets
        def _page10_render_labels():
            if not hasattr(self, "back_image_10"):
                return
            arrangement = self.dropdown_btn_placement.text() if hasattr(self, "dropdown_btn_placement") else "No Electrodes"

            # Reset modified_image.svg to the base image for this arrangement
            SetupMainWindow.load_back_image(arrangement, self.tasks_path, self.btn_chan_connection, self.back_image_10)

            # Determine how many electrodes the current arrangement has
            try:
                buttons = SetupMainWindow.get_placement_buttons(self.tasks_path, arrangement)
                n = len(buttons)
            except Exception:
                n = 0

            # Build label list by electrode index (only numeric part is rendered)
            if n == 1:
                labels = ["M1"]
            elif n == 6:
                labels = ["L1", "L2", "L3", "R1", "R2", "R3"]
            elif n == 7:
                labels = ["L1", "L2", "L3", "M1", "R1", "R2", "R3"]
                
            elif n == 8:
                # Default left-to-right ordering matching button indices 0..7
                # Use FES-specific muscle names when either:
                #  - the placement string explicitly contains "fes", or
                #  - the FES toggle is checked (preferred).
                is_fes_arrangement = False
                try:
                    if getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked():
                        is_fes_arrangement = True
                    else:
                        is_fes_arrangement = "fes" in (arrangement or "").lower() #Doesnt work idk why
                except Exception:
                    is_fes_arrangement = "fes" in (arrangement or "").lower()

               
                if is_fes_arrangement:
                    # EDIT THIS ARRAY TO MATCH YOUR FES MUSCLE NAMES / DESIRED ORDER
                    labels = ["BF_L", "VM_L", "GA_L", "TA_L", "BF_R", "VM_R", "GA_R", "TA_R"]
                    
                else:
                    labels = ["L1", "L2", "L3", "L4", "R1", "R2", "R3", "R4"]
                    
            else:
                labels = []

            # For each channel that has a target (not "Not to be used"), draw the number at its electrode index
            from modify_svg import change_number_to
            for ch, btn in sorted(self.page10_target_sel.items()):
                if not _is_valid(btn):
                    continue
                if ch < 0 or ch >= n:
                    continue
                if btn.text() == "Not to be used":
                    continue
                lbl = labels[ch] if ch < len(labels) else None
                if not lbl:
                    continue
                num = int(lbl[-1]) if lbl[-1].isdigit() else (ch + 1)
                try:
                    change_number_to(Functions.set_svg_image("modified_image.svg"), ch, num)
                except Exception:
                    pass

            # Reload updated image
            try:
                self.back_image_10.load(Functions.set_svg_image("modified_image.svg"))
                self.back_image_10.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
            except Exception:
                pass

        # Initialize Selected Task display if already chosen
        def _sync_task_and_image_on_page10():
            # Prefer the existing read-only field if present, else dropdown caption
            name = ""
            if hasattr(self, "lineEdit_selected_task") and self.lineEdit_selected_task and self.lineEdit_selected_task.text():
                name = self.lineEdit_selected_task.text()
            elif hasattr(self, "dropdown_btn_task") and hasattr(self.dropdown_btn_task, "text"):
                name = self.dropdown_btn_task.text()
            if name:
                self.lineEdit_selected_task_10.setText(name)
            # Try to load image for the current placement selection if available
            try:
                if hasattr(self, "btn_chan_connection"):
                    # Use dropdown_btn_placement caption if exists; otherwise do nothing
                    placement = ""
                    if hasattr(self, "dropdown_btn_placement") and hasattr(self.dropdown_btn_placement, "text"):
                        placement = self.dropdown_btn_placement.text()
                    if placement:
                        # Reuse helper to load SVG into Page 10 image
                        SetupMainWindow.load_back_image(placement, self.tasks_path, self.btn_chan_connection, self.back_image_10)
            except Exception:
                pass
            """ # Reflect selected task name
            try:
                self.lineEdit_selected_task_10.setText(self.lineEdit_selected_task.text())
            except Exception:
                pass """
            # Reset image and render labels for current placement
            """ try:
                _page10_render_labels()
            except Exception:
                pass """
        QTimer.singleShot(0, _sync_task_and_image_on_page10)

        # Sync initial Page 10 targets from Page 5 mapping (if present)
        def _sync_page10_targets_from_page5():
            # Map Page 5 target dropdowns to their keys
            if self.fes_toggle.isChecked() and not self.tscs_toggle.isChecked() :
                    page5_targets = {
                    "TA_left": getattr(self, "dropdown_btn_target_1", None),
                    "TA_right": getattr(self, "dropdown_btn_target_2", None),
                    "GA_left": getattr(self, "dropdown_btn_target_3", None),
                    "GA_right": getattr(self, "dropdown_btn_target_4", None),
                    "VM_left": getattr(self, "dropdown_btn_target_5", None),
                    "VM_right": getattr(self, "dropdown_btn_target_6", None),
                    "BF_left": getattr(self, "dropdown_btn_target_7", None),
                    "BF_right": getattr(self, "dropdown_btn_target_8", None),
                }
            elif self.tscs_toggle.isChecked() and not self.fes_toggle.isChecked():   
                page5_targets = {
                    "full_leg_left": getattr(self, "dropdown_btn_target_1", None),
                    "full_leg_right": getattr(self, "dropdown_btn_target_2", None),
                    "proximal_left": getattr(self, "dropdown_btn_target_3", None),
                    "proximal_right": getattr(self, "dropdown_btn_target_4", None),
                    "distal_left": getattr(self, "dropdown_btn_target_5", None),
                    "distal_right": getattr(self, "dropdown_btn_target_6", None),
                    "continuous": getattr(self, "dropdown_btn_target_7", None),
                }
                
            else: 
                
                pass
            
            # Invert label map: key -> label
            inv_label = {v: k for k, v in self.page10_target_key_map.items()}
            for key, btn in page5_targets.items():
                if btn is None:
                    continue
                txt = btn.text()
                if not txt or "Channel" not in txt:
                    continue
                try:
                    ch = int(txt.split(" ")[-1])
                except Exception:
                    continue
                if ch in self.page10_target_sel and key in inv_label:
                    label = inv_label[key]
                    target_btn = self.page10_target_sel[ch]
                    # Trigger the action so the button text and state update consistently
                    for act in target_btn._menu.actions():
                        if act.text() == label:
                            target_btn.on_action_triggered(act)
                            break
            try:
                _page10_refresh_target_options()
                _page10_render_labels()
            except Exception:
                pass
            # After syncing, enforce uniqueness
            QTimer.singleShot(0, _page10_refresh_target_options)
            #QTimer.singleShot(0, _page10_render_labels)

        QTimer.singleShot(0, _sync_page10_targets_from_page5)

        # When task/placement changes, reset image and render labels
        if hasattr(self, "dropdown_btn_placement"):
            for act in self.dropdown_btn_placement.menu().actions():
                act.triggered.connect(lambda _: QTimer.singleShot(0, _rebuild_page10_rows))
                act.triggered.connect(lambda _: QTimer.singleShot(0, _page10_render_all_labels_for_arrangement))

        # Add Page 10 to the stacked widget
        self.ui.load_pages.pages.addWidget(self.ui.load_pages.page_10)

        # --- Page 10: Testing box (manual quick test on channel 0) ---
        # UI
       
        self.page10_test_frame = QFrame(self.ui.load_pages.page_10)
        self.page10_test_frame.setObjectName("page10_test_frame")
        self.page10_test_frame.setStyleSheet(
            f"QFrame#page10_test_frame {{border: 2px solid {self.themes['app_color']['bg_two']}; border-radius: 4px;}}"
        )
        self.page10_test_layout = QVBoxLayout(self.page10_test_frame)
        self.page10_test_layout.setContentsMargins(10, 8, 10, 8)
        self.page10_test_layout.setSpacing(8)

        test_title = QLabel("Testing")
        test_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        test_title.setStyleSheet("font-size: 14pt; font-weight: 500;")

        # Controls row: left = checkboxes, right = duration input
        controls_row = QWidget(self.page10_test_frame)
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        # LEFT: two checkboxes
        left_controls = QWidget(controls_row)
        left_controls_layout = QHBoxLayout(left_controls)
        left_controls_layout.setContentsMargins(0, 0, 0, 0)
        left_controls_layout.setSpacing(6)

        self.test_functional_cb = QCheckBox("Test Functional Stimulation", left_controls)
        # Replaced Stimulate Phase with a Stimulate FES Step toggle + related widgets
        self.stimulate_fes_step_cb = QCheckBox("Stimulate FES Step", left_controls)
       # speed dropdown (simple list, add more later)
        self.page10_fes_speed_dd = SetupMainWindow.create_std_dropdown_btn(self.themes, [QAction("0.8 km/h")], "0.8 km/h")
        self.page10_fes_speed_dd.setMinimumHeight(LINE_HEIGHT)
        self.page10_fes_speed_dd.setVisible(False)
        # number of steps input
        self.page10_fes_steps = SetupMainWindow.create_std_line_edit(self.themes, text="1", place_holder_text="Steps")
        self.page10_fes_steps.setMaximumWidth(80)
        self.page10_fes_steps.setValidator(QIntValidator(1, 10000, self))
        self.page10_fes_steps.setVisible(False)
        # side selector (Left / Right / Both)
        side_actions = [QAction("Left"), QAction("Right"), QAction("Both")]
        self.page10_fes_side_dd = SetupMainWindow.create_std_dropdown_btn(self.themes, side_actions, "Left")
        self.page10_fes_side_dd.setMinimumHeight(LINE_HEIGHT)
        # Ensure menu opens and actions update the button text reliably
        try:
            # open menu on click
            self.page10_fes_side_dd.clicked.connect(self.page10_fes_side_dd.showMenu)
        except Exception:
            pass
        try:
            # wire actions to the button handler so selecting an action updates the caption
            menu = getattr(self.page10_fes_side_dd, "_menu", None) or getattr(self.page10_fes_side_dd, "menu", lambda: None)()
            actions = menu.actions() if menu else []
            for act in actions:
                act.triggered.connect(lambda _, a=act: self.page10_fes_side_dd.on_action_triggered(a))
            # set a sensible default (Both)
            for act in actions:
                if act.text().strip().lower() == "both":
                    try:
                        self.page10_fes_side_dd.on_action_triggered(act)
                    except Exception:
                        pass
                    break
        except Exception:
            pass
        self.page10_fes_side_dd.setVisible(False)

        # Add to left controls layout (toggle first, other widgets shown when checked)
        left_controls_layout.addWidget(self.test_functional_cb)
        left_controls_layout.addWidget(self.stimulate_fes_step_cb)
        left_controls_layout.addWidget(self.page10_fes_speed_dd)
        left_controls_layout.addWidget(self.page10_fes_steps)
        left_controls_layout.addWidget(self.page10_fes_side_dd)
        # Small spacer
        left_controls_layout.addStretch(1)

        # keep existing stretch + right-side duration label / edit (added below)
        # RIGHT: duration input (seconds)
        right_controls = QWidget(controls_row)
        right_controls_layout = QHBoxLayout(right_controls)
        right_controls_layout.setContentsMargins(0, 0, 0, 0)
        right_controls_layout.setSpacing(6)
        duration_label = QLabel("Duration (s):")
        duration_label.setStyleSheet("font-size: 11pt;")
        # Use helper to create consistent styled line edit
        self.page10_test_duration = SetupMainWindow.create_std_line_edit(self.themes, text="1.0", place_holder_text="s")
        self.page10_test_duration.setMaximumWidth(100)
        # Allow sub-second precision (up to 6 decimals)
        v = QDoubleValidator(0.0001, 3600.0, 6)
        try:
            # prefer standard notation
            v.setNotation(QDoubleValidator.Notation.StandardNotation)
        except Exception:
            try:
                v.setNotation(QDoubleValidator.StandardNotation)
            except Exception:
                pass
        self.page10_test_duration.setValidator(v)
        # Ensure the duration field is editable and focusable
        try:
            self.page10_test_duration.setReadOnly(False)
            self.page10_test_duration.setEnabled(True)
            self.page10_test_duration.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            # Make sure user clicks give focus (workaround for custom PyLineEdit)
            try:
                _orig_mouse = getattr(self.page10_test_duration, "mousePressEvent", None)
                def _duration_mouse(evt):
                    try:
                        self.page10_test_duration.setReadOnly(False)
                        self.page10_test_duration.setEnabled(True)
                        self.page10_test_duration.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                        self.page10_test_duration.setFocus()
                    except Exception:
                        pass
                    if callable(_orig_mouse):
                        try:
                            _orig_mouse(evt)
                        except Exception:
                            pass
                self.page10_test_duration.mousePressEvent = _duration_mouse  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            pass
        right_controls_layout.addStretch(1)
        right_controls_layout.addWidget(duration_label)
        right_controls_layout.addWidget(self.page10_test_duration)
        # Initially hide duration controls unless functional test is checked
        duration_label.setVisible(bool(getattr(self, "test_functional_cb", None) and self.test_functional_cb.isChecked()))
        self.page10_test_duration.setVisible(bool(getattr(self, "test_functional_cb", None) and self.test_functional_cb.isChecked()))

        # helper to parse duration text robustly (accept comma or dot decimals)
        def _parse_duration_text() -> float:
            try:
                txt = (self.page10_test_duration.text() or "").strip()
                if not txt:
                    return 1.0
                # accept comma as decimal separator
                txt = txt.replace(",", ".")
                return float(txt)
            except Exception:
                pass
                
        # Show/hide duration input when Test Functional Stimulation is toggled.
        def _on_test_functional_toggled(checked: bool):
            try:
                duration_label.setVisible(bool(checked))
                self.page10_test_duration.setVisible(bool(checked))
                # ensure edit is writable/focusable when shown
                if checked:
                    try:
                        self.page10_test_duration.setReadOnly(False)
                        self.page10_test_duration.setEnabled(True)
                        self.page10_test_duration.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                    except Exception:
                        pass
                # If turned off, cancel any pending auto-stop timer to avoid hidden auto-stop actions
                if not checked:
                    # guard the timer stop separately so errors are localised
                    try:
                        if hasattr(self, "_page10_test_auto_stop_timer") and self._page10_test_auto_stop_timer.isActive():
                            self._page10_test_auto_stop_timer.stop()
                    except Exception as e:
                        print(f"[DEBUG] failed stopping auto-stop timer: {e}")
                    # don't call timeout.disconnect() here (Qt warns if disconnecting untracked slots)
                    # reset test UI buttons
                    try:
                        self.page10_test_start_btn.setEnabled(True)
                        self.page10_test_stop_btn.setEnabled(False)
                    except Exception:
                        pass
            except Exception:
                pass
            
        # Connect the checkbox to the handler and apply initial state
        try:
            self.test_functional_cb.toggled.connect(_on_test_functional_toggled)
            # Apply initial visibility once
            QTimer.singleShot(0, lambda: _on_test_functional_toggled(self.test_functional_cb.isChecked()))
        except Exception:
            pass

        # Add left and right controls to main controls row
        controls_layout.addWidget(left_controls, 0, )
        controls_layout.addWidget(right_controls, 1, Qt.AlignmentFlag.AlignRight)

        # Row: Test Channel selector
        chan_row = QWidget(self.page10_test_frame)
        chan_row_layout = QHBoxLayout(chan_row)
        chan_row_layout.setContentsMargins(0, 0, 0, 0)
        chan_row_layout.setSpacing(8)
        chan_label = QLabel("Test Channel")
        chan_label.setStyleSheet("font-size: 12pt; font-weight: 500;")
        self.page10_test_channel_dd = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Select Channel")
        self.page10_test_channel_dd.setMinimumHeight(LINE_HEIGHT)
        self.page10_test_channel_dd.clicked.connect(self.page10_test_channel_dd.showMenu)
        chan_row_layout.addStretch(1)
        chan_row_layout.addWidget(chan_label)
        chan_row_layout.addWidget(self.page10_test_channel_dd, 1)
        chan_row_layout.addStretch(1)

        self.page10_test_btns = QWidget(self.page10_test_frame)
        self.page10_test_btns_layout = QHBoxLayout(self.page10_test_btns)
        self.page10_test_btns_layout.setContentsMargins(0, 0, 0, 0)
        self.page10_test_btns_layout.setSpacing(8)

        self.page10_test_set_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Set Params")
        self.page10_test_start_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Start Test")
        self.page10_test_stop_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Stop Test")
        self.page10_test_stop_btn.setEnabled(False)

        self.page10_test_btns_layout.addStretch(1)
        self.page10_test_btns_layout.addWidget(self.page10_test_set_btn)
        self.page10_test_btns_layout.addWidget(self.page10_test_start_btn)
        self.page10_test_btns_layout.addWidget(self.page10_test_stop_btn)
        self.page10_test_btns_layout.addStretch(1)

        # Assemble test frame
        self.page10_test_layout.addWidget(test_title)
        self.page10_test_layout.addWidget(controls_row)
        self.page10_test_layout.addWidget(chan_row)
        self.page10_test_layout.addWidget(self.page10_test_btns)

        # Place above the Start Experiment button if present, else append
        page10_layout = self.ui.load_pages.page_10.layout()
        if page10_layout is None:
            page10_layout = QVBoxLayout(self.ui.load_pages.page_10)
            page10_layout.setContentsMargins(0, 0, 0, 0)
            self.ui.load_pages.page_10.setLayout(page10_layout)
        try:
            idx = page10_layout.indexOf(getattr(self, "page10_start_btn_widget", None))
            if idx != -1:
                page10_layout.insertWidget(idx, self.page10_test_frame)
            else:
                page10_layout.addWidget(self.page10_test_frame)
        except Exception:
            page10_layout.addWidget(self.page10_test_frame)

        # --- Testing logic ---
        TEST_CH = 0  # hard-coded channel to test

        # Timer to auto-stop phase/channel stimulation
        self._page10_test_auto_stop_timer = QTimer(self)
        self._page10_test_auto_stop_timer.setSingleShot(True)
        
        # Track whether we've connected a slot to the timer so disconnect() is safe
        self._page10_test_auto_stop_timer_connected = False

        # Safe helpers to (dis)connect the auto-stop timer without triggering Qt warnings
        def _connect_auto_stop(slot):
            try:
                # If previously connected, disconnect first (only when we know we connected)
                if getattr(self, "_page10_test_auto_stop_timer_connected", False):
                    try:
                        self._page10_test_auto_stop_timer.timeout.disconnect()
                    except Exception:
                        pass
                    self._page10_test_auto_stop_timer_connected = False
                # Connect new slot
                self._page10_test_auto_stop_timer.timeout.connect(slot)
                self._page10_test_auto_stop_timer_connected = True
            except Exception:
                # keep robust if Qt complains
                self._page10_test_auto_stop_timer_connected = False

        def _disconnect_auto_stop():
            try:
                if getattr(self, "_page10_test_auto_stop_timer_connected", False):
                    try:
                        self._page10_test_auto_stop_timer.timeout.disconnect()
                    except Exception:
                        pass
                    self._page10_test_auto_stop_timer_connected = False
            except Exception:
                pass

        # --- Testing logic helpers ---
        def _current_test_channel() -> int:
            # Parse "Channel N" from dropdown; default to 0 if unset
            txt = getattr(self.page10_test_channel_dd, "text", lambda: "Channel 0")()
            try:
                return int(txt.split(" ")[-1])
            except Exception:
                return 0



        def _refresh_page10_test_channels():
            # Build channel list from the assigned/available channels on Page 5
            channels: list[int] = []
            try:
                # Collect unique channel numbers from buttons assigned in the image grid
                for btn in getattr(self, "btn_chan_connection", []):
                    t = btn.text()
                    if t and t.startswith("Channel"):
                        try:
                            channels.append(int(t.split(" ")[-1]))
                        except Exception:
                            pass
                channels = sorted(set(channels))
            except Exception:
                channels = []

            # Fallback: if nothing assigned yet, offer all 0..7
            if not channels:
                channels = list(range(8))

            # Preserve current selection if still valid
            prev = _current_test_channel()
            actions = [QAction(f"Channel {n}") for n in channels]
            self.page10_test_channel_dd.set_actions(actions)
            for act in self.page10_test_channel_dd._menu.actions():
                # Bind dropdown behavior
                act.triggered.connect(lambda _, a=act: self.page10_test_channel_dd.on_action_triggered(a))
            # Restore previous if possible; else pick first
            restore = next((a for a in self.page10_test_channel_dd._menu.actions() if a.text().endswith(f" {prev}")), None)
            self.page10_test_channel_dd.on_action_triggered(restore or self.page10_test_channel_dd._menu.actions()[0])

        # Call once at build time (default to channels)
        _refresh_page10_test_channels()

        # Toggle dropdown content when user toggles "Stimulate Phase"
        # Toggle UI when user toggles "Stimulate FES Step"
        def _on_stimulate_fes_step_toggled(checked: bool):
            """
            When Stimulate FES Step is enabled:
              - hide the small quick-test buttons and the channel dropdown
              - show and ENABLE FES controls (speed / steps / side)
              - uncheck & disable the Test Functional Stimulation toggle
              - hide the functional stimulation duration controls
              - update bottom Start/Confirm button text
            """
            try:
                # hide channel selector (we use sequence / step controls instead)
                try:
                    self.page10_test_channel_dd.setVisible(not checked)
                except Exception:
                    pass

                # Populate speed dropdown with 0.1 .. 0.8 km/h when enabling
                try:
                    speeds = [f"{x/10:.1f} km/h" for x in range(1, 9)]  # 0.1..0.8
                    actions = [QAction(s) for s in speeds]
                    # set_actions is used elsewhere for PyDropDownButton
                    try:
                        self.page10_fes_speed_dd.set_actions(actions)
                    except Exception:
                        # fallback: recreate menu if custom API differs
                        self.page10_fes_speed_dd.set_actions(actions)
                    # ensure a sensible default if none set
                    try:
                        if not self.page10_fes_speed_dd.text() or self.page10_fes_speed_dd.text() not in speeds:
                            self.page10_fes_speed_dd.setText(speeds[-1])
                    except Exception:
                        pass
                except Exception:
                    pass

                # Show/enable the FES controls and make them editable/focusable
                for w in (
                    getattr(self, "page10_fes_speed_dd", None),
                    getattr(self, "page10_fes_steps", None),
                    getattr(self, "page10_fes_side_dd", None),
                ):
                    try:
                        if w is None:
                            continue
                        w.setVisible(bool(checked))
                        w.setEnabled(bool(checked))
                        # If it's a line edit, ensure writeable and focusable
                        try:
                            if hasattr(w, "setReadOnly"):
                                w.setReadOnly(False)
                        except Exception:
                            pass
                        try:
                            w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                        except Exception:
                            pass
                        # If it's a dropdown ensure menu can open
                        try:
                            if hasattr(w, "clicked"):
                                w.clicked.connect(getattr(w, "showMenu", lambda: None))
                        except Exception:
                            pass
                    except Exception:
                        pass

                # Hide the small quick-test buttons when FES-step mode active
                try:
                    self.page10_test_set_btn.setVisible(not checked)
                    self.page10_test_start_btn.setVisible(not checked)
                    self.page10_test_stop_btn.setVisible(not checked)
                except Exception:
                    pass

                # Hide/disable the functional stimulation duration controls (they belong to Test Functional)
                try:
                    duration_label = locals().get("duration_label", None) or getattr(self, "page10_test_duration_label", None)
                    # If duration_label is a local var in scope above, hide it; else hide the widget directly
                    if duration_label is not None:
                        try:
                            duration_label.setVisible(not checked)
                        except Exception:
                            pass
                    # Always hide the duration edit
                    try:
                        self.page10_test_duration.setVisible(not checked)
                        self.page10_test_duration.setEnabled(not checked)
                    except Exception:
                        pass
                except Exception:
                    pass

                # Uncheck and disable the "Test Functional Stimulation" toggle while FES-step is active
                try:
                    if checked:
                        try:
                            self.test_functional_cb.blockSignals(True)
                        except Exception:
                            pass
                        try:
                            self.test_functional_cb.setChecked(False)
                        except Exception:
                            pass
                        try:
                            self.test_functional_cb.setEnabled(False)
                        except Exception:
                            pass
                        try:
                            self.test_functional_cb.blockSignals(False)
                        except Exception:
                            pass
                    else:
                        try:
                            self.test_functional_cb.setEnabled(True)
                        except Exception:
                            pass
                except Exception:
                    pass

                # Update bottom/confirm button labels for Page 10 to reflect FES-step flow
                try:
                    if checked:
                        if hasattr(self, "start_btn"):
                            self.start_btn.setText("Confirm and Start FES Step Test")
                        if hasattr(self, "confirm_btn"):
                            self.confirm_btn.setText("Confirm and Start FES Step Test")
                    else:
                        if hasattr(self, "start_btn"):
                            self.start_btn.setText("Confirm and Start")
                        if hasattr(self, "confirm_btn"):
                            self.confirm_btn.setText("Confirm")
                except Exception:
                    pass
            except Exception:
                pass

        try:
            self.stimulate_fes_step_cb.toggled.connect(_on_stimulate_fes_step_toggled)
        except Exception:
            pass

        # --- Use selected channel in parametrization ---
        def _build_params_from_page10() -> StimulatorParameters:
            ch = _current_test_channel()
            # Read current from the Channel N field (same as confirmation/save uses)
            page10_ch_curr: dict[int, str] = {}
            try:
                row_map = getattr(self, "page10_row_channel_map", {}) or {}
                for row_idx, editor in getattr(self, "page10_curr_opt", {}).items():
                    try:
                        ch_idx = int(row_map.get(row_idx, row_idx))
                        val = editor.text().strip()
                        if val and ch_idx not in page10_ch_curr:
                            page10_ch_curr[ch_idx] = val
                    except Exception:
                        continue
            except Exception:
                page10_ch_curr = {}

            # Build per-mode param dicts (prefer per-mode fields if present, fallback to base fields)
            def _read_field(mode_suffix: str, base_attr: str):
                attr = f"{base_attr}_{mode_suffix}" if hasattr(self, f"{base_attr}_{mode_suffix}") else base_attr
                v = getattr(self, attr, None)
                if v is None:
                    return None
                try:
                    return v.as_value()
                except Exception:
                    try:
                        return float(v.text()) if hasattr(v, "text") else None
                    except Exception:
                        return None

            tscs_on = bool(getattr(self, "tscs_toggle", None) and self.tscs_toggle.isChecked())
            fes_on = bool(getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked())

            tscs_params = None
            fes_params = None
            
            

            if tscs_on:
                tscs_params = {
                    "burst_frequency": _read_field("tscs", "lineEdit_burst_frequency") or _read_field("", "lineEdit_burst_frequency"),
                    "burst_duration": _read_field("tscs", "lineEdit_burst_duration") or _read_field("", "lineEdit_burst_duration"),
                    "interpulse_interval": _read_field("tscs", "lineEdit_interpulse_interval") or _read_field("", "lineEdit_interpulse_interval"),
                    "pulse_deadtime": _read_field("tscs", "lineEdit_pulse_deadtime") or _read_field("", "lineEdit_pulse_deadtime"),
                    "carrier_frequency": _read_field("tscs", "lineEdit_carrier_frequency") or _read_field("", "lineEdit_carrier_frequency"),
                }

            if fes_on:
                bd_fes = calculate_burst_duration_FES()
                bf_fes= return_frequency_FES()
                # FES commonly has no carrier; prefer explicit FES fields if present, else fallback; if absent use 0 for carrier.
                fes_params = {
                    "burst_frequency":bf_fes,
                    "burst_duration": bd_fes ,
                    "interpulse_interval": _read_field("fes", "lineEdit_interpulse_interval") or _read_field("", "lineEdit_interpulse_interval"),
                    "pulse_deadtime": _read_field("fes", "lineEdit_pulse_deadtime") or _read_field("", "lineEdit_pulse_deadtime"),
                    "carrier_frequency": _read_field("fes", "lineEdit_carrier_frequency") or 0,
                }

            # Create StimulatorParameters with per-mode dicts when toggles are active
            params = StimulatorParameters(
                burst_frequency=self.lineEdit_burst_frequency.as_value() if not fes_on else bf_fes,
                burst_duration=self.lineEdit_burst_duration.as_value() if not fes_on else bd_fes,
                pulse_deadtime=self.lineEdit_pulse_deadtime.as_value(),
                interpulse_interval=self.lineEdit_interpulse_interval.as_value(),
                carrier_frequency=self.lineEdit_carrier_frequency.as_value(),
                stim_currents=page10_ch_curr,
                tscs_params=tscs_params,
                fes_params=fes_params,
            )

            # Decide mode for this test channel by inspecting Page10 mapping first
            target_for_ch = None
            try:
                for row_idx, btn in getattr(self, "page10_target_sel", {}).items():
                    try:
                        if not btn or not hasattr(btn, "text"):
                            continue
                        lbl = btn.text().strip()
                        if not lbl or lbl == "Not to be used":
                            continue
                        hw = int(getattr(self, "page10_row_channel_map", {}).get(row_idx, row_idx))
                        if hw == ch:
                            # map label to internal key
                            target_for_ch = self.page10_target_key_map.get(lbl, lbl)
                            break
                    except Exception:
                        continue
            except Exception:
                target_for_ch = None

            # fallback: check Page5 dropdowns in order (1..8). map index->standard key lists
            if target_for_ch is None:
                try:
                    # choose candidate key list depending on active UI mode (hybrid uses both)
                    fes_keys = ["TA_left","TA_right","GA_left","GA_right","VM_left","VM_right","BF_left","BF_right", "GM_left", "GM_right", "RF_left", "RF_right"]
                    tscs_keys = ["full_leg_left","full_leg_right","proximal_left","proximal_right","distal_left","distal_right","continuous"]
                    for i in range(1, 9):
                        btn = getattr(self, f"dropdown_btn_target_{i}", None)
                        if not btn or not hasattr(btn, "text"):
                            continue
                        txt = btn.text().strip()
                        if not txt:
                            continue
                        # attempt to parse hardware number at end
                        import re
                        m = re.search(r"(\d+)\s*$", txt)
                        if m and int(m.group(1)) == ch:
                            # pick appropriate key by position and current mode preference
                            if fes_on and not tscs_on:
                                target_for_ch = fes_keys[i - 1]
                            elif tscs_on and not fes_on:
                                target_for_ch = tscs_keys[i - 1]
                            else:
                                # hybrid: prefer FES muscle names if they exist at that position
                                target_for_ch = fes_keys[i - 1] if i - 1 < len(fes_keys) else tscs_keys[i - 1]
                            break
                except Exception:
                    pass

            # if we found a target, set explicit channel mode for the test channel (so StimulatorParameters._get_derived_for_channel works)
            if target_for_ch is not None:
                try:
                    params.channel_mode_by_target[target_for_ch] = ("FES" if any(tok in target_for_ch for tok in ("TA", "GA", "VM", "BF", "GM" , "RF")) else "tSCS")
                    # Also register channel->mode
                    params.channel_mode_by_channel[int(ch)] = params.channel_mode_by_target[target_for_ch]
                except Exception:
                    pass
                
            # Debug: print resolved mapping for quick-test channel
            try:
                debug_mode = params.get_mode_for_channel(int(ch)) if hasattr(params, "get_mode_for_channel") else "unknown"
                print(f"DEBUG: _build_params_from_page10: test_channel={ch}, target_for_ch={target_for_ch}, inferred_mode={debug_mode}")
            except Exception:
                pass

            return params

        import math
        def _safe_int(val, fallback=0):
            try:
                if val is None:
                    return int(fallback)
                # math.isnan accepts numpy.nan too
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    return int(fallback)
                return int(val)
            except Exception:
                try:
                    return int(float(val))
                except Exception:
                    return int(fallback)
                    
        # Step 1: Only prime (no activation)
        def _prime_channel(port: Serial, ch: int, params: StimulatorParameters, mode: int = 0):
            from stimulator.ComPortFunc import SetSingleChanAllParam, SetSingleChanSingleParam
            from time import sleep
            StimulatorParameters.activate_hv(port, ch)
            sleep(0.02)
            try:
                SetSingleChanSingleParam(port, ch, 7, 0)  # mode=continuous
            except Exception:
                pass
            sleep(0.02)
            
            # Debug: print derived params that will be sent to hardware
            try:
                derived = params._get_derived_for_channel(ch)
                print(f"DEBUG prime channel={ch} derived={derived}")
            except Exception:
                print(f"DEBUG prime channel={ch} derived=UNAVAILABLE")

            # Use per-channel derived params (fallback to legacy attrs inside _get_derived_for_channel)
            # Use per-channel derived params (fallback to legacy attrs inside _get_derived_for_channel)
            derived = params._get_derived_for_channel(ch)

            ipw = _safe_int(derived.get("ideal_pulse_width", getattr(params, "ideal_pulse_width", 0)), fallback=0)
            pd  = _safe_int(derived.get("pulse_deadtime", getattr(params, "pulse_deadtime", 0)), fallback=0)
            ipi = _safe_int(derived.get("interpulse_interval", getattr(params, "interpulse_interval", 0)), fallback=0)
            bp  = _safe_int(derived.get("burst_period", getattr(params, "burst_period", 0)), fallback=0)
            ppb = _safe_int(derived.get("pulses_per_burst", getattr(params, "pulses_per_burst", 1)), fallback=1)
            SetSingleChanAllParam(
                 port, ch,
                 ipw,
                 pd,
                 ipi,
                 bp,
                 ppb,
                 int(getattr(params, "initial_current", 0)),
                 int(mode),
             )
            sleep(0.06)

        # Step 2: Activate and set amplitude (uses user-set current)
        def _activate_channel(port: Serial, ch: int, params: StimulatorParameters, mode: int = 0):
            from stimulator.ComPortFunc import SetSingleChanAllParam, SetSingleChanSingleParam
            from time import sleep
            StimulatorParameters.activate_output(port, ch)
            sleep(0.06)
            # page10 uses channel-keyed currents for quick test
            try:
                current_to_use = int(params.stim_currents.get(ch, params.initial_current))
            except Exception:
                current_to_use = int(getattr(params, "initial_current", 0))
            SetSingleChanSingleParam(port, ch, 6, current_to_use)  # amplitude
            sleep(0.02)
            # Use per-channel derived params
            # Use per-channel derived params (fallback to legacy attrs inside _get_derived_for_channel)
            derived = params._get_derived_for_channel(ch)
            # reuse _safe_int defined above (or re-define locally)
            ipw = _safe_int(derived.get("ideal_pulse_width", getattr(params, "ideal_pulse_width", 0)), fallback=0)
            pd  = _safe_int(derived.get("pulse_deadtime", getattr(params, "pulse_deadtime", 0)), fallback=0)
            ipi = _safe_int(derived.get("interpulse_interval", getattr(params, "interpulse_interval", 0)), fallback=0)
            bp  = _safe_int(derived.get("burst_period", getattr(params, "burst_period", 0)), fallback=0)
            ppb = _safe_int(derived.get("pulses_per_burst", getattr(params, "pulses_per_burst", 1)), fallback=1)
            SetSingleChanAllParam(
                 port, ch,
                 ipw,
                 pd,
                 ipi,
                 bp,
                 ppb,
                 int(current_to_use),
                 int(mode),
             )
            sleep(0.06)

        def _page10_test_set():
            if not hasattr(self, "serial_port") or self.serial_port is None:
                QMessageBox.warning(self, "Not Connected", "Please connect to the stimulator first on Page 3.")
                return
            try:
                ch = _current_test_channel()
                params = _build_params_from_page10()
                if hasattr(params, "is_valid") and not params.is_valid():
                    QMessageBox.critical(self, "Invalid Parameters", "Stimulation parameters are invalid.")
                    return
                _prime_channel(self.serial_port, ch, params)
                self.page10_test_start_btn.setEnabled(True)
                self.page10_test_stop_btn.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Test Error", f"Failed to SET on channel {ch}:\n{e}")

        def _page10_test_start():
            if not hasattr(self, "serial_port") or self.serial_port is None:
                QMessageBox.warning(self, "Not Connected", "Please connect to the stimulator first on Page 3.")
                return
            try:
                params = _build_params_from_page10()                
                # Channel mode: single channel activation
                ch = _current_test_channel()
                _activate_channel(self.serial_port, ch, params)
                # schedule single-channel auto-stop if requested
                if self.test_functional_cb.isChecked():
                    try:
                        dur = float(self.page10_test_duration.text().strip())
                    except Exception:
                        dur = 1.0
                    try:
                        self._page10_test_auto_stop_timer.stop()
                    except Exception:
                        pass
                    _connect_auto_stop(lambda ch=ch: StimulatorParameters.deactivate_output(self.serial_port, ch))
                    self._page10_test_auto_stop_timer.start(int(dur * 1000))


                self.page10_test_start_btn.setEnabled(False)
                self.page10_test_stop_btn.setEnabled(True)
            except Exception as e:
                QMessageBox.critical(self, "Test Error", f"Failed to start test:\n{e}")


                
        def _page10_test_stop():
            if not hasattr(self, "serial_port") or self.serial_port is None:
                return
            # cancel auto-stop timer
            try:
                if self._page10_test_auto_stop_timer.isActive():
                    self._page10_test_auto_stop_timer.stop()
            except Exception:
                pass

            # If phase mode, deactivate all mapped channels for selected phase
            
            ch = _current_test_channel()
            try:
                StimulatorParameters.deactivate_output(self.serial_port, ch)
            except Exception:
                pass
            finally:
                # ensure we cancel any auto-stop connection/timer
                _disconnect_auto_stop()
                self.page10_test_start_btn.setEnabled(True)
                self.page10_test_stop_btn.setEnabled(False)
                    
        try:
            self.page10_test_set_btn.clicked.connect(_page10_test_set)
            self.page10_test_start_btn.clicked.connect(_page10_test_start)
            self.page10_test_stop_btn.clicked.connect(_page10_test_stop)
        except Exception:
            pass



        # --- Move Start Experiment button from Page 1 to Page 10 ---
        # Detach from Page 1 if it was added there
        try:
            if hasattr(self.ui.load_pages, "start_layout"):
                if self.ui.load_pages.start_layout.indexOf(self.start_btn) != -1:
                    self.ui.load_pages.start_layout.removeWidget(self.start_btn)
            # Ensure it's parentless before re-adding
            self.start_btn.setParent(None)
        except Exception:
            pass

        # Ensure Page 10 has a main layout
        page10_layout = self.ui.load_pages.page_10.layout()
        if page10_layout is None:
            page10_layout = QVBoxLayout(self.ui.load_pages.page_10)
            page10_layout.setContentsMargins(0, 0, 0, 0)
            self.ui.load_pages.page_10.setLayout(page10_layout)

        # Footer widget on Page 10 to host the Start button
        self.page10_start_btn_widget = QWidget(self.ui.load_pages.page_10)
        self.page10_start_btn_widget.setObjectName("page10_start_btn_widget")
        self.page10_start_btn_widget.setMaximumHeight(80)
        self.page10_start_btn_layout = QHBoxLayout(self.page10_start_btn_widget)
        self.page10_start_btn_layout.setContentsMargins(0, 0, 0, 0)
        self.page10_start_btn_layout.setSpacing(0)
        
        # Make the Start button expand horizontally to fill the left column
        self.start_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.page10_start_btn_layout.addWidget(self.start_btn, 1)

        #--- Page 10: Stop Experiment button (same functionality as Page 6 stop) ---
        self.page10_stop_btn_widget = QWidget(self.ui.load_pages.page_10)
        self.page10_stop_btn_widget.setObjectName("page10_stop_btn_widget")
        self.page10_stop_btn_widget.setMaximumHeight(80)

        self.page10_stop_btn_layout = QHBoxLayout(self.page10_stop_btn_widget)
        self.page10_stop_btn_layout.setContentsMargins(0, 0, 0, 0)
        self.page10_stop_btn_layout.setSpacing(0)

        self.page10_stop_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Stop")
        self.page10_stop_btn.setToolTip("Stop the current experiment")
        # Same functionality as the main Stop button
        self.page10_stop_btn.clicked.connect(self.stop_clicked)

        # Make the Stop button expand horizontally to match Start
        self.page10_stop_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.page10_stop_btn_layout.addWidget(self.page10_stop_btn, 1)

        # --- Page 10 footer row: [ Start/Stop ]  |  [ Status & Log ] ---
        self.page10_footer_row = QWidget(self.ui.load_pages.page_10)
        self.page10_footer_row_layout = QHBoxLayout(self.page10_footer_row)
        self.page10_footer_row_layout.setContentsMargins(0, 0, 0, 0)
        self.page10_footer_row_layout.setSpacing(8)

        # Left column: existing Start/Stop footers stacked vertically
        left_col = QWidget(self.page10_footer_row)
        left_col_layout = QVBoxLayout(left_col)
        left_col_layout.setContentsMargins(0, 0, 0, 0)
        left_col_layout.setSpacing(8)
        left_col_layout.addWidget(self.page10_start_btn_widget)
        left_col_layout.addWidget(self.page10_stop_btn_widget)
        
        # --- NEW: Page 10 Pause button widget (inserted between Start and Stop) ---
        self.page10_pause_btn_widget = QWidget(self.ui.load_pages.page_10)
        self.page10_pause_btn_widget.setObjectName("page10_pause_btn_widget")
        self.page10_pause_btn_widget.setMaximumHeight(80)
        self.page10_pause_btn_layout = QHBoxLayout(self.page10_pause_btn_widget)
        self.page10_pause_btn_layout.setContentsMargins(0, 0, 0, 0)
        self.page10_pause_btn_layout.setSpacing(0)

        self.page10_pause_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Pause")
        self.page10_pause_btn.setToolTip("Pause the experiment")
        self.page10_pause_btn.setEnabled(False)  # only enabled while running
        # Delegate handling to MainWindow slot
        self.page10_pause_btn.clicked.connect(self.pause_clicked)

        self.page10_pause_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.page10_pause_btn_layout.addWidget(self.page10_pause_btn, 1)

        # Insert Pause between Start and Stop
        try:
            idx = left_col_layout.indexOf(self.page10_stop_btn_widget)
            if idx != -1:
                left_col_layout.insertWidget(idx, self.page10_pause_btn_widget)
            else:
                left_col_layout.addWidget(self.page10_pause_btn_widget)
        except Exception:
            left_col_layout.addWidget(self.page10_pause_btn_widget)

        # Right column: Status & Log box
        self.page10_status_log_frame = QFrame(self.page10_footer_row)
        self.page10_status_log_frame.setObjectName("page10_status_log_frame")
        self.page10_status_log_frame.setStyleSheet(
            f"QFrame#page10_status_log_frame {{ border: 2px solid {self.themes['app_color']['bg_two']}; border-radius: 6px; }}"
        )
        # Ensure the log box takes the larger portion of the row
        self.page10_status_log_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        status_log_layout = QVBoxLayout(self.page10_status_log_frame)
        status_log_layout.setContentsMargins(8, 8, 8, 8)
        status_log_layout.setSpacing(8)

        # Header label
        status_title = QLabel("Status & Log")
        status_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_title.setStyleSheet("font-size: 14pt; font-weight: 600;")
        status_log_layout.addWidget(status_title)

        # Grid for Timer and Step Counter
        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(8)
        status_grid.setVerticalSpacing(6)

        # STEP GROUP: centered title, then Right/Left labels on one row, then the two cells on the same row
        lbl_steps = QLabel("Step Counter")
        lbl_steps.setStyleSheet("font-size: 12pt; font-weight: 600;")
        lbl_steps.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_steps_right = QLabel("Right Leg")
        lbl_steps_right.setStyleSheet("font-size: 10pt; font-weight: 600;")
        lbl_steps_right.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_steps_left = QLabel("Left Leg")
        lbl_steps_left.setStyleSheet("font-size: 10pt; font-weight: 600;")
        lbl_steps_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.page10_step_right_value = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="")
        self.page10_step_right_value.setReadOnly(True)
        self.page10_step_right_value.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.page10_step_right_value.setMinimumHeight(LINE_HEIGHT)

        self.page10_step_left_value = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="")
        self.page10_step_left_value.setReadOnly(True)
        self.page10_step_left_value.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.page10_step_left_value.setMinimumHeight(LINE_HEIGHT)
        
        # Active Phase title and per-leg read-only fields (below step counters)
        lbl_active = QLabel("Active Phase")
        lbl_active.setStyleSheet("font-size: 12pt; font-weight: 600;")
        lbl_active.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_active_right = QLabel("Right Leg")
        lbl_active_right.setStyleSheet("font-size: 10pt; font-weight: 600;")
        lbl_active_right.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_active_left = QLabel("Left Leg")
        lbl_active_left.setStyleSheet("font-size: 10pt; font-weight: 600;")
        lbl_active_left.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Read-only line edits for active phase (mirrors step counter style)
        self.page10_phase_right_value = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="")
        self.page10_phase_right_value.setReadOnly(True)
        self.page10_phase_right_value.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.page10_phase_right_value.setMinimumHeight(LINE_HEIGHT)
        self.page10_phase_right_value.setText("Unknown")

        self.page10_phase_left_value = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="")
        self.page10_phase_left_value.setReadOnly(True)
        self.page10_phase_left_value.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.page10_phase_left_value.setMinimumHeight(LINE_HEIGHT)
        self.page10_phase_left_value.setText("Unknown")

        step_group = QWidget(self.page10_status_log_frame)
        step_grid = QGridLayout(step_group)
        step_grid.setContentsMargins(0, 0, 0, 0)
        step_grid.setHorizontalSpacing(8)
        step_grid.setVerticalSpacing(6)
        # Title centered across both columns
        step_grid.addWidget(lbl_steps, 0, 0, 1, 2, Qt.AlignmentFlag.AlignHCenter)
        # Labels row
        step_grid.addWidget(lbl_steps_right, 1, 1)
        step_grid.addWidget(lbl_steps_left, 1, 0)
        # Cells row (same line for both)
        step_grid.addWidget(self.page10_step_right_value, 2, 1)
        step_grid.addWidget(self.page10_step_left_value, 2, 0)
        
        # Active phase rows
        step_grid.addWidget(lbl_active, 3, 0, 1, 2, Qt.AlignmentFlag.AlignHCenter)
        step_grid.addWidget(lbl_active_right, 4, 1)
        step_grid.addWidget(lbl_active_left, 4, 0)
        step_grid.addWidget(self.page10_phase_right_value, 5, 1)
        step_grid.addWidget(self.page10_phase_left_value, 5, 0)


        # TIMER GROUP (label over spacer over cell) so the cell aligns with the step cells row
        lbl_timer = QLabel("Timer")
        lbl_timer.setStyleSheet("font-size: 12pt; font-weight: 600;")
        lbl_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.page10_timer_value = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="")
        self.page10_timer_value.setReadOnly(True)
        self.page10_timer_value.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.page10_timer_value.setMinimumHeight(LINE_HEIGHT)
        # Center the text and keep a fixed width so it stays centered when resizing
        self.page10_timer_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page10_timer_value.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # spacer to match the Right/Left labels row height
        timer_spacer = QLabel(" ")
        timer_spacer.setStyleSheet("font-size: 10pt; font-weight: 600;")
        timer_spacer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        timer_group = QWidget(self.page10_status_log_frame)
        timer_vbox = QVBoxLayout(timer_group)
        timer_vbox.setContentsMargins(0, 0, 0, 0)
        timer_vbox.setSpacing(6)
        timer_vbox.addWidget(lbl_timer, 0, Qt.AlignmentFlag.AlignHCenter)
        timer_vbox.addWidget(timer_spacer)
        timer_vbox.addWidget(self.page10_timer_value, 0, Qt.AlignmentFlag.AlignHCenter)

        # Place groups side by side and align to top
        status_grid.addWidget(timer_group, 0, 0, 1, 1, Qt.AlignmentFlag.AlignTop)
        status_grid.addWidget(step_group, 0, 1, 1, 1, Qt.AlignmentFlag.AlignTop)
        status_grid.setColumnStretch(0, 1)
        status_grid.setColumnStretch(1, 2)

        status_log_layout.addLayout(status_grid)

        # Log box (captures terminal prints)
        self.page10_log_box = QTextBrowser(self.page10_status_log_frame)
        self.page10_log_box.setStyleSheet(
            f"color: {self.themes['app_color']['text_foreground']};"
            f"background-color: {self.themes['app_color']['dark_one']};"
            f"border: 1px solid {self.themes['app_color']['bg_two']};"
            "border-radius: 6px; padding: 6px;"
        )
        self.page10_log_box.setMinimumHeight(180)
        status_log_layout.addWidget(self.page10_log_box, 1)

        # Assemble row
        self.page10_footer_row_layout.addWidget(left_col, 1)
        self.page10_footer_row_layout.addWidget(self.page10_status_log_frame, 3)
        self.page10_footer_row_layout.setStretch(0, 1)  # left: Start/Stop column
        self.page10_footer_row_layout.setStretch(1, 3)  # right: Status & Log

        # Add the footer row to Page 10 layout
        page10_layout.addWidget(self.page10_footer_row)

        #---- Redirect stdout/stderr to the log box (while keeping terminal output) ----
        class _QtStreamRedirect(QObject):
            text_written = Signal(str)
            def __init__(self, original_stream):
                super().__init__()
                self._orig = original_stream
            def write(self, s: str):
                try:
                    self._orig.write(s)
                except Exception:
                    pass
                self.text_written.emit(s)
            def flush(self):
                try:
                    self._orig.flush()
                except Exception:
                    pass

        try:
            self._orig_stdout = sys.stdout
            self._orig_stderr = sys.stderr
            self._stdout_redirect = _QtStreamRedirect(self._orig_stdout)
            self._stderr_redirect = _QtStreamRedirect(self._orig_stderr)
            self._stdout_redirect.text_written.connect(self.page10_log_box.append)
            self._stderr_redirect.text_written.connect(self.page10_log_box.append)
            sys.stdout = self._stdout_redirect
            sys.stderr = self._stderr_redirect
        except Exception:
            pass

        # Update hidden field and derived labels when selecting CF
        def _on_carrier_selected(freq_hz: int):
            tscs_on = bool(getattr(self, "tscs_toggle", None) and self.tscs_toggle.isChecked())
            fes_on = bool(getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked())
            # Uses the hidden field from Task Information page
            if tscs_on and not fes_on:
               self.lineEdit_carrier_frequency.setText(str(freq_hz))
            else: 
               self.lineEdit_carrier_frequency_tscs.setText(str(freq_hz)) 
            calculate_stimulation_parameters()

        self.cf_0khz_cb.toggled.connect(lambda checked: _on_carrier_selected(0) if checked else None)
        self.cf_5khz_cb.toggled.connect(lambda checked: _on_carrier_selected(5000) if checked else None)
        self.cf_10khz_cb.toggled.connect(lambda checked: _on_carrier_selected(10000) if checked else None)

        # Toggle "Other": enable entry and apply current value
        def _on_other_toggled(checked: bool):
            self.cf_other_edit.setEnabled(checked)
            if checked:
                # parse kHz -> Hz
                try:
                    khz = float((self.cf_other_edit.text() or "0").replace(",", "."))
                except ValueError:
                    khz = 0.0
                _on_carrier_selected(int(round(khz * 1000)))
        self.cf_other_cb.toggled.connect(_on_other_toggled)
        # When user edits kHz, ensure "Other" is active and apply
        def _apply_other_from_edit():
            if not self.cf_other_cb.isChecked():
                self.cf_other_cb.setChecked(True)
                return
            try:
                khz = float((self.cf_other_edit.text() or "0").replace(",", "."))
            except ValueError:
                khz = 0.0
            _on_carrier_selected(int(round(khz * 1000)))
        self.cf_other_edit.editingFinished.connect(_apply_other_from_edit)

        # Reflect current carrier into the checkboxes
        def _sync_carrier_checkboxes():
            try:
                v = int((self.lineEdit_carrier_frequency.text() or "0").strip())
            except ValueError:
                v = 0
            for cb in (self.cf_0khz_cb, self.cf_5khz_cb, self.cf_10khz_cb,self.cf_other_cb):
                cb.blockSignals(True)
            self.cf_0khz_cb.setChecked(v == 0)
            self.cf_5khz_cb.setChecked(v == 5000)
            self.cf_10khz_cb.setChecked(v == 10000)
            # If not standard, select Other and show kHz
            if v not in (0, 5000, 10000):
                self.cf_other_cb.setChecked(True)
                self.cf_other_edit.setEnabled(True)
                # show as kHz with up to 2 decimals
                self.cf_other_edit.blockSignals(True)
                self.cf_other_edit.setText("{:.2f}".format(v / 1000.0).rstrip("0").rstrip("."))
                self.cf_other_edit.blockSignals(False)
            else:
                self.cf_other_cb.setChecked(False)
                self.cf_other_edit.setEnabled(False)
            for cb in (self.cf_0khz_cb, self.cf_5khz_cb, self.cf_10khz_cb,self.cf_other_cb):
                cb.blockSignals(False)

        # Initial sync after widgets exist
        QTimer.singleShot(0, _sync_carrier_checkboxes)

        # Hook into task loader so CF reflects loaded tasks
        # (Assumes load_task is defined above in setup_gui)
        if 'load_task' in locals():
            old_load_task = load_task
            def load_task(activated_button: QToolButton, selected_action: QAction):
                old_load_task(activated_button, selected_action)
                try:
                    _sync_carrier_checkboxes()
                except Exception:
                    pass
























        # PAGE 5 - STIMULATION SETUP
        # ///////////////////////////////////////////////////////////////
        # MENU ACTIONS
        def select_electrode(activated_button: PyPushButton, selected_action: QAction):
            activated_button.setText(selected_action.text())

            # Update target list
            update_target_list()

            # Get the buttons
            buttons: list[int] = SetupMainWindow.get_placement_buttons(self.tasks_path, self.dropdown_btn_placement.text())

            # Find the index of the button in the list
            def get_index(button: PyPushButton):
                for ind, btn in enumerate(buttons):
                    if self.btn_chan_connection[btn] == button:
                        return ind
                return -1

            number = get_index(activated_button)

            path_to_svg = change_number_to(
                Functions.set_svg_image("modified_image.svg"),
                number,
                int(selected_action.text()[-1]),
            )

            # White and red in hex
            white_hex = "#FFFFFF"
            red_hex = "#FF0000"

            # Change textcolor of all electrodes to white
            for ind, btn in enumerate(buttons):
                if self.btn_chan_connection[btn].text() != "Choose Channel":
                    change_color_to(path_to_svg, ind, white_hex)

            # Find duplicates
            name_map = defaultdict(list)
            for btn in self.btn_chan_connection:
                name_map[btn.text()].append(btn)

            duplicates = {name: btns for name, btns in name_map.items() if len(btns) > 1}

            # Change color of duplicates to red
            for key, btn in duplicates.items():
                if key == "Choose Channel":
                    continue

                for b in btn:
                    index = get_index(b)
                    change_color_to(path_to_svg, index, red_hex)

            self.back_image.load(path_to_svg)
            self.back_image.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

        def update_target_list():
            # Update the target list based on the selected channels
            self.target_list = []
            for btn in self.btn_chan_connection:
                if btn.text() != "Choose Channel" and btn.isEnabled():
                    self.target_list.append(btn.text())
            # Remove duplicates and sort to have Channel 0, Channel 1, etc.
            self.target_list = sorted(set(self.target_list), key=lambda x: int(x.split(" ")[-1]))
            # Add "Not to be used" as the first item
            self.target_list.insert(0, "Not to be used")

            # Create actions and add them to the dropdown buttons
            for i in range(1, 8):
                dropdown_btn: PyDropDownButton = getattr(self, f"dropdown_btn_target_{i}")
                previous_action = dropdown_btn.text()
                dropdown_btn.set_actions([QAction(channel) for channel in self.target_list])

                # If the previous action is not in the new list, set the button to "Not to be used"
                dropdown_btn.setText("Not to be used")

                # Set the previous action as selected if it exists in the new list
                for action in dropdown_btn._menu.actions():
                    if action.text() == previous_action:
                        dropdown_btn.on_action_triggered(action)
                        break
            # Keep the Page 10 test channel list in sync with available channels
            if hasattr(self, "page10_test_channel_dd"):
                try:
                    _refresh_page10_test_channels()
                except Exception:
                    pass

        self.channel_actions = [
            QAction("Channel 0"),
            QAction("Channel 1"),
            QAction("Channel 2"),
            QAction("Channel 3"),
            QAction("Channel 4"),
            QAction("Channel 5"),
            QAction("Channel 6"),
            QAction("Channel 7"),
        ]

        # LINE EDIT 1 - CHANNEL 0 AMPLITUDE
        self.lineEdit_channel_0 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 0 Amplitude")
        self.lineEdit_channel_0.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_0.setToolTip("Feedforward stimulation amplitude for Channel 0. (Open Loop)")

        # LINE EDIT 2 - CHANNEL 0 MAXIMUM AMPLITUDE
        self.lineEdit_channel_0_max = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 0 Max Amplitude")
        self.lineEdit_channel_0_max.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_0_max.setToolTip("Maximum amplitude for Channel 0. (Only used for Closed Loop)")

        # LINE EDIT 3 - CHANNEL 1 AMPLITUDE
        self.lineEdit_channel_1 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 1 Amplitude")
        self.lineEdit_channel_1.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_1.setToolTip("Feedforward stimulation amplitude for Channel 1. (Open Loop)")

        # LINE EDIT 4 - CHANNEL 1 MAXIMUM AMPLITUDE
        self.lineEdit_channel_1_max = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 1 Max Amplitude")
        self.lineEdit_channel_1_max.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_1_max.setToolTip("Maximum amplitude for Channel 1. (Only used for Closed Loop)")

        # LINE EDIT 5 - CHANNEL 2 AMPLITUDE
        self.lineEdit_channel_2 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 2 Amplitude")
        self.lineEdit_channel_2.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_2.setToolTip("Feedforward stimulation amplitude for Channel 2. (Open Loop)")

        # LINE EDIT 6 - CHANNEL 2 MAXIMUM AMPLITUDE
        self.lineEdit_channel_2_max = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 2 Max Amplitude")
        self.lineEdit_channel_2_max.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_2_max.setToolTip("Maximum amplitude for Channel 2. (Only used for Closed Loop)")

        # LINE EDIT 7 - CHANNEL 3 AMPLITUDE
        self.lineEdit_channel_3 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 3 Amplitude")
        self.lineEdit_channel_3.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_3.setToolTip("Feedforward stimulation amplitude for Channel 3. (Open Loop)")

        # LINE EDIT 8 - CHANNEL 3 MAXIMUM AMPLITUDE
        self.lineEdit_channel_3_max = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 3 Max Amplitude")
        self.lineEdit_channel_3_max.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_3_max.setToolTip("Maximum amplitude for Channel 3. (Only used for Closed Loop)")

        # LINE EDIT 9 - CHANNEL 4 AMPLITUDE
        self.lineEdit_channel_4 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 4 Amplitude")
        self.lineEdit_channel_4.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_4.setToolTip("Feedforward stimulation amplitude for Channel 4. (Open Loop)")

        # LINE EDIT 10 - CHANNEL 4 MAXIMUM AMPLITUDE
        self.lineEdit_channel_4_max = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 4 Max Amplitude")
        self.lineEdit_channel_4_max.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_4_max.setToolTip("Maximum amplitude for Channel 4. (Only used for Closed Loop)")

        # LINE EDIT 11 - CHANNEL 5 AMPLITUDE
        self.lineEdit_channel_5 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 5 Amplitude")
        self.lineEdit_channel_5.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_5.setToolTip("Feedforward stimulation amplitude for Channel 5. (Open Loop)")

        # LINE EDIT 12 - CHANNEL 5 MAXIMUM AMPLITUDE
        self.lineEdit_channel_5_max = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 5 Max Amplitude")
        self.lineEdit_channel_5_max.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_5_max.setToolTip("Maximum amplitude for Channel 5. (Only used for Closed Loop)")

        # LINE EDIT 13 - CHANNEL 6 AMPLITUDE
        self.lineEdit_channel_6 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 6 Amplitude")
        self.lineEdit_channel_6.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_6.setToolTip("Feedforward stimulation amplitude for Channel 6. (Open Loop)")

        # LINE EDIT 14 - CHANNEL 6 MAXIMUM AMPLITUDE
        self.lineEdit_channel_6_max = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 6 Max Amplitude")
        self.lineEdit_channel_6_max.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_6_max.setToolTip("Maximum amplitude for Channel 6. (Only used for Closed Loop)")

        # LINE EDIT 15 - CHANNEL 7 AMPLITUDE
        self.lineEdit_channel_7 = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 7 Amplitude")
        self.lineEdit_channel_7.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_7.setToolTip("Feedforward stimulation amplitude for Channel 7. (Open Loop)")

        # LINE EDIT 16 - CHANNEL 7 MAXIMUM AMPLITUDE
        self.lineEdit_channel_7_max = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 7 Max Amplitude")
        self.lineEdit_channel_7_max.setMinimumWidth(LINE_WIDTH // 2)
        self.lineEdit_channel_7_max.setToolTip("Maximum amplitude for Channel 7. (Only used for Closed Loop)")

        # LINE EDIT 17 - SELECTED TASK
        self.lineEdit_selected_task = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="No Task Selected")
        self.lineEdit_selected_task.setReadOnly(True)
        self.lineEdit_selected_task.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # DROP DOWN BUTTON 1
        self.dropdown_btn_l_elec_1 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.channel_actions, "Choose Channel")
        self.dropdown_btn_l_elec_1.setMinimumHeight(BUTTON_HEIGHT)

        # DROP DOWN BUTTON 2
        self.dropdown_btn_l_elec_2 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.channel_actions, "Choose Channel")
        self.dropdown_btn_l_elec_2.setMinimumHeight(BUTTON_HEIGHT)

        # DROP DOWN BUTTON 3
        self.dropdown_btn_l_elec_3 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.channel_actions, "Choose Channel")
        self.dropdown_btn_l_elec_3.setMinimumHeight(BUTTON_HEIGHT)

        # DROP DOWN BUTTON 4
        self.dropdown_btn_l_elec_4 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.channel_actions, "Choose Channel")
        self.dropdown_btn_l_elec_4.setMinimumHeight(BUTTON_HEIGHT)

        # DROP DOWN BUTTON 5
        self.dropdown_btn_r_elec_1 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.channel_actions, "Choose Channel")
        self.dropdown_btn_r_elec_1.setMinimumHeight(BUTTON_HEIGHT)

        # DROP DOWN BUTTON 6
        self.dropdown_btn_r_elec_2 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.channel_actions, "Choose Channel")
        self.dropdown_btn_r_elec_2.setMinimumHeight(BUTTON_HEIGHT)

        # DROP DOWN BUTTON 7
        self.dropdown_btn_r_elec_3 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.channel_actions, "Choose Channel")
        self.dropdown_btn_r_elec_3.setMinimumHeight(BUTTON_HEIGHT)

        # DROP DOWN BUTTON 8
        self.dropdown_btn_r_elec_4 = SetupMainWindow.create_std_dropdown_btn(self.themes, self.channel_actions, "Choose Channel")
        self.dropdown_btn_r_elec_4.setMinimumHeight(BUTTON_HEIGHT)

        # DROP DOWN BUTTON 9
        self.dropdown_btn_target_1 = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
        self.dropdown_btn_target_1.setMinimumHeight(LINE_HEIGHT)

        # DROP DOWN BUTTON 10
        self.dropdown_btn_target_2 = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
        self.dropdown_btn_target_2.setMinimumHeight(LINE_HEIGHT)

        # DROP DOWN BUTTON 11
        self.dropdown_btn_target_3 = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
        self.dropdown_btn_target_3.setMinimumHeight(LINE_HEIGHT)

        # DROP DOWN BUTTON 12
        self.dropdown_btn_target_4 = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
        self.dropdown_btn_target_4.setMinimumHeight(LINE_HEIGHT)

        # DROP DOWN BUTTON 13
        self.dropdown_btn_target_5 = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
        self.dropdown_btn_target_5.setMinimumHeight(LINE_HEIGHT)

        # DROP DOWN BUTTON 14
        self.dropdown_btn_target_6 = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
        self.dropdown_btn_target_6.setMinimumHeight(LINE_HEIGHT)

        # DROP DOWN BUTTON 15
        self.dropdown_btn_target_7 = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
        self.dropdown_btn_target_7.setMinimumHeight(LINE_HEIGHT)
        
        # DROP DOWN BUTTON 16
        self.dropdown_btn_target_8 = SetupMainWindow.create_std_dropdown_btn(self.themes, [], "Not to be used")
        self.dropdown_btn_target_8.setMinimumHeight(LINE_HEIGHT)


        # PUSH BUTTON 1
        self.finish_btn_4 = SetupMainWindow.create_std_push_btn(self.themes, text="Finish")

        # CREATE WIDGETS
        # Create amplitude widgets for all 8 channels (0-7)
        self.channel_0_amp_widget = QWidget()
        self.channel_0_amp_widget.setLayout(QHBoxLayout())
        self.channel_0_amp_widget.layout().setContentsMargins(0, 0, 0, 0)

        self.channel_1_amp_widget = QWidget()
        self.channel_1_amp_widget.setLayout(QHBoxLayout())
        self.channel_1_amp_widget.layout().setContentsMargins(0, 0, 0, 0)

        self.channel_2_amp_widget = QWidget()
        self.channel_2_amp_widget.setLayout(QHBoxLayout())
        self.channel_2_amp_widget.layout().setContentsMargins(0, 0, 0, 0)

        self.channel_3_amp_widget = QWidget()
        self.channel_3_amp_widget.setLayout(QHBoxLayout())
        self.channel_3_amp_widget.layout().setContentsMargins(0, 0, 0, 0)

        self.channel_4_amp_widget = QWidget()
        self.channel_4_amp_widget.setLayout(QHBoxLayout())
        self.channel_4_amp_widget.layout().setContentsMargins(0, 0, 0, 0)

        self.channel_5_amp_widget = QWidget()
        self.channel_5_amp_widget.setLayout(QHBoxLayout())
        self.channel_5_amp_widget.layout().setContentsMargins(0, 0, 0, 0)

        self.channel_6_amp_widget = QWidget()
        self.channel_6_amp_widget.setLayout(QHBoxLayout())
        self.channel_6_amp_widget.layout().setContentsMargins(0, 0, 0, 0)

        self.channel_7_amp_widget = QWidget()
        self.channel_7_amp_widget.setLayout(QHBoxLayout())
        self.channel_7_amp_widget.layout().setContentsMargins(0, 0, 0, 0)

        # FILL LIST
        self.btn_chan_connection: list[PyDropDownButton] = [
            self.dropdown_btn_l_elec_1,
            self.dropdown_btn_l_elec_2,
            self.dropdown_btn_l_elec_3,
            self.dropdown_btn_l_elec_4,
            self.dropdown_btn_r_elec_1,
            self.dropdown_btn_r_elec_2,
            self.dropdown_btn_r_elec_3,
            self.dropdown_btn_r_elec_4,
        ]

        self.target_list: str = []

        # ADD IMAGE
        self.back_image = QSvgWidget()
        SetupMainWindow.load_back_image("No Electrodes", self.tasks_path, self.btn_chan_connection, self.back_image)

        # ADD VALIDATOR
        self.int_validator = QIntValidator(0, 1000)
        self.lineEdit_channel_0.setValidator(self.int_validator)
        self.lineEdit_channel_1.setValidator(self.int_validator)
        self.lineEdit_channel_2.setValidator(self.int_validator)
        self.lineEdit_channel_3.setValidator(self.int_validator)
        self.lineEdit_channel_4.setValidator(self.int_validator)
        self.lineEdit_channel_5.setValidator(self.int_validator)
        self.lineEdit_channel_6.setValidator(self.int_validator)
        self.lineEdit_channel_7.setValidator(self.int_validator)

        # FILL DICTIONARY
        self.channel_dict = {
            "Channel 0": self.lineEdit_channel_0,
            "Channel 1": self.lineEdit_channel_1,
            "Channel 2": self.lineEdit_channel_2,
            "Channel 3": self.lineEdit_channel_3,
            "Channel 4": self.lineEdit_channel_4,
            "Channel 5": self.lineEdit_channel_5,
            "Channel 6": self.lineEdit_channel_6,
            "Channel 7": self.lineEdit_channel_7,
        }

        self.channel_max_dict = {
            "Channel 0": self.lineEdit_channel_0_max,
            "Channel 1": self.lineEdit_channel_1_max,
            "Channel 2": self.lineEdit_channel_2_max,
            "Channel 3": self.lineEdit_channel_3_max,
            "Channel 4": self.lineEdit_channel_4_max,
            "Channel 5": self.lineEdit_channel_5_max,
            "Channel 6": self.lineEdit_channel_6_max,
            "Channel 7": self.lineEdit_channel_7_max,
        }

        self.subject_info_dict["task"] = self.lineEdit_selected_task

        # CONNECT BUTTONS
        self.dropdown_btn_l_elec_1.clicked.connect(self.dropdown_btn_l_elec_1.showMenu)
        self.dropdown_btn_l_elec_2.clicked.connect(self.dropdown_btn_l_elec_2.showMenu)
        self.dropdown_btn_l_elec_3.clicked.connect(self.dropdown_btn_l_elec_3.showMenu)
        self.dropdown_btn_l_elec_4.clicked.connect(self.dropdown_btn_l_elec_4.showMenu)
        self.dropdown_btn_r_elec_1.clicked.connect(self.dropdown_btn_r_elec_1.showMenu)
        self.dropdown_btn_r_elec_2.clicked.connect(self.dropdown_btn_r_elec_2.showMenu)
        self.dropdown_btn_r_elec_3.clicked.connect(self.dropdown_btn_r_elec_3.showMenu)
        self.dropdown_btn_r_elec_4.clicked.connect(self.dropdown_btn_r_elec_4.showMenu)
        self.dropdown_btn_target_1.clicked.connect(self.dropdown_btn_target_1.showMenu)
        self.dropdown_btn_target_2.clicked.connect(self.dropdown_btn_target_2.showMenu)
        self.dropdown_btn_target_3.clicked.connect(self.dropdown_btn_target_3.showMenu)
        self.dropdown_btn_target_4.clicked.connect(self.dropdown_btn_target_4.showMenu)
        self.dropdown_btn_target_5.clicked.connect(self.dropdown_btn_target_5.showMenu)
        self.dropdown_btn_target_6.clicked.connect(self.dropdown_btn_target_6.showMenu)
        self.dropdown_btn_target_7.clicked.connect(self.dropdown_btn_target_7.showMenu)
        self.dropdown_btn_target_8.clicked.connect(self.dropdown_btn_target_8.showMenu)

        self.finish_btn_4.clicked.connect(finish_btn_clicked)

        self.dropdown_btn_l_elec_1.action_selected.connect(select_electrode)
        self.dropdown_btn_l_elec_2.action_selected.connect(select_electrode)
        self.dropdown_btn_l_elec_3.action_selected.connect(select_electrode)
        self.dropdown_btn_l_elec_4.action_selected.connect(select_electrode)
        self.dropdown_btn_r_elec_1.action_selected.connect(select_electrode)
        self.dropdown_btn_r_elec_2.action_selected.connect(select_electrode)
        self.dropdown_btn_r_elec_3.action_selected.connect(select_electrode)
        self.dropdown_btn_r_elec_4.action_selected.connect(select_electrode)

        # ADD WIDGETS
        # Add line edits to layout of intermediate widgets
        self.channel_0_amp_widget.layout().addWidget(self.lineEdit_channel_0)
        self.channel_0_amp_widget.layout().addWidget(self.lineEdit_channel_0_max)
        self.channel_1_amp_widget.layout().addWidget(self.lineEdit_channel_1)
        self.channel_1_amp_widget.layout().addWidget(self.lineEdit_channel_1_max)
        self.channel_2_amp_widget.layout().addWidget(self.lineEdit_channel_2)
        self.channel_2_amp_widget.layout().addWidget(self.lineEdit_channel_2_max)
        self.channel_3_amp_widget.layout().addWidget(self.lineEdit_channel_3)
        self.channel_3_amp_widget.layout().addWidget(self.lineEdit_channel_3_max)
        self.channel_4_amp_widget.layout().addWidget(self.lineEdit_channel_4)
        self.channel_4_amp_widget.layout().addWidget(self.lineEdit_channel_4_max)
        self.channel_5_amp_widget.layout().addWidget(self.lineEdit_channel_5)
        self.channel_5_amp_widget.layout().addWidget(self.lineEdit_channel_5_max)
        self.channel_6_amp_widget.layout().addWidget(self.lineEdit_channel_6)
        self.channel_6_amp_widget.layout().addWidget(self.lineEdit_channel_6_max)
        self.channel_7_amp_widget.layout().addWidget(self.lineEdit_channel_7)
        self.channel_7_amp_widget.layout().addWidget(self.lineEdit_channel_7_max)
        # Add intermediate widgets to layouts
        self.ui.load_pages.channel_layout_0.addWidget(self.channel_0_amp_widget)
        self.ui.load_pages.channel_layout_1.addWidget(self.channel_1_amp_widget)
        self.ui.load_pages.channel_layout_2.addWidget(self.channel_2_amp_widget)
        self.ui.load_pages.channel_layout_3.addWidget(self.channel_3_amp_widget)
        self.ui.load_pages.channel_layout_4.addWidget(self.channel_4_amp_widget)
        self.ui.load_pages.channel_layout_5.addWidget(self.channel_5_amp_widget)
        self.ui.load_pages.channel_layout_6.addWidget(self.channel_6_amp_widget)
        self.ui.load_pages.channel_layout_7.addWidget(self.channel_7_amp_widget)
        # Add other widgets to layouts
        self.ui.load_pages.selected_task_layout.addWidget(self.lineEdit_selected_task)
        self.ui.load_pages.image_layout.addWidget(self.back_image)
        self.ui.load_pages.channel_assign_layout.addWidget(self.dropdown_btn_l_elec_1)
        self.ui.load_pages.channel_assign_layout.addWidget(self.dropdown_btn_r_elec_1)
        self.ui.load_pages.channel_assign_layout.addWidget(self.dropdown_btn_l_elec_2)
        self.ui.load_pages.channel_assign_layout.addWidget(self.dropdown_btn_r_elec_2)
        self.ui.load_pages.channel_assign_layout.addWidget(self.dropdown_btn_l_elec_3)
        self.ui.load_pages.channel_assign_layout.addWidget(self.dropdown_btn_r_elec_3)
        self.ui.load_pages.channel_assign_layout.addWidget(self.dropdown_btn_l_elec_4)
        self.ui.load_pages.channel_assign_layout.addWidget(self.dropdown_btn_r_elec_4)
        self.ui.load_pages.target_assign_layout.addWidget(self.dropdown_btn_target_1, 1, 1)
        self.ui.load_pages.target_assign_layout.addWidget(self.dropdown_btn_target_2, 2, 1)
        self.ui.load_pages.target_assign_layout.addWidget(self.dropdown_btn_target_3, 3, 1)
        self.ui.load_pages.target_assign_layout.addWidget(self.dropdown_btn_target_4, 4, 1)
        self.ui.load_pages.target_assign_layout.addWidget(self.dropdown_btn_target_5, 5, 1)
        self.ui.load_pages.target_assign_layout.addWidget(self.dropdown_btn_target_6, 6, 1)
        self.ui.load_pages.target_assign_layout.addWidget(self.dropdown_btn_target_7, 7, 1)
        self.ui.load_pages.target_assign_layout.addWidget(self.dropdown_btn_target_8, 8, 1)
        self.ui.load_pages.finish_btn_layout_4.addWidget(self.finish_btn_4)

        # Change frame color
        self.ui.load_pages.image_frame.setStyleSheet(self.frame_stylesheet)

        # PAGE 6 - CONFIRMATION
        # ///////////////////////////////////////////////////////////////
        # LINE EDIT 1 - FIRST NAME CONFIRMATION
        self.lineEdit_first_name_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="First Name")

        # LINE EDIT 2 - LAST NAME CONFIRMATION
        self.lineEdit_last_name_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Last Name")

        # LINE EDIT 3 - SUBJECT ID CONFIRMATION
        self.lineEdit_subject_id_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Subject ID")

        # LINE EDIT 4 - HEIGHT CONFIRMATION
        self.lineEdit_height_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Height")

        # LINE EDIT 5 - WEIGHT CONFIRMATION
        self.lineEdit_weight_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Weight")

        # LINE EDIT 6 - AGE CONFIRMATION
        self.lineEdit_age_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Age")

        # Read-only confirm fields for stimulation params
        self.lineEdit_burst_frequency_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Burst Frequency [Hz]")
        self.lineEdit_burst_frequency_confirm.setReadOnly(True); self.lineEdit_burst_frequency_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_burst_duration_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Burst Duration [us]")
        self.lineEdit_burst_duration_confirm.setReadOnly(True); self.lineEdit_burst_duration_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_pulse_deadtime_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Pulse Deadtime (T2) [us]")
        self.lineEdit_pulse_deadtime_confirm.setReadOnly(True); self.lineEdit_pulse_deadtime_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_interpulse_interval_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Interpulse Interval (T3) [us]")
        self.lineEdit_interpulse_interval_confirm.setReadOnly(True); self.lineEdit_interpulse_interval_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_carrier_frequency_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Carrier Frequency [Hz]")
        self.lineEdit_carrier_frequency_confirm.setReadOnly(True); self.lineEdit_carrier_frequency_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # LINE EDIT 7 - TASK CONFIRMATION
        self.lineEdit_task_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Task Name")
        self.lineEdit_task_confirm.setMaximumWidth(1e6)

        # LINE EDIT 8 - SAVE INFO CONFIRMATION
        self.lineEdit_save_info_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Save Info")
        self.lineEdit_save_info_confirm.setMaximumWidth(1e6)
        # LINE EDIT 9 - CHANNEL 0 CONFIRMATION
        self.lineEdit_channel_0_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 0 Amplitude")

        # LINE EDIT 10 - CHANNEL 1 CONFIRMATION
        self.lineEdit_channel_1_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 1 Amplitude")

        # LINE EDIT 11 - CHANNEL 2 CONFIRMATION
        self.lineEdit_channel_2_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 2 Amplitude")

        # LINE EDIT 12 - CHANNEL 3 CONFIRMATION
        self.lineEdit_channel_3_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 3 Amplitude")

        # LINE EDIT 13 - CHANNEL 4 CONFIRMATION
        self.lineEdit_channel_4_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 4 Amplitude")

        # LINE EDIT 14 - CHANNEL 5 CONFIRMATION
        self.lineEdit_channel_5_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 5 Amplitude")

        # LINE EDIT 15 - CHANNEL 6 CONFIRMATION
        self.lineEdit_channel_6_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 6 Amplitude")

        # LINE EDIT 16 - CHANNEL 7 CONFIRMATION
        self.lineEdit_channel_7_confirm = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Channel 7 Amplitude")

        # PUSH BUTTON 1
        self.confirm_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Confirm")

        # PUSH BUTTON 2
        self.cancel_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Cancel")

        # IMAGE
        self.confirm_image = QSvgWidget(Functions.set_svg_image("modified_image.svg"))

        # FILL DICTIONARY
        self.confirm_dict = {}
        self.confirm_dict[self.lineEdit_first_name_confirm] = self.lineEdit_first_name
        self.confirm_dict[self.lineEdit_last_name_confirm] = self.lineEdit_last_name
        self.confirm_dict[self.lineEdit_subject_id_confirm] = self.lineEdit_subject_id
        self.confirm_dict[self.lineEdit_height_confirm] = self.lineEdit_height
        self.confirm_dict[self.lineEdit_weight_confirm] = self.lineEdit_weight
        self.confirm_dict[self.lineEdit_age_confirm] = self.lineEdit_age

        self.confirm_dict[self.lineEdit_burst_frequency_confirm]     = self.lineEdit_burst_frequency
        self.confirm_dict[self.lineEdit_burst_duration_confirm]      = self.lineEdit_burst_duration
        self.confirm_dict[self.lineEdit_pulse_deadtime_confirm]      = self.lineEdit_pulse_deadtime
        self.confirm_dict[self.lineEdit_interpulse_interval_confirm] = self.lineEdit_interpulse_interval
        self.confirm_dict[self.lineEdit_carrier_frequency_confirm]   = self.lineEdit_carrier_frequency

        self.confirm_dict[self.lineEdit_task_confirm] = self.lineEdit_selected_task
        self.confirm_dict[self.lineEdit_save_info_confirm] = [
            self.lineEdit_safe_path,
            self.lineEdit_file_name,
        ]
        self.confirm_dict[self.lineEdit_channel_0_confirm] = self.lineEdit_channel_0
        self.confirm_dict[self.lineEdit_channel_1_confirm] = self.lineEdit_channel_1
        self.confirm_dict[self.lineEdit_channel_2_confirm] = self.lineEdit_channel_2
        self.confirm_dict[self.lineEdit_channel_3_confirm] = self.lineEdit_channel_3
        self.confirm_dict[self.lineEdit_channel_4_confirm] = self.lineEdit_channel_4
        self.confirm_dict[self.lineEdit_channel_5_confirm] = self.lineEdit_channel_5
        self.confirm_dict[self.lineEdit_channel_6_confirm] = self.lineEdit_channel_6
        self.confirm_dict[self.lineEdit_channel_7_confirm] = self.lineEdit_channel_7

        # ALIGN CENTER
        self.lineEdit_first_name_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_last_name_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_subject_id_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_height_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_weight_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_age_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lineEdit_burst_frequency_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_burst_duration_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_pulse_deadtime_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_interpulse_interval_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_carrier_frequency_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lineEdit_task_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_save_info_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_channel_0_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_channel_1_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_channel_2_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_channel_3_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_channel_4_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_channel_5_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_channel_6_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineEdit_channel_7_confirm.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Create read-only "Target" fields per channel for Page 6 (confirmation)
        for ch in range(8):
            le_name = f"lineEdit_channel_{ch}_target_confirm"
            if not hasattr(self, le_name):
                tgt = SetupMainWindow.create_std_line_edit(self.themes, place_holder_text="Target")
                tgt.setReadOnly(True)
                tgt.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                tgt.setAlignment(Qt.AlignmentFlag.AlignCenter)
                setattr(self, le_name, tgt)

        # Place Current + Target side-by-side per row in Page 6 form
        def _setup_confirmation_target_display():
            try:
                form: QFormLayout = self.ui.load_pages.channel_layout
                parent = self.ui.load_pages.channel_widget
            except Exception:
                return
            for ch in range(8):
                try:
                    curr: PyLineEdit = getattr(self, f"lineEdit_channel_{ch}_confirm", None)
                    tgt:  PyLineEdit = getattr(self, f"lineEdit_channel_{ch}_target_confirm", None)
                    if not curr or not tgt:
                        continue
                    row_widget = QWidget(parent)
                    row_layout = QHBoxLayout(row_widget)
                    row_layout.setContentsMargins(0, 0, 0, 0)
                    row_layout.setSpacing(6)
                    # keep both compact and same style as other cells
                    curr.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    tgt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                    row_layout.addWidget(curr, 1)
                    row_layout.addWidget(tgt, 1)
                    # Replace the FieldRole with our container
                    form.setWidget(ch, QFormLayout.ItemRole.FieldRole, row_widget)
                except Exception:
                    pass
        # Defer until the confirmation layout exists
        QTimer.singleShot(0, _setup_confirmation_target_display)

        # Frame + grid with labels on top of value cells
        self.stim_params_confirm_frame = QFrame(self.ui.load_pages.page_06)
        self.stim_params_confirm_frame.setObjectName("stim_params_confirm_frame")
        self.stim_params_confirm_frame.setStyleSheet(self.frame_stylesheet)
        self.stim_params_confirm_layout = QGridLayout(self.stim_params_confirm_frame)
        self.stim_params_confirm_layout.setContentsMargins(9, 6, 9, 6)
        self.stim_params_confirm_layout.setHorizontalSpacing(9)
        self.stim_params_confirm_layout.setVerticalSpacing(6)

        label_style = "font-size:12pt"
        lbl_bf  = QLabel("Burst Frequency [Hz]");          lbl_bf.setStyleSheet(label_style);  lbl_bf.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_bd  = QLabel("Burst Duration [us]");           lbl_bd.setStyleSheet(label_style);  lbl_bd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_t2  = QLabel("Pulse Deadtime (T2) [us]");      lbl_t2.setStyleSheet(label_style);  lbl_t2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_t3  = QLabel("Interpulse Interval (T3) [us]"); lbl_t3.setStyleSheet(label_style);  lbl_t3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_cf  = QLabel("Carrier Frequency [Hz]");        lbl_cf.setStyleSheet(label_style);  lbl_cf.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Row 0: labels
        self.stim_params_confirm_layout.addWidget(lbl_bf, 0, 0)
        self.stim_params_confirm_layout.addWidget(lbl_bd, 0, 1)
        self.stim_params_confirm_layout.addWidget(lbl_t2, 0, 2)
        self.stim_params_confirm_layout.addWidget(lbl_t3, 0, 3)
        self.stim_params_confirm_layout.addWidget(lbl_cf, 0, 4)
        # Row 1: read-only values
        self.stim_params_confirm_layout.addWidget(self.lineEdit_burst_frequency_confirm,     1, 0)
        self.stim_params_confirm_layout.addWidget(self.lineEdit_burst_duration_confirm,      1, 1)
        self.stim_params_confirm_layout.addWidget(self.lineEdit_pulse_deadtime_confirm,      1, 2)
        self.stim_params_confirm_layout.addWidget(self.lineEdit_interpulse_interval_confirm, 1, 3)
        self.stim_params_confirm_layout.addWidget(self.lineEdit_carrier_frequency_confirm,   1, 4)

        # SET READ ONLY
        self.lineEdit_first_name_confirm.setReadOnly(True)
        self.lineEdit_last_name_confirm.setReadOnly(True)
        self.lineEdit_subject_id_confirm.setReadOnly(True)
        self.lineEdit_height_confirm.setReadOnly(True)
        self.lineEdit_weight_confirm.setReadOnly(True)
        self.lineEdit_age_confirm.setReadOnly(True)
        self.lineEdit_task_confirm.setReadOnly(True)
        self.lineEdit_save_info_confirm.setReadOnly(True)
        self.lineEdit_channel_0_confirm.setReadOnly(True)
        self.lineEdit_channel_1_confirm.setReadOnly(True)
        self.lineEdit_channel_2_confirm.setReadOnly(True)
        self.lineEdit_channel_3_confirm.setReadOnly(True)
        self.lineEdit_channel_4_confirm.setReadOnly(True)
        self.lineEdit_channel_5_confirm.setReadOnly(True)
        self.lineEdit_channel_6_confirm.setReadOnly(True)
        self.lineEdit_channel_7_confirm.setReadOnly(True)

        # SET FOCUS POLICY
        self.lineEdit_first_name_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_last_name_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_subject_id_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_height_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_weight_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_age_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_task_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_save_info_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_channel_0_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_channel_1_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_channel_2_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_channel_3_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_channel_4_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_channel_5_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_channel_6_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit_channel_7_confirm.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # BUTTON CLICKED
        def confirm_clicked():
            try:
                # Create WaveformParameters object and check for validity
                # Helper to read value from a widget (as_value preferred)
                def _read_widget_value(name):
                    w = getattr(self, name, None)
                    if w is None:
                        return None
                    try:
                        return w.as_value()
                    except Exception:
                        try:
                            return float(w.text())
                        except Exception:
                            return None

                # Determine current mode (fallback to toggles if _stimulation_mode missing)
                mode = getattr(self, "_stimulation_mode", None)
                if mode is None:
                    fes_on = bool(getattr(self, "fes_toggle", None) and self.fes_toggle.isChecked())
                    tscs_on = bool(getattr(self, "tscs_toggle", None) and self.tscs_toggle.isChecked())
                    mode = "hybrid" if (fes_on and tscs_on) else ("fes" if fes_on else "tscs")

                tscs_params = None
                fes_params = None
                if mode == "hybrid":
                    tscs_params = {
                        "burst_frequency": _read_widget_value("lineEdit_burst_frequency_tscs") or _read_widget_value("lineEdit_burst_frequency"),
                        "burst_duration": _read_widget_value("lineEdit_burst_duration_tscs") or _read_widget_value("lineEdit_burst_duration"),
                        "interpulse_interval": _read_widget_value("lineEdit_interpulse_interval_tscs") or _read_widget_value("lineEdit_interpulse_interval"),
                        "pulse_deadtime": _read_widget_value("lineEdit_pulse_deadtime_tscs") or _read_widget_value("lineEdit_pulse_deadtime"),
                        "carrier_frequency": _read_widget_value("lineEdit_carrier_frequency_tscs") or _read_widget_value("lineEdit_carrier_frequency"),
                    }
                    fes_params = {
                        "burst_frequency": _read_widget_value("lineEdit_burst_frequency_fes") or _read_widget_value("lineEdit_burst_frequency"),
                        "burst_duration": _read_widget_value("lineEdit_burst_duration_fes") or _read_widget_value("lineEdit_burst_duration"),
                        "interpulse_interval": _read_widget_value("lineEdit_interpulse_interval_fes") or _read_widget_value("lineEdit_interpulse_interval"),
                        "pulse_deadtime": _read_widget_value("lineEdit_pulse_deadtime_fes") or _read_widget_value("lineEdit_pulse_deadtime"),
                        "carrier_frequency": _read_widget_value("lineEdit_carrier_frequency_fes") or 0,
                    }

                parameters = StimulatorParameters(
                    burst_frequency=self.lineEdit_burst_frequency.as_value(),
                    burst_duration=self.lineEdit_burst_duration.as_value(),
                    pulse_deadtime=self.lineEdit_pulse_deadtime.as_value(),
                    interpulse_interval=self.lineEdit_interpulse_interval.as_value(),
                    carrier_frequency=self.lineEdit_carrier_frequency.as_value(),
                    tscs_params=tscs_params,
                    fes_params=fes_params,
                )
                if not parameters.is_valid():
                    self.error_handler(
                        "Please check waveform parameters. Even without stimulation, these parameters should be set to something."
                    )
                    return

                # Create the dictionary to send to the experiment
                task_dict = SetupMainWindow.create_dict(
                    self,
                    parameters,
                )
            except Exception as e:
                raise e

            # Create only the parent folder of the final file path that’s already shown on Page 6
            try:
                import os
                final_path = self.lineEdit_save_info_confirm.text().strip()
                parent_dir = os.path.dirname(final_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                # Ensure task_dict uses this exact path
                task_dict["save_path_filename"] = final_path
            except Exception as e:
                print(f"Failed to prepare/save session directory: {e}")
            
            # Reset timer display only; start happens via MainWindow.start_timer
            try:
                self.ui.load_pages.time_label.setText("00:00:00")
                self.ui.load_pages.time_label.setVisible(True)
                if hasattr(self, "page10_timer_value") and self.page10_timer_value is not None:
                    self.page10_timer_value.setText("00:00:00")
            except Exception:
                pass

            # Show stop button and hide other buttons
            self.ui.load_pages.selection_btn_widget.setVisible(False)
            self.ui.load_pages.stimulator_frame.setVisible(False)

            # Show time label
            self.ui.load_pages.time_label.setVisible(True)

            # Load start page (PAGE 1)
            self.ui.left_menu.select_only_one("btn_stimulation_2")
            MainFunctions.set_page(self, self.ui.load_pages.page_10)

            # Disable left menu buttons
            self.ui.left_menu.top_frame.setVisible(False)

            # Set focus on the stop button for return
            self.stop_btn.setFocus()

            # Change label
            self.ui.load_pages.title_label.setText("Running...")

            # Start the experiment
            self.start_experiment.emit(task_dict)

        def cancel_clicked():
            # Load home page and select the tab
            MainFunctions.set_page(self, self.ui.load_pages.page_10)
            self.ui.left_menu.select_only_one("btn_stimulation_2")

        # CONNECT BUTTONS
        self.confirm_btn.clicked.connect(confirm_clicked)
        self.cancel_btn.clicked.connect(cancel_clicked)

        # ADD WIDGETS
        self.ui.load_pages.subject_layout.addWidget(self.lineEdit_first_name_confirm)
        self.ui.load_pages.subject_layout.addWidget(self.lineEdit_last_name_confirm)
        self.ui.load_pages.subject_layout.addWidget(self.lineEdit_subject_id_confirm)
        self.ui.load_pages.subject_layout.addWidget(self.lineEdit_height_confirm)
        self.ui.load_pages.subject_layout.addWidget(self.lineEdit_weight_confirm)
        self.ui.load_pages.subject_layout.addWidget(self.lineEdit_age_confirm)

        self.ui.load_pages.verticalLayout.addWidget(self.stim_params_confirm_frame)

        self.ui.load_pages.task_info_layout.addWidget(self.lineEdit_task_confirm)

        self.ui.load_pages.save_layout.addWidget(self.lineEdit_save_info_confirm)

        self.ui.load_pages.channel_layout.setWidget(0, QFormLayout.ItemRole.FieldRole, self.lineEdit_channel_0_confirm)
        self.ui.load_pages.channel_layout.setWidget(1, QFormLayout.ItemRole.FieldRole, self.lineEdit_channel_1_confirm)
        self.ui.load_pages.channel_layout.setWidget(2, QFormLayout.ItemRole.FieldRole, self.lineEdit_channel_2_confirm)
        self.ui.load_pages.channel_layout.setWidget(3, QFormLayout.ItemRole.FieldRole, self.lineEdit_channel_3_confirm)
        self.ui.load_pages.channel_layout.setWidget(4, QFormLayout.ItemRole.FieldRole, self.lineEdit_channel_4_confirm)
        self.ui.load_pages.channel_layout.setWidget(5, QFormLayout.ItemRole.FieldRole, self.lineEdit_channel_5_confirm)
        self.ui.load_pages.channel_layout.setWidget(6, QFormLayout.ItemRole.FieldRole, self.lineEdit_channel_6_confirm)
        self.ui.load_pages.channel_layout.setWidget(7, QFormLayout.ItemRole.FieldRole, self.lineEdit_channel_7_confirm)

        self.ui.load_pages.confirm_cancel_layout.addWidget(self.confirm_btn)
        self.ui.load_pages.confirm_cancel_layout.addWidget(self.cancel_btn)

        # Change frame color
        self.ui.load_pages.subject_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.task_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.save_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.stimulation_frame.setStyleSheet(self.frame_stylesheet)

        # PAGE 7 - RESULT
        # ///////////////////////////////////////////////////////////////
        # PUSH BUTTON 1
        self.finish_btn_5: PyPushButton = SetupMainWindow.create_std_push_btn(self.themes, text="Finish")

        # BUTTON CLICKED
        def finish_result_clicked():
            # Delete line edits in result page
            for line_edit in self.ui.load_pages.phase_left_widget.children():
                if isinstance(line_edit, PyLineEdit):
                    line_edit.deleteLater()
            for line_edit in self.ui.load_pages.phase_right_widget.children():
                if isinstance(line_edit, PyLineEdit):
                    line_edit.deleteLater()
            for line_edit in self.ui.load_pages.subphase_left_widget.children():
                if isinstance(line_edit, PyLineEdit):
                    line_edit.deleteLater()
            for line_edit in self.ui.load_pages.subphase_right_widget.children():
                if isinstance(line_edit, PyLineEdit):
                    line_edit.deleteLater()

            # Load PAGE 1 and select the tab
            MainFunctions.set_page(self, self.ui.load_pages.page_10)
            self.ui.left_menu.select_only_one("btn_stimulation_2")

            # Renable menu buttons
            self.ui.left_menu.top_frame.setEnabled(True)

        # CONNECT BUTTONS
        self.finish_btn_5.clicked.connect(finish_result_clicked)

        # ADD WIDGETS
        self.ui.load_pages.finish_btn_layout_5.addWidget(self.finish_btn_5)

        # CHANGE FRAME COLOR
        self.ui.load_pages.left_leg_frame.setStyleSheet(self.frame_stylesheet)
        self.ui.load_pages.right_leg_frame.setStyleSheet(self.frame_stylesheet)

        # PAGE 8 - FSR SETUP
        # ///////////////////////////////////////////////////////////////

        # -------------------- BUTTONS --------------------
        self.scan_fsr_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Scan")
        self.scan_fsr_btn.setMinimumWidth(DROPDOWN_WIDTH)

        self.connect_left_fsr_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Connect Left FSR")
        self.connect_left_fsr_btn.setMinimumWidth(DROPDOWN_WIDTH)

        self.disconnect_left_fsr_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Disconnect Left FSR")
        self.disconnect_left_fsr_btn.setMinimumWidth(DROPDOWN_WIDTH)

        self.connect_right_fsr_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Connect Right FSR")
        self.connect_right_fsr_btn.setMinimumWidth(DROPDOWN_WIDTH)

        self.disconnect_right_fsr_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Disconnect Right FSR")
        self.disconnect_right_fsr_btn.setMinimumWidth(DROPDOWN_WIDTH)

        self.finish_btn_6 = SetupMainWindow.create_std_push_btn(self.themes, text="Finish")

        # -------------------- SPIN BOX --------------------
        self.fsr_threshold_left_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0, 500),
            value=20,
        )
        
        self.fsr_threshold_right_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0, 500),
            value=20,
        )

        # -------------------- CONNECTION CHECKBOXES --------------------
        self.left_connected_checkbox = QCheckBox("Left FSR Connected")
        self.left_connected_checkbox.setChecked(False)
        self.left_connected_checkbox.setEnabled(False)

        self.right_connected_checkbox = QCheckBox("Right FSR Connected")
        self.right_connected_checkbox.setChecked(False)
        self.right_connected_checkbox.setEnabled(False)

        # -------------------- LABELS --------------------
        self.fsr_threshold_left_label = QLabel("Left Threshold:")
        self.fsr_threshold_left_label.setStyleSheet("font-size: 12pt;")

        self.fsr_threshold_right_label = QLabel("Right Threshold:")
        self.fsr_threshold_right_label.setStyleSheet("font-size: 12pt;")

        # -------------------- VALUE DISPLAY --------------------
        # Status box (general messages)
        self.fsr_status_box = PyTextBrowser(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
        )
        self.fsr_status_box.setMinimumWidth(300)

        # FSR value displays
        self.ff_left_value = QLabel("0")
        self.mf_left_value = QLabel("0")
        self.bf_left_value = QLabel("0")

        self.ff_right_value = QLabel("0")
        self.mf_right_value = QLabel("0")
        self.bf_right_value = QLabel("0")

        # -------------------- BUTTON CONNECTIONS --------------------
        #self.scan_fsr_btn.clicked.connect(self.scan_fsr)

        self.connect_left_fsr_btn.clicked.connect(self.connect_left_fsr)
        self.disconnect_left_fsr_btn.clicked.connect(self.disconnect_left_fsr)

        self.connect_right_fsr_btn.clicked.connect(self.connect_right_fsr)
        self.disconnect_right_fsr_btn.clicked.connect(self.disconnect_right_fsr)

        self.finish_btn_6.clicked.connect(finish_btn_page3_to_setup)

        # -------------------- ADD WIDGETS TO LAYOUT --------------------
        # Status box and scan
        self.ui.load_pages.fsr_status_layout.addWidget(self.fsr_status_box, 0, 0, 3, 1)  # keep as 1 column span for half width
        self.ui.load_pages.fsr_status_layout.addWidget(self.scan_fsr_btn, 1, 1, 1, 1)  # move scan button left

        # Left FSR buttons (shift one column left)
        self.ui.load_pages.fsr_status_layout.addWidget(self.connect_left_fsr_btn, 1, 2, 1, 1)
        self.ui.load_pages.fsr_status_layout.addWidget(self.disconnect_left_fsr_btn, 2, 2, 1, 1)
        self.ui.load_pages.fsr_status_layout.addWidget(self.left_connected_checkbox, 3, 2, 1, 1)

        # Right FSR buttons (shift one column left)
        self.ui.load_pages.fsr_status_layout.addWidget(self.connect_right_fsr_btn, 1, 3, 1, 1)
        self.ui.load_pages.fsr_status_layout.addWidget(self.disconnect_right_fsr_btn, 2, 3, 1, 1)
        self.ui.load_pages.fsr_status_layout.addWidget(self.right_connected_checkbox, 3, 3, 1, 1)

        # Threshold (unchanged)
        self.ui.load_pages.fsr_status_layout.addWidget(self.fsr_threshold_left_label, 0, 4, 1, 1)
        self.ui.load_pages.fsr_status_layout.addWidget(self.fsr_threshold_left_spin_box, 1, 4, 1, 1)

        self.ui.load_pages.fsr_status_layout.addWidget(self.fsr_threshold_right_label, 0, 5, 1, 1)
        self.ui.load_pages.fsr_status_layout.addWidget(self.fsr_threshold_right_spin_box, 1, 5, 1, 1)

        # Value display (optional: can add a dedicated grid for better layout)
        #self.ui.load_pages.fsr_status_layout.addWidget(QLabel("FF Left:"), 4, 0)
        #self.ui.load_pages.fsr_status_layout.addWidget(self.ff_left_value, 4, 1)
        #self.ui.load_pages.fsr_status_layout.addWidget(QLabel("MF Left:"), 5, 0)
        #self.ui.load_pages.fsr_status_layout.addWidget(self.mf_left_value, 5, 1)
        #self.ui.load_pages.fsr_status_layout.addWidget(QLabel("BF Left:"), 6, 0)
        #self.ui.load_pages.fsr_status_layout.addWidget(self.bf_left_value, 6, 1)

        #self.ui.load_pages.fsr_status_layout.addWidget(QLabel("FF Right:"), 4, 2)
        #self.ui.load_pages.fsr_status_layout.addWidget(self.ff_right_value, 4, 3)
        #self.ui.load_pages.fsr_status_layout.addWidget(self.mf_right_value, 5, 3)
        #self.ui.load_pages.fsr_status_layout.addWidget(QLabel("BF Right:"), 6, 2)
        #self.ui.load_pages.fsr_status_layout.addWidget(self.bf_right_value, 6, 3)

        # Finish button
        self.ui.load_pages.finish_btn_layout_3.addWidget(self.finish_btn_6)


        # Change frame color
        self.ui.load_pages.fsr_frame.setStyleSheet(self.frame_stylesheet)

        # PAGE 9 - IMU SETUP
        # ///////////////////////////////////////////////////////////////
        self.process: subprocess.Popen = None
        self.plot_dialog = None  # Will be created when "Start Graph" is pressed

        # ── BUTTONS ──
        self.imu_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Open IMU GUI")
        self.imu_btn.setMinimumHeight(LINE_HEIGHT)
        self.imu_btn.setToolTip("Open the IMU GUI to connect to the IMU sensors.")

        self.calibrate_offset_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Calibrate Offsets")
        self.calibrate_offset_btn.setMinimumHeight(LINE_HEIGHT)
        self.calibrate_offset_btn.setToolTip("Calibrate the angle offset of the connected legs in neutral pose.")

        self.start_graph_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Start Graph")
        self.start_graph_btn.setMinimumHeight(LINE_HEIGHT)
        self.start_graph_btn.setToolTip("Open the real-time angle plot window.")

        self.finish_btn_7 = SetupMainWindow.create_std_push_btn(self.themes, text="Finish")

        # ── TOGGLES (all 6 independent) ──
        self.left_leg_toggle = PyToggleSmall(
            text="Left Leg",
            bg_color=self.themes["app_color"]["dark_two"],
            circle_color=self.themes["app_color"]["icon_color"],
            active_color=self.themes["app_color"]["context_color"],
        )
        self.right_leg_toggle = PyToggleSmall(
            text="Right Leg",
            bg_color=self.themes["app_color"]["dark_two"],
            circle_color=self.themes["app_color"]["icon_color"],
            active_color=self.themes["app_color"]["context_color"],
        )
        self.left_knee_toggle = PyToggleSmall(
            text="Left Knee",
            bg_color=self.themes["app_color"]["dark_two"],
            circle_color=self.themes["app_color"]["icon_color"],
            active_color=self.themes["app_color"]["context_color"],
        )
        self.right_knee_toggle = PyToggleSmall(
            text="Right Knee",
            bg_color=self.themes["app_color"]["dark_two"],
            circle_color=self.themes["app_color"]["icon_color"],
            active_color=self.themes["app_color"]["context_color"],
        )
        self.left_ankle_toggle = PyToggleSmall(
            text="Left Ankle",
            bg_color=self.themes["app_color"]["dark_two"],
            circle_color=self.themes["app_color"]["icon_color"],
            active_color=self.themes["app_color"]["context_color"],
        )
        self.right_ankle_toggle = PyToggleSmall(
            text="Right Ankle",
            bg_color=self.themes["app_color"]["dark_two"],
            circle_color=self.themes["app_color"]["icon_color"],
            active_color=self.themes["app_color"]["context_color"],
        )

        # ── STATUS BOX ──
        self.imu_status_box = QTextBrowser()
        self.imu_status_box.setStyleSheet(
            f"font-size: 9pt; background: {self.themes['app_color']['dark_one']}; "
            f"color: {self.themes['app_color']['text_foreground']}; border-radius: 4px;"
        )
        self.imu_status_box.setMaximumHeight(80)

        # ── KNEE PARAMETER WIDGETS ──
        lbl_style = f"font-size: 10pt; font-weight: bold; color: {self.themes['app_color']['text_foreground']};"
        lbl_sub_style = f"font-size: 9pt; color: {self.themes['app_color']['text_foreground']};"

        self.knee_header = QLabel("KNEE")
        self.knee_header.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {self.themes['app_color']['text_foreground']};")
        self.knee_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.invert_left_angle_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Invert L")
        self.invert_left_angle_btn.setMinimumHeight(LINE_HEIGHT)
        self.invert_right_angle_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Invert R")
        self.invert_right_angle_btn.setMinimumHeight(LINE_HEIGHT)

        self.scale_label = QLabel("Scale:")
        self.scale_label.setStyleSheet(lbl_sub_style)
        self.scale_left_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.1, 4.0), decimals=1, step_size=0.1, value=1.0,
        )
        self.scale_right_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.1, 4.0), decimals=1, step_size=0.1, value=1.0,
        )

        self.targets_label = QLabel("Targets (Ext. – Flex.):")
        self.targets_label.setStyleSheet(lbl_sub_style)
        self.extension_left_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(-30, 30), value=0,
        )
        self.flexion_left_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0, 120), value=60,
        )
        self.extension_right_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(-30, 30), value=0,
        )
        self.flexion_right_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0, 120), value=60,
        )

        self.pi_param_label = QLabel("PI (Kp – Ki):")
        self.pi_param_label.setStyleSheet(lbl_sub_style)
        self.pi_kp_left_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.0, 10.0), decimals=2, step_size=0.01, value=0.10,
        )
        self.pi_ki_left_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.0, 10.0), decimals=2, step_size=0.01, value=0.01,
        )
        self.pi_kp_right_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.0, 10.0), decimals=2, step_size=0.01, value=0.10,
        )
        self.pi_ki_right_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.0, 10.0), decimals=2, step_size=0.01, value=0.01,
        )

        # ── ANKLE PARAMETER WIDGETS ──
        self.ankle_header = QLabel("ANKLE")
        self.ankle_header.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {self.themes['app_color']['text_foreground']};")
        self.ankle_header.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.invert_left_ankle_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Invert L")
        self.invert_left_ankle_btn.setMinimumHeight(LINE_HEIGHT)
        self.invert_right_ankle_btn = SetupMainWindow.create_std_push_btn(self.themes, text="Invert R")
        self.invert_right_ankle_btn.setMinimumHeight(LINE_HEIGHT)

        self.ankle_scale_label = QLabel("Scale:")
        self.ankle_scale_label.setStyleSheet(lbl_sub_style)
        self.ankle_scale_left_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.1, 4.0), decimals=1, step_size=0.1, value=1.0,
        )
        self.ankle_scale_right_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.1, 4.0), decimals=1, step_size=0.1, value=1.0,
        )

        self.ankle_targets_label = QLabel("Targets (Dorsi. – Plant.):")
        self.ankle_targets_label.setStyleSheet(lbl_sub_style)
        self.dorsiflexion_left_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(-30, 30), value=-10,
        )
        self.plantarflexion_left_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(-30, 60), value=20,
        )
        self.dorsiflexion_right_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(-30, 30), value=-10,
        )
        self.plantarflexion_right_spin_box = PySpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(-30, 60), value=20,
        )

        self.ankle_pi_param_label = QLabel("PI (Kp – Ki):")
        self.ankle_pi_param_label.setStyleSheet(lbl_sub_style)
        self.ankle_pi_kp_left_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.0, 10.0), decimals=2, step_size=0.01, value=0.10,
        )
        self.ankle_pi_ki_left_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.0, 10.0), decimals=2, step_size=0.01, value=0.01,
        )
        self.ankle_pi_kp_right_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.0, 10.0), decimals=2, step_size=0.01, value=0.10,
        )
        self.ankle_pi_ki_right_spin_box = PyDoubleSpinBox(
            text_color=self.themes["app_color"]["text_foreground"],
            bg_color=self.themes["app_color"]["dark_one"],
            value_range=(0.0, 10.0), decimals=2, step_size=0.01, value=0.01,
        )

        # ── ANGLE CALIBRATOR ──
        self.angle_calibrator = AngleCalibrator(
            self.left_leg_toggle, self.right_leg_toggle,
            self.extension_left_spin_box, self.extension_right_spin_box, self
        )

        # ── CALLBACKS ──
        def open_imu_gui():
            if self.process is not None:
                retcode = self.process.poll()
                if retcode is None:
                    return
            self.process = subprocess.Popen(["./DeployDir/MovellaGUI"])

        def update_imu_status(status: str):
            """Show a normal message in the status box."""
            self.imu_status_box.append(status)

        def update_imu_error(status: str):
            """Show an error message in RED in the status box."""
            self.imu_status_box.append(f'<span style="color: #ff5555;">{status}</span>')

        def open_plot_dialog():
            """Create (or re-open) the floating plot window — only if sensors are connected."""
            if not self.angle_calibrator.has_any_sensor():
                update_imu_error("No sensors connected. Cannot start graph.")
                return

            if self.plot_dialog is None:
                self.plot_dialog = PlotDialog(self.angle_calibrator, self.themes, parent=self)
                # Wire toggles → plot visibility
                def _sync_knee_left(st):
                    self.plot_dialog.knee_plot.show_left_knee_angle(st == Qt.CheckState.Checked)
                def _sync_knee_right(st):
                    self.plot_dialog.knee_plot.show_right_knee_angle(st == Qt.CheckState.Checked)
                def _sync_ankle_left(st):
                    self.plot_dialog.ankle_plot.show_left_ankle_angle(st == Qt.CheckState.Checked)
                def _sync_ankle_right(st):
                    self.plot_dialog.ankle_plot.show_right_ankle_angle(st == Qt.CheckState.Checked)
                self.left_knee_toggle.checkStateChanged.connect(_sync_knee_left)
                self.right_knee_toggle.checkStateChanged.connect(_sync_knee_right)
                self.left_ankle_toggle.checkStateChanged.connect(_sync_ankle_left)
                self.right_ankle_toggle.checkStateChanged.connect(_sync_ankle_right)
                # ── Sync current toggle state immediately (toggles may already be ON) ──
                self.plot_dialog.knee_plot.show_left_knee_angle(self.left_knee_toggle.isChecked())
                self.plot_dialog.knee_plot.show_right_knee_angle(self.right_knee_toggle.isChecked())
                self.plot_dialog.ankle_plot.show_left_ankle_angle(self.left_ankle_toggle.isChecked())
                self.plot_dialog.ankle_plot.show_right_ankle_angle(self.right_ankle_toggle.isChecked())
                # Wire spin boxes → plot
                self.scale_left_spin_box.valueChanged.connect(lambda v: self.plot_dialog.knee_plot.set_scale_factor(v, LEFT))
                self.scale_right_spin_box.valueChanged.connect(lambda v: self.plot_dialog.knee_plot.set_scale_factor(v, RIGHT))
                self.extension_left_spin_box.valueChanged.connect(lambda v: self.plot_dialog.knee_plot.set_target_extension_angle(v, LEFT))
                self.flexion_left_spin_box.valueChanged.connect(lambda v: self.plot_dialog.knee_plot.set_target_flexion_angle(v, LEFT))
                self.extension_right_spin_box.valueChanged.connect(lambda v: self.plot_dialog.knee_plot.set_target_extension_angle(v, RIGHT))
                self.flexion_right_spin_box.valueChanged.connect(lambda v: self.plot_dialog.knee_plot.set_target_flexion_angle(v, RIGHT))
                self.ankle_scale_left_spin_box.valueChanged.connect(lambda v: self.plot_dialog.ankle_plot.set_scale_factor(v, LEFT))
                self.ankle_scale_right_spin_box.valueChanged.connect(lambda v: self.plot_dialog.ankle_plot.set_scale_factor(v, RIGHT))
                self.dorsiflexion_left_spin_box.valueChanged.connect(lambda v: self.plot_dialog.ankle_plot.set_target_dorsiflexion_angle(v, LEFT))
                self.plantarflexion_left_spin_box.valueChanged.connect(lambda v: self.plot_dialog.ankle_plot.set_target_plantarflexion_angle(v, LEFT))
                self.dorsiflexion_right_spin_box.valueChanged.connect(lambda v: self.plot_dialog.ankle_plot.set_target_dorsiflexion_angle(v, RIGHT))
                self.plantarflexion_right_spin_box.valueChanged.connect(lambda v: self.plot_dialog.ankle_plot.set_target_plantarflexion_angle(v, RIGHT))
                # Wire invert buttons
                self.invert_left_angle_btn.clicked.connect(lambda: self.plot_dialog.knee_plot.invert_angle(LEFT))
                self.invert_right_angle_btn.clicked.connect(lambda: self.plot_dialog.knee_plot.invert_angle(RIGHT))
                self.invert_left_ankle_btn.clicked.connect(lambda: self.plot_dialog.ankle_plot.invert_angle(LEFT))
                self.invert_right_ankle_btn.clicked.connect(lambda: self.plot_dialog.ankle_plot.invert_angle(RIGHT))
            self.plot_dialog.start()

        # ── Toggle callbacks ──
        def left_leg_state_changed(state: Qt.CheckState):
            show: bool = state == Qt.CheckState.Checked
            self.angle_calibrator.handle_left_inlet(show)

        def right_leg_state_changed(state: Qt.CheckState):
            show: bool = state == Qt.CheckState.Checked
            self.angle_calibrator.handle_right_inlet(show)

        def left_knee_state_changed(state: Qt.CheckState):
            if state == Qt.CheckState.Checked:
                cal = self.angle_calibrator
                if cal.left_shank_inlet and cal.left_thigh_inlet:
                    update_imu_status("Left Knee: sensors connected (Thigh + Shank).")
                else:
                    update_imu_error("Left Knee: Thigh or Shank sensor not connected. Enable Left Leg first.")
                    self.left_knee_toggle.setChecked(False)

        def right_knee_state_changed(state: Qt.CheckState):
            if state == Qt.CheckState.Checked:
                cal = self.angle_calibrator
                if cal.right_shank_inlet and cal.right_thigh_inlet:
                    update_imu_status("Right Knee: sensors connected (Thigh + Shank).")
                else:
                    update_imu_error("Right Knee: Thigh or Shank sensor not connected. Enable Right Leg first.")
                    self.right_knee_toggle.setChecked(False)

        def left_ankle_state_changed(state: Qt.CheckState):
            if state == Qt.CheckState.Checked:
                cal = self.angle_calibrator
                if cal.left_shank_inlet and cal.left_foot_inlet:
                    update_imu_status("Left Ankle: sensors connected (Shank + Foot).")
                else:
                    update_imu_error("Left Ankle: Shank or Foot sensor not connected. Enable Left Leg first.")
                    self.left_ankle_toggle.setChecked(False)

        def right_ankle_state_changed(state: Qt.CheckState):
            if state == Qt.CheckState.Checked:
                cal = self.angle_calibrator
                if cal.right_shank_inlet and cal.right_foot_inlet:
                    update_imu_status("Right Ankle: sensors connected (Shank + Foot).")
                else:
                    update_imu_error("Right Ankle: Shank or Foot sensor not connected. Enable Right Leg first.")
                    self.right_ankle_toggle.setChecked(False)

        # ── CONNECT BUTTONS ──
        self.imu_btn.clicked.connect(open_imu_gui)
        self.calibrate_offset_btn.clicked.connect(self.angle_calibrator.calibration)
        self.start_graph_btn.clicked.connect(open_plot_dialog)
        self.left_leg_toggle.checkStateChanged.connect(left_leg_state_changed)
        self.right_leg_toggle.checkStateChanged.connect(right_leg_state_changed)
        self.left_knee_toggle.checkStateChanged.connect(left_knee_state_changed)
        self.right_knee_toggle.checkStateChanged.connect(right_knee_state_changed)
        self.left_ankle_toggle.checkStateChanged.connect(left_ankle_state_changed)
        self.right_ankle_toggle.checkStateChanged.connect(right_ankle_state_changed)
        self.finish_btn_7.clicked.connect(finish_btn_clicked)

        # CONNECT SIGNALS
        self.angle_calibrator.message_signal.connect(update_imu_status)
        self.angle_calibrator.error_signal.connect(update_imu_error)
        # Diagnostic signal: HTML content, so we use insertHtml directly
        self.angle_calibrator.diagnostic_signal.connect(
            lambda html: (
                self.imu_status_box.append(""),          # blank line separator
                self.imu_status_box.insertHtml(html),
            )
        )
        # Calibration done: insert prominent banner AND scroll to bottom so it's always visible
        self.angle_calibrator.calibration_done_signal.connect(
            lambda html: (
                self.imu_status_box.append(""),
                self.imu_status_box.insertHtml(html),
                self.imu_status_box.verticalScrollBar().setValue(
                    self.imu_status_box.verticalScrollBar().maximum()
                ),
            )
        )

        # Axis diagnostic: open a dedicated, persistent popup window
        def _show_axis_diagnostic(html_content: str):
            """Open a non-modal dialog showing the full sensor axis diagnostic."""
            import os
            from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                           QTextBrowser, QPushButton, QFileDialog, QLabel)
            from PySide6.QtCore import Qt

            dlg = QDialog(self)
            dlg.setWindowTitle("📐 Sensor Axis Diagnostic — Calibration Report")
            dlg.setMinimumSize(780, 520)
            dlg.setStyleSheet("""
                QDialog        { background: #1e1f26; color: #ecf0f1; }
                QTextBrowser   { background: #16171e; color: #ecf0f1;
                                 border: 1px solid #3d4059; border-radius: 6px;
                                 font-family: 'Consolas','Courier New',monospace; font-size: 12px; }
                QPushButton    { background: #2c3e50; color: #ecf0f1; border: none;
                                 border-radius: 5px; padding: 6px 16px; font-size: 12px; }
                QPushButton:hover { background: #3d5166; }
                QPushButton#close_btn { background: #8e44ad; }
                QPushButton#close_btn:hover { background: #9b59b6; }
                QPushButton#save_btn { background: #27ae60; }
                QPushButton#save_btn:hover { background: #2ecc71; }
                QLabel         { color: #bdc3c7; font-size: 11px; padding: 4px; }
            """)

            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

            # Instructions label
            lbl = QLabel(
                "<b>How to read:</b>  "
                "<span style='color:#2ecc71'>Vertical ↕ close to 1.0</span> = axis aligned with gravity.  "
                "<span style='color:#3498db'>Horizontal ↔ close to 1.0</span> = axis along the floor (along foot).  "
                "The correct ankle axis is the Foot axis with the highest Horizontal score."
            )
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

            # Main text browser
            browser = QTextBrowser()
            browser.setOpenExternalLinks(False)
            browser.setHtml(html_content)
            layout.addWidget(browser)

            # Button row
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)

            save_btn = QPushButton("💾  Save report to file…")
            save_btn.setObjectName("save_btn")
            def _save_report():
                path, _ = QFileDialog.getSaveFileName(
                    dlg, "Save Axis Diagnostic",
                    os.path.join(os.path.expanduser("~"), "Desktop",
                                 "axis_diagnostic.html"),
                    "HTML Files (*.html);;Text Files (*.txt)"
                )
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        if path.endswith(".txt"):
                            import re
                            f.write(re.sub(r'<[^>]+>', '', html_content))
                        else:
                            f.write(f"<html><body style='background:#1e1f26; color:#ecf0f1;"
                                    f" font-family:monospace; padding:16px;'>{html_content}</body></html>")
            save_btn.clicked.connect(_save_report)

            close_btn = QPushButton("✕  Close")
            close_btn.setObjectName("close_btn")
            close_btn.clicked.connect(dlg.close)

            btn_row.addWidget(save_btn)
            btn_row.addStretch()
            btn_row.addWidget(close_btn)
            layout.addLayout(btn_row)

            dlg.setWindowModality(Qt.NonModal)
            dlg.show()   # non-blocking, stays open until user closes it

        self.angle_calibrator.axis_diagnostic_signal.connect(_show_axis_diagnostic)

        # Live offset update: if a test is currently running, push new offsets
        # immediately to the running stimulation object so they take effect
        # without restarting the test.
        def _push_live_offsets(_html: str = "") -> None:
            try:
                stim = getattr(self.experiment_handler, "stimulator", None)
            except AttributeError:
                return
            if stim is None:
                return
            try:
                kl, kr = self.angle_calibrator.get_offset()
                al, ar = self.angle_calibrator.get_ankle_offset()
                stim.update_offsets(kl, kr, al, ar)
                self.imu_status_box.append(
                    '<span style="color:#2ecc71">✔ Offsets updated live in running test.</span>'
                )
            except Exception as e:
                print(f"[live offset update] {e}")

        self.angle_calibrator.calibration_done_signal.connect(_push_live_offsets)

        # ============================================================
        # POPULATE LAYOUT
        # ============================================================

        # ── Toggle bar ──
        tbar = self.ui.load_pages.toggle_bar_layout
        tbar.addStretch(1)
        tbar.addWidget(self.left_leg_toggle)
        tbar.addWidget(self.right_leg_toggle)
        tbar.addWidget(self.left_knee_toggle)
        tbar.addWidget(self.right_knee_toggle)
        tbar.addWidget(self.left_ankle_toggle)
        tbar.addWidget(self.right_ankle_toggle)
        tbar.addStretch(1)

        # ── Button bar ──
        bbar = self.ui.load_pages.btn_bar_layout
        bbar.addStretch(1)
        bbar.addWidget(self.imu_btn)
        bbar.addWidget(self.calibrate_offset_btn)
        bbar.addWidget(self.start_graph_btn)
        bbar.addStretch(1)

        # ── Status box ──
        self.ui.load_pages.status_layout.addWidget(self.imu_status_box)

        # ── Knee parameters grid ──
        kg = self.ui.load_pages.knee_params_layout
        kg.addWidget(self.knee_header,             0, 0, 1, 4)
        kg.addWidget(self.invert_left_angle_btn,   1, 0, 1, 2)
        kg.addWidget(self.invert_right_angle_btn,  1, 2, 1, 2)
        #
        lbl_l = QLabel("Left")
        lbl_l.setStyleSheet(lbl_sub_style)
        lbl_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_r = QLabel("Right")
        lbl_r.setStyleSheet(lbl_sub_style)
        lbl_r.setAlignment(Qt.AlignmentFlag.AlignCenter)
        kg.addWidget(lbl_l,                        2, 1, 1, 1)
        kg.addWidget(lbl_r,                        2, 2, 1, 1)
        #
        kg.addWidget(self.scale_label,             3, 0, 1, 1)
        kg.addWidget(self.scale_left_spin_box,     3, 1, 1, 1)
        kg.addWidget(self.scale_right_spin_box,    3, 2, 1, 1)
        #
        kg.addWidget(self.targets_label,           4, 0, 1, 1)
        kg.addWidget(self.extension_left_spin_box, 4, 1, 1, 1)
        kg.addWidget(self.extension_right_spin_box,4, 2, 1, 1)
        kg.addWidget(self.flexion_left_spin_box,   5, 1, 1, 1)
        kg.addWidget(self.flexion_right_spin_box,  5, 2, 1, 1)
        #
        kg.addWidget(self.pi_param_label,          6, 0, 1, 1)
        kg.addWidget(self.pi_kp_left_spin_box,     6, 1, 1, 1)
        kg.addWidget(self.pi_kp_right_spin_box,    6, 2, 1, 1)
        kg.addWidget(self.pi_ki_left_spin_box,     7, 1, 1, 1)
        kg.addWidget(self.pi_ki_right_spin_box,    7, 2, 1, 1)

        # ── Ankle parameters grid ──
        ag = self.ui.load_pages.ankle_params_layout
        ag.addWidget(self.ankle_header,                0, 0, 1, 4)
        ag.addWidget(self.invert_left_ankle_btn,       1, 0, 1, 2)
        ag.addWidget(self.invert_right_ankle_btn,      1, 2, 1, 2)
        #
        lbl_la = QLabel("Left")
        lbl_la.setStyleSheet(lbl_sub_style)
        lbl_la.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_ra = QLabel("Right")
        lbl_ra.setStyleSheet(lbl_sub_style)
        lbl_ra.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ag.addWidget(lbl_la,                           2, 1, 1, 1)
        ag.addWidget(lbl_ra,                           2, 2, 1, 1)
        #
        ag.addWidget(self.ankle_scale_label,           3, 0, 1, 1)
        ag.addWidget(self.ankle_scale_left_spin_box,   3, 1, 1, 1)
        ag.addWidget(self.ankle_scale_right_spin_box,  3, 2, 1, 1)
        #
        ag.addWidget(self.ankle_targets_label,         4, 0, 1, 1)
        ag.addWidget(self.dorsiflexion_left_spin_box,  4, 1, 1, 1)
        ag.addWidget(self.dorsiflexion_right_spin_box, 4, 2, 1, 1)
        ag.addWidget(self.plantarflexion_left_spin_box, 5, 1, 1, 1)
        ag.addWidget(self.plantarflexion_right_spin_box,5, 2, 1, 1)
        #
        ag.addWidget(self.ankle_pi_param_label,        6, 0, 1, 1)
        ag.addWidget(self.ankle_pi_kp_left_spin_box,   6, 1, 1, 1)
        ag.addWidget(self.ankle_pi_kp_right_spin_box,  6, 2, 1, 1)
        ag.addWidget(self.ankle_pi_ki_left_spin_box,   7, 1, 1, 1)
        ag.addWidget(self.ankle_pi_ki_right_spin_box,  7, 2, 1, 1)

        # ── Finish ──
        self.ui.load_pages.finish_btn_layout_6.addWidget(self.finish_btn_7)

        # # RIGHT COLUMN
        # # ///////////////////////////////////////////////////////////////

        # # BTN 1
        # self.right_btn_1 = PyPushButton(
        #     text="Show Menu 2",
        #     radius=8,
        #     color=self.themes["app_color"]["text_foreground"],
        #     bg_color=self.themes["app_color"]["dark_one"],
        #     bg_color_hover=self.themes["app_color"]["dark_three"],
        #     bg_color_pressed=self.themes["app_color"]["dark_four"],
        # )
        # self.icon_right = QIcon(Functions.set_svg_icon("icon_arrow_right.svg"))
        # self.right_btn_1.setIcon(self.icon_right)
        # self.right_btn_1.setMaximumHeight(40)
        # self.right_btn_1.clicked.connect(lambda: MainFunctions.set_right_column_menu(self, self.ui.right_column.menu_2))
        # self.ui.right_column.btn_1_layout.addWidget(self.right_btn_1)

        # # BTN 2
        # self.right_btn_2 = PyPushButton(
        #     text="Show Menu 1",
        #     radius=8,
        #     color=self.themes["app_color"]["text_foreground"],
        #     bg_color=self.themes["app_color"]["dark_one"],
        #     bg_color_hover=self.themes["app_color"]["dark_three"],
        #     bg_color_pressed=self.themes["app_color"]["dark_four"],
        # )
        # self.icon_left = QIcon(Functions.set_svg_icon("icon_arrow_left.svg"))
        # self.right_btn_2.setIcon(self.icon_left)
        # self.right_btn_2.setMaximumHeight(40)
        # self.right_btn_2.clicked.connect(lambda: MainFunctions.set_right_column_menu(self, self.ui.right_column.menu_1))
        # self.ui.right_column.btn_2_layout.addWidget(self.right_btn_2)

        # ///////////////////////////////////////////////////////////////
        # END - WIDGETS
        # ///////////////////////////////////////////////////////////////

    # RESIZE GRIPS AND CHANGE POSITION
    # Resize or change position when window is resized
    # ///////////////////////////////////////////////////////////////
    def resize_grips(self):
        if self.settings["custom_title_bar"]:
            self.left_grip.setGeometry(5, 10, 10, self.height())
            self.right_grip.setGeometry(self.width() - 15, 10, 10, self.height())
            self.top_grip.setGeometry(5, 5, self.width() - 10, 10)
            self.bottom_grip.setGeometry(5, self.height() - 15, self.width() - 10, 10)
            self.top_right_grip.setGeometry(self.width() - 20, 5, 15, 15)
            self.bottom_left_grip.setGeometry(5, self.height() - 20, 15, 15)
            self.bottom_right_grip.setGeometry(self.width() - 20, self.height() - 20, 15, 15)

    # WIDGET CREATE FUNCTIONS
    # ///////////////////////////////////////////////////////////////
    @staticmethod
    def create_std_line_edit(theme: dict, text: str = "", place_holder_text: str = "") -> PyLineEdit:
        line_edit = PyLineEdit(
            text=text,
            place_holder_text=place_holder_text,
            radius=8,
            border_size=2,
            color=theme["app_color"]["text_foreground"],
            selection_color=theme["app_color"]["white"],
            bg_color=theme["app_color"]["dark_one"],
            bg_color_active=theme["app_color"]["dark_three"],
            context_color=theme["app_color"]["context_color"],
        )
        line_edit.setMinimumHeight(LINE_HEIGHT)
        line_edit.setMaximumWidth(LINE_WIDTH)
        line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return line_edit

    @staticmethod
    def create_std_push_btn(theme: dict, text: str = "Push Button") -> PyPushButton:
        push_btn = PyPushButton(
            text=text,
            radius=8,
            color=theme["app_color"]["text_foreground"],
            bg_color=theme["app_color"]["dark_one"],
            bg_color_hover=theme["app_color"]["dark_three"],
            bg_color_pressed=theme["app_color"]["dark_four"],
        )
        push_btn.setMinimumHeight(BUTTON_HEIGHT)
        push_btn.setMaximumWidth(BUTTON_WIDTH)
        return push_btn

    @staticmethod
    def create_std_dropdown_btn(theme: dict, actions: list[QAction], text: str = "Dropdown Button") -> PyDropDownButton:
        dropdown_btn = PyDropDownButton(
            text=text,
            radius=8,
            color=theme["app_color"]["text_foreground"],
            bg_color=theme["app_color"]["dark_one"],
            bg_color_hover=theme["app_color"]["dark_three"],
            bg_color_pressed=theme["app_color"]["dark_four"],
            actions=actions,
        )
        # dropdown_btn.setMinimumHeight(BUTTON_HEIGHT)
        dropdown_btn.setMinimumWidth(BUTTON_WIDTH)
        return dropdown_btn

    @staticmethod
    def create_std_small_toggle(theme: dict, text: str = "Small Toggle") -> PyToggleSmall:
        small_toggle = PyToggleSmall(
            text=text,
            bg_color=theme["app_color"]["dark_two"],
            circle_color=theme["app_color"]["icon_color"],
            active_color=theme["app_color"]["context_color"],
            text_color=theme["app_color"]["text_foreground"],
            text_disabled_color=theme["app_color"]["dark_four"],
            bg_color_disabled=theme["app_color"]["bg_one"],
            text_color_active=theme["app_color"]["text_active"],
        )
        return small_toggle

    @staticmethod
    def create_std_radio_btn(theme: dict, text: str = "Radio Button") -> PyRadioButton:
        radio_btn = PyRadioButton(
            text=text,
            text_color=theme["app_color"]["text_foreground"],
            active_color=theme["app_color"]["text_active"],
            disabled_color=theme["app_color"]["dark_four"],
        )
        return radio_btn

    # EDIT FUNCTIONS
    # ///////////////////////////////////////////////////////////////
    @staticmethod
    def create_file_name(format: str, subj_info_input: dict[str, PyLineEdit], format_btns: list[PyDropDownButton]) -> str:
        # Create model subject information
        mustermann = {
            "first_name": "Max",
            "last_name": "Mustermann",
            "subject_id": "001",
            "custom_text": "high_frequency_gait_stimulation",
            "task": "task1",
            "file_type": "pkl",
        }

        subj_info = {"---": ""}

        # Get the information from page 4, fill with default values if empty
        subj_info["first_name"] = subj_info_input["first_name"].text() if subj_info_input["first_name"].text() else mustermann["first_name"]
        subj_info["last_name"] = subj_info_input["last_name"].text() if subj_info_input["last_name"].text() else mustermann["last_name"]
        subj_info["subject_id"] = subj_info_input["subject_id"].text() if subj_info_input["subject_id"].text() else mustermann["subject_id"]

        # Get the current time
        subj_info["time"] = QDateTime.currentDateTime().toString("yyyy-MM-dd_hh-mm-ss")

        # Get the task, only take the part before a dash if present
        task_text = subj_info_input["task"].text()
        if task_text:
            task_text = task_text.split("-")[0].strip()
            subj_info["task"] = task_text.lower().replace(" ", "_")
        else:
            subj_info["task"] = mustermann["task"]

        # Get the initials
        subj_info["initials"] = subj_info["first_name"][0] + subj_info["last_name"][0]

        # Get the custom text
        subj_info["custom_text"] = (
            subj_info_input["custom_text"].text() if subj_info_input["custom_text"].text() else mustermann["custom_text"]
        )

        # Get file type
        subj_info["file_type"] = "pkl"

        # Create the file name
        if format == "SubjID-Time":
            return f"{subj_info['subject_id']}-{subj_info['time']}.{subj_info['file_type']}"
        elif format == "Task-SubjID-Time":
            return f"{subj_info['task']}-{subj_info['subject_id']}-{subj_info['time']}.{subj_info['file_type']}"
        elif format == "Initials-Task-SubjID-Time":
            return f"{subj_info['initials']}-{subj_info['task']}-{subj_info['subject_id']}-{subj_info['time']}.{subj_info['file_type']}"
        elif format == "CustomText-SubjID-Time":
            return f"{subj_info['custom_text']}-{subj_info['subject_id']}-{subj_info['time']}.{subj_info['file_type']}"
        elif format == "CustomText-SubjID":
            return f"{subj_info['custom_text']}-{subj_info['subject_id']}.{subj_info['file_type']}"
        elif format == "CustomLayout":
            formatted_string = ""
            for selection in format_btns:
                if selection.text() != "---":
                    formatted_string = formatted_string + subj_info[selection.text().lower().replace(" ", "_")] + "-"
            formatted_string = formatted_string[:-1] + "." + subj_info["file_type"]  # Remove the last '-' character and add the file type

            return formatted_string
        else:
            return ""

    @staticmethod
    def load_back_image(arrangement: str, task_path: str, btn_chan_connection: list[PyDropDownButton], back_image: QSvgWidget) -> None:
        # Depending on task type, override modified_image.svg with the correct back image (of electrode arrangement)
        if arrangement == "No Electrodes":
            svg_name = "electrode_arrangement_none.svg"
        elif arrangement == "Singlesite":
            svg_name = "electrode_arrangement_one_mid.svg"
        elif arrangement == "Three Electrodes":
            svg_name = "electrode_arrangement_three_mid.svg"
        elif arrangement == "Four Electrodes":
            svg_name = "electrode_arrangement_four_mid.svg"
        elif arrangement == "Multisite - Six Electrodes":
            svg_name = "electrode_arrangement_six.svg"
        elif arrangement == "Multisite - Eight Electrodes":
            svg_name = "electrode_arrangement_eight.svg"
        elif arrangement == "Combination - Seven Electrodes":
            svg_name = "electrode_arrangement_seven.svg"
            
        # Accept the FES label as alias for the 8-electrode arrangement
        elif arrangement == "FES - 8 Electrodes" or arrangement.strip().lower() == "fes - 8 electrodes":
            svg_name = "FES_arrangment_8_electodes.svg" 
            
        elif arrangement == "FES - No Stimulation":
            svg_name = "FES_arrangment_no_electodes.svg"

        # Lock the dropdown buttons depending on the number of electrodes
        for btn in btn_chan_connection:
            btn.setEnabled(False)

        # Open the json file tasks.json in the root folder
        with open(task_path, "r") as file:
            task_definitions: dict = json.load(file)

        #enabled_buttons: list[int] = task_definitions[arrangement]["buttons"]
        
        # Resolve buttons entry defensively: prefer exact key, then try common fallbacks
        enabled_buttons: list[int] = []
        try:
            if arrangement in task_definitions and "buttons" in task_definitions[arrangement]:
                enabled_buttons = task_definitions[arrangement]["buttons"]
            else:
                # try sensible fallbacks (tolerate aliases like "FES - 8 Electrodes")
                for fallback in ("FES - 8 Electrodes", "Multisite - Eight Electrodes", "Multisite - Six Electrodes"):
                    if fallback in task_definitions and "buttons" in task_definitions[fallback]:
                        enabled_buttons = task_definitions[fallback]["buttons"]
                        break
        except Exception:
            enabled_buttons = []

        for value in enabled_buttons:
            btn_chan_connection[value].setEnabled(True)

        # Override modified_image.svg with task image
        change_number_to(Functions.set_svg_image(svg_name), 0, 0)

        # Load the new image and set aspect ratio
        back_image.load(Functions.set_svg_image("modified_image.svg"))
        back_image.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

    def load_back_image_page10(arrangement:str, back_image: QSvgWidget) -> None:
        # Depending on task type, override modified_image.svg with the correct back image (of electrode arrangement)
        if arrangement == "No Electrodes":
            svg_name = "electrode_arrangement_none.svg"
        elif arrangement == "Singlesite":
            svg_name = "electrode_arrangement_one_mid.svg"
        elif arrangement == "Three Electrodes":
            svg_name = "electrode_arrangement_three_mid.svg"
        elif arrangement == "Four Electrodes":
            svg_name = "electrode_arrangement_four_mid.svg"
        elif arrangement == "Multisite - Six Electrodes":
            svg_name = "electrode_arrangement_six.svg"
        elif arrangement == "Multisite - Eight Electrodes":
            svg_name = "electrode_arrangement_eight.svg"
        elif arrangement == "Combination - Seven Electrodes":
            svg_name = "electrode_arrangement_seven.svg"
        
        elif arrangement == "FES - 8 Electrodes" or arrangement.strip().lower() == "fes - 8 electrodes":
            svg_name = "electrode_arrangement_eight.svg" 
            
        elif arrangement == "FES - No Stimulation":
            svg_name = "FES_arrangment_no_electodes.svg"
        
        # Override modified_image.svg with task image
        change_number_to(Functions.set_svg_image(svg_name), 0, 0)

        # Load the new image and set aspect ratio
        back_image.load(Functions.set_svg_image("modified_image.svg"))
        back_image.renderer().setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)


    @staticmethod
    def update_confirm_page(
        line_edit_dict: dict[PyLineEdit, PyLineEdit | list[PyLineEdit]],
    ):
        for line_edit_confirm, line_edit in line_edit_dict.items():
            if isinstance(line_edit, list):
                # This is the save path and file name
                line_edit_confirm.setText(line_edit[0].text() + "\\" + line_edit[1].text())
            else:
                # This is for all the other information
                line_edit_confirm.setText(line_edit.text())

    @staticmethod
    def get_placement_buttons(task_path: str, placement: str) -> list:
        # Open the json file tasks.json in the root folder
        with open(task_path, "r") as file:
            task_definitions: dict = json.load(file)

        # The value of the position key is the index of the button
        #return task_definitions[placement]["buttons"]
        # Resolve placement defensively: return buttons list or empty list if not found
        if placement in task_definitions and "buttons" in task_definitions[placement]:
            return task_definitions[placement]["buttons"]
        # common fallbacks
        for fallback in ("FES - 8 Electrodes", "Multisite - Eight Electrodes", "Multisite - Six Electrodes"):
            if fallback in task_definitions and "buttons" in task_definitions[fallback]:
                return task_definitions[fallback]["buttons"]
        # If nothing found, return empty list (caller already guards against length==0)
        return []


    @staticmethod
    def create_dict(
        main_window: QMainWindow,
        parameters: StimulatorParameters,
    ) -> dict:
        
        # # Get the targets (Page 5 default)
        # # Helper to safely parse an int channel index from a dropdown widget's text
        # import re
        # def _parse_hw_index(widget) -> int | None:
        #     if widget is None:
        #         return None
        #     try:
        #         txt = str(widget.text()).strip()
        #     except Exception:
        #         return None
        #     if not txt:
        #         return None
        #     # find last integer in the text
        #     m = re.findall(r"-?\d+", txt)
        #     if not m:
        #         return None
        #     try:
        #         return int(m[-1])
        #     except Exception:
        #         return None

        # # Build per-mode maps (values are int hw channel indices or None)
        # fes_map = {
        #     "TA_left":  _parse_hw_index(getattr(main_window, "dropdown_btn_target_1", None)),
        #     "TA_right": _parse_hw_index(getattr(main_window, "dropdown_btn_target_2", None)),
        #     "GA_left":  _parse_hw_index(getattr(main_window, "dropdown_btn_target_3", None)),
        #     "GA_right": _parse_hw_index(getattr(main_window, "dropdown_btn_target_4", None)),
        #     "VM_left":  _parse_hw_index(getattr(main_window, "dropdown_btn_target_5", None)),
        #     "VM_right": _parse_hw_index(getattr(main_window, "dropdown_btn_target_6", None)),
        #     "BF_left":  _parse_hw_index(getattr(main_window, "dropdown_btn_target_7", None)),
        #     "BF_right": _parse_hw_index(getattr(main_window, "dropdown_btn_target_8", None)),
        # }

        # tscs_map = {
        #     "full_leg_left":  _parse_hw_index(getattr(main_window, "dropdown_btn_target_1", None)),
        #     "full_leg_right": _parse_hw_index(getattr(main_window, "dropdown_btn_target_2", None)),
        #     "proximal_left":  _parse_hw_index(getattr(main_window, "dropdown_btn_target_3", None)),
        #     "proximal_right": _parse_hw_index(getattr(main_window, "dropdown_btn_target_4", None)),
        #     "distal_left":    _parse_hw_index(getattr(main_window, "dropdown_btn_target_5", None)),
        #     "distal_right":   _parse_hw_index(getattr(main_window, "dropdown_btn_target_6", None)),
        #     "continuous":     _parse_hw_index(getattr(main_window, "dropdown_btn_target_7", None)),
        # }

        # # Decide active mapping depending on toggles
        # fes_on = bool(getattr(main_window, "fes_toggle", None) and main_window.fes_toggle.isChecked())
        # tscs_on = bool(getattr(main_window, "tscs_toggle", None) and main_window.tscs_toggle.isChecked())

        # # Build a normalized channels dict: target_name -> int(hw_index)
        # channels: dict[str, int] = {}

        # if fes_on and not tscs_on:
        #     for k, v in fes_map.items():
        #         if v is not None:
        #             channels[k] = v
        # elif tscs_on and not fes_on:
        #     for k, v in tscs_map.items():
        #         if v is not None:
        #             channels[k] = v
        # elif fes_on and tscs_on:
        #     used_hw: set[int] = set()
        #     # Add FES first (priority)
        #     for k, v in fes_map.items():
        #         if v is None:
        #             continue
        #         if v in used_hw:
        #             print(f"WARNING: duplicate HW index {v} for FES target {k}")
        #             continue
        #         channels[k] = v
        #         used_hw.add(v)
        #     # Add tSCS only when hw slot not used
        #     for k, v in tscs_map.items():
        #         if v is None:
        #             continue
        #         if v in used_hw:
        #             # conflict: skip tSCS assignment (FES has precedence)
        #             print(f"DEBUG: hybrid conflict - HW {v} already used by FES, skipping tSCS target {k}")
        #             continue
        #         channels[k] = v
        #         used_hw.add(v)
        # else:
        #     # neither toggle: empty mapping
        #     channels = {}

        channels: dict[str, int] = {}
        page10_ch_curr: dict[int, str] = {}
        page10_override: dict[str, int] = {}
        currents: dict[str, int] = {}
        max_currents: dict[str, int] = {}
        not_in_use: list = []
        
        # Prefer Page 10 target->channel overrides
        page10_override: dict[str, int] = {}
        if hasattr(main_window, "page10_target_sel"):
            # Build target->channel from Page 10 rows
            for row_idx, btn in getattr(main_window, "page10_target_sel", {}).items():
                try:
                    lbl = btn.text().strip()
                    if not lbl or lbl == "Not to be used":
                        continue
                    key = getattr(main_window, "page10_target_key_map", {}).get(lbl)
                    if not key:
                        print(f"DEBUG: no target key for label '{lbl}' at row {row_idx}")
                        continue
                    hw_ch = int(getattr(main_window, "page10_row_channel_map", {}).get(row_idx, row_idx))
                    page10_override[key] = hw_ch
                except Exception as e:
                    print(f"DEBUG: page10 target mapping err row={row_idx}: {e}")
                    continue
        print("DEBUG: computed page10_override:", page10_override)
        if page10_override:
            channels = page10_override.copy()

        # Build a Channel->current map directly from Page 10 (primary source)
        page10_ch_curr: dict[int, str] = {}
        try:
            row_map = getattr(main_window, "page10_row_channel_map", {}) or {}
            for row_idx, editor in getattr(main_window, "page10_curr_opt", {}).items():
                try:
                    ch = int(row_map.get(row_idx, row_idx))
                    val = editor.text().strip()
                    if val and ch not in page10_ch_curr:
                        page10_ch_curr[ch] = val
                except Exception:
                    continue
        except Exception:
            page10_ch_curr = {}

        currents: dict = {}
        max_currents: dict = {}
        not_in_use: list = []

        # Create channel and current dictionaries (prefer Page 10 current)
        import re
        for key, value in list(channels.items()):
            try:
                ch_idx = int(value)
                channels[key] = ch_idx
                ch_label = f"Channel {ch_idx}"

                # 1) Page 10: prefer per-row current for this exact target (handles multiple targets on same HW channel)
                ch_text = ""
                try:
                    for row_idx, btn in getattr(main_window, "page10_target_sel", {}).items():
                        if not btn:
                            continue
                        lbl = btn.text().strip()
                        tgt_key = getattr(main_window, "page10_target_key_map", {}).get(lbl, lbl)
                        if tgt_key == key:
                            editor = getattr(main_window, "page10_curr_opt", {}).get(row_idx)
                            if editor:
                                ch_text = editor.text().strip()
                                break
                except Exception:
                    ch_text = page10_ch_curr.get(ch_idx, "").strip()
                if not ch_text:
                    ch_text = page10_ch_curr.get(ch_idx, "").strip()


                # 2) Confirmation page (if available)
                if not ch_text:
                    try:
                        confirm = getattr(main_window, f"lineEdit_channel_{ch_idx}_confirm", None)
                        if confirm:
                            ch_text = confirm.text().strip()
                    except Exception:
                        pass

                # 3) Page 5 line edit
                if not ch_text:
                    try:
                        ch_text = main_window.channel_dict[ch_label].text().strip()
                    except Exception:
                        ch_text = ""

                # Parse digits or fallback to initial_current
                try:
                    if ch_text == "":
                        raise ValueError("empty")
                    m = re.search(r"-?\d+", ch_text)
                    if not m:
                        raise ValueError("no digits")
                    currents[key] = int(m.group(0))
                except Exception:
                    print(f"DEBUG: missing/non-numeric current for {ch_label} (raw='{ch_text}'), using initial_current={parameters.initial_current}")
                    currents[key] = int(parameters.initial_current)

                # Max current: Page 5 max field or same as current
                try:
                    max_currents[key] = int(main_window.channel_max_dict[ch_label].text())
                except Exception:
                    max_currents[key] = currents[key]

            except ValueError:
                # Remove if "Not in use"
                not_in_use.append(key)

        # Remove unused targets
        for key in not_in_use:
            if key in channels: del channels[key]
            if key in currents: del currents[key]
            if key in max_currents: del max_currents[key]

        print(" UG: about to set stim currents", {"channels": channels, "currents": currents, "max_currents": max_currents})
        parameters.set_stim_currents(currents)                 # uses target keys
        parameters.set_max_currents(max_currents)
        
        parameters.set_targets(channels)

        # Ensure stim_param knows per-channel modes inferred from targets (do this after set_targets)
        mode = getattr(main_window, "_stimulation_mode", "tscs")
        if mode == "hybrid":
            fes_target_map = getattr(main_window, "_fes_target_map", {}) or {}
            fes_target_names = set(fes_target_map.values())
            parameters.infer_channel_modes_from_targets(fes_target_names=fes_target_names)
            print(
                "DEBUG: create_dict: inferred channel modes:",
                {ch: parameters.get_mode_for_channel(ch) for ch in parameters.channel_to_target.keys()},
            )        
        print(f"Channels: {channels}")
        print(f"Currents: {currents}")

        # Get the offset values from the angle calibrator (0 if not calibrated)
        offset_left, offset_right = main_window.angle_calibrator.get_offset()
        offset_left_ankle, offset_right_ankle = main_window.angle_calibrator.get_ankle_offset()

        # Get the scale factors securely (fallback to 1.0 if not opened yet)
        try:
            scale_left, scale_right = main_window.plot_dialog.knee_plot.get_scale_factors()
        except AttributeError:
            scale_left, scale_right = 1.0, 1.0

    

        # Decide whether to run continuous stimulation
        try:
            # Heuristic: if the "continuous" target is selected, prefer continuous mode
            do_continuous = ("continuous" in channels) 
            
        except Exception:
            do_continuous = ("continuous" in channels)
            
        # map new imu methods names to previous names:
        imu_mapping = {
            "Main (norm)":"Method 2 - IMU",
            "Optional (gyro)":"Method 1 - IMU"
        }
        if main_window.dropdown_btn_method.text() in imu_mapping:
            method_imu = imu_mapping[main_window.dropdown_btn_method.text()]
        else:
            method_imu = main_window.dropdown_btn_method.text()

        # map new fsr methods names to previous names:
        fsr_mapping = {
            "Main (ST, SW)":"Method 2 - FSR",
            "Optional (ST, MST, SW)":"Method 1 - FSR"
        }
        if main_window.dropdown_btn_fsr_method.text() in fsr_mapping:
            method_fsr = fsr_mapping[main_window.dropdown_btn_fsr_method.text()]
        else:
            method_fsr = main_window.dropdown_btn_fsr_method.text()
            
        
        
        # --- read FES-step UI values safely ---
        try:
            stimulate_fes_step = bool(getattr(main_window, "stimulate_fes_step_cb", None) and main_window.stimulate_fes_step_cb.isChecked())
        except Exception:
            stimulate_fes_step = False

        try:
            # page10_fes_speed_dd shows texts like "0.8 km/h" — extract numeric part
            sp_text = getattr(main_window, "page10_fes_speed_dd", None) and main_window.page10_fes_speed_dd.text() or ""
            import re as _re
            m = _re.search(r"[\d.,]+", sp_text or "")
            if m:
                fes_speed = float(m.group(0).replace(",", "."))
            else:
                fes_speed = float(main_window.lineEdit_walking_speed.text()) if getattr(main_window, "lineEdit_walking_speed", None) and main_window.lineEdit_walking_speed.text().strip() else 0.8
        except Exception:
            fes_speed = 0.8

        try:
            fes_steps = int(getattr(main_window, "page10_fes_steps", None) and main_window.page10_fes_steps.text().strip() or 0)
            if fes_steps <= 0:
                fes_steps = 1
        except Exception:
            fes_steps = 1

        try:
            fes_side = getattr(main_window, "page10_fes_side_dd", None) and main_window.page10_fes_side_dd.text().strip() or "Both"
        except Exception:
            fes_side = "Both"
            
        # --- New: Pre-swing percentage mapping to terminal stance divider (15% -> 4, 10% -> 6) ---
        try:
            if getattr(main_window, "page10_pre_swing_15_toggle", None) and main_window.page10_pre_swing_15_toggle.isChecked():
                terminal_stance_divider = 4
            elif getattr(main_window, "page10_pre_swing_10_toggle", None) and main_window.page10_pre_swing_10_toggle.isChecked():
                terminal_stance_divider = 3
            else:
                terminal_stance_divider = 4
        except Exception:
            terminal_stance_divider = 4

        dict_to_send = {
            "stimulation_parameters": parameters,
            "channels": channels,
            "save_path_filename": main_window.lineEdit_save_info_confirm.text(),
            "do_gait_detection": main_window.gait_toggle.isChecked(),
            "tSCS": main_window.tscs_toggle.isChecked(),
            "FES": main_window.fes_toggle.isChecked(),
            "fast_walking": main_window.walking_speed_toggle.isChecked() and main_window.walking_speed_toggle.isEnabled(),
            "use_imus": main_window.imu_toggle.isChecked() and main_window.imu_toggle.isEnabled(),
            "use_fsr": main_window.fsr_toggle.isChecked() and main_window.fsr_toggle.isEnabled(),
            "nb_imus": 2 if main_window.imu2_radio_btn.isChecked() else 4 if main_window.imu4_radio_btn.isChecked() else 0,
            "do_phase_detection": main_window.gait_toggle.isChecked() and main_window.phase_toggle.isChecked(),
            "do_subphase_detection": main_window.subphase_radio_btn.isChecked() and main_window.subphase_radio_btn.isEnabled(),
            "stimulator_connection": main_window.serial_port,
            "threshold_left": main_window.fsr_threshold_left_spin_box.value(),
            "threshold_right": main_window.fsr_threshold_right_spin_box.value(),
            "offset_left": offset_left,
            "offset_right": offset_right,
            "offset_left_ankle": offset_left_ankle,
            "offset_right_ankle": offset_right_ankle,
            "scale_left": scale_left,
            "scale_right": scale_right,
            "closed_loop": main_window.closed_loop_toggle.isChecked() and main_window.closed_loop_toggle.isEnabled(),
            "do_continuous_stimulation": do_continuous,
            "left_knee_angle_range": [main_window.extension_left_spin_box.value(), main_window.flexion_left_spin_box.value()],
            "right_knee_angle_range": [main_window.extension_right_spin_box.value(), main_window.flexion_right_spin_box.value()],
            "left_knee_pi_params": {
                "kp": main_window.pi_kp_left_spin_box.value(),
                "ki": main_window.pi_ki_left_spin_box.value(),
            },
            "right_knee_pi_params": {
                "kp": main_window.pi_kp_right_spin_box.value(),
                "ki": main_window.pi_ki_right_spin_box.value(),
            },
            # GUI keys (kept)
            "walking_speed": float(main_window.lineEdit_walking_speed.text()) if main_window.lineEdit_walking_speed.text().strip() else 0.4,
            "imu_method": main_window.dropdown_btn_method.text(),
            # backend keys expected by StimulationIMUs

            "method_imu": method_imu,
            "method_fsr": method_fsr,
            
            "personalized_gait_model" : main_window.page10_personalize_gait_cb.isChecked(),
            "gait_model" : main_window.dropdown_btn_gait_model.text(),
            "terminal_stance_divider": terminal_stance_divider,

            
            # --- FES-step UI values ---
            "stimulate_fes_step": stimulate_fes_step,  # bool
            "fes_speed": float(fes_speed),             # float (km/h)
            "fes_steps": int(fes_steps),               # int (number of steps)
            "fes_side": str(fes_side),                 # "Left"|"Right"|"Both"
        }
            
        
        return dict_to_send
