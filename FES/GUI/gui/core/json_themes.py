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
import json
import os

# IMPORT SETTINGS
# ///////////////////////////////////////////////////////////////
from gui.core.json_settings import Settings

# APP THEMES
# ///////////////////////////////////////////////////////////////
class Themes(object):
    # LOAD SETTINGS
    # ///////////////////////////////////////////////////////////////
    setup_settings = Settings()
    _settings = setup_settings.items

    # APP PATH
    # ///////////////////////////////////////////////////////////////
    #json_file = f"gui/themes/{_settings['theme_name']}.json"
    #app_path = os.path.abspath(os.getcwd()) #original 

    #LUKA: settings_path is now theme_path

    # Get the folder where this file (json_themes.py) lives
    here = os.path.dirname(os.path.abspath(__file__))          # ...\GUI\gui\core
    gui_folder = os.path.dirname(here)                          # ...\GUI\gui
    themes_folder = os.path.join(gui_folder, "themes")          # ...\GUI\gui\themes

    # Determine theme file
    theme_file = f"{_settings.get('theme_name', 'default')}.json"
    theme_path = os.path.join(themes_folder, theme_file)

    # Build path to the JSON inside gui/core/themes
    #settings_path = os.path.join(here, "themes", f"{_settings['theme_name']}.json")
    #settings_path = os.path.normpath(os.path.join(app_path, json_file))

    if not os.path.isfile(theme_path):
        print(f"WARNING: \"gui/themes/{_settings['theme_name']}.json\" not found! check in the folder {theme_path}")

    # INIT SETTINGS
    # ///////////////////////////////////////////////////////////////
    def __init__(self):
        super(Themes, self).__init__()

        # DICTIONARY WITH SETTINGS
        self.items = {}

        # DESERIALIZE
        self.deserialize()

    # SERIALIZE JSON
    # ///////////////////////////////////////////////////////////////
    def serialize(self):
        # WRITE JSON FILE
        with open(self.theme_path, "w", encoding='utf-8') as write:
            json.dump(self.items, write, indent=4)

    # DESERIALIZE JSON
    # ///////////////////////////////////////////////////////////////
    def deserialize(self):
        # READ JSON FILE
        with open(self.theme_path, "r", encoding='utf-8') as reader:
            settings = json.loads(reader.read())
            self.items = settings