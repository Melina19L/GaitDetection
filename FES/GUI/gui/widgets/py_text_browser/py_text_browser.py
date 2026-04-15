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

# IMPORT QT CORE
# ///////////////////////////////////////////////////////////////
from qt_core import *

# STYLE
# ///////////////////////////////////////////////////////////////
style = """
QTextBrowser {{
	background-color: {_bg_color};
    color: {_color};
    border: none;                  
    border-radius: 8px;            
    outline: none;                 
    padding: 6px;                  
}}
"""


# PY TEXT BROWSER
# ///////////////////////////////////////////////////////////////
class PyTextBrowser(QTextBrowser):
    def __init__(
        self,
        text_color="#FFFFFF",
        bg_color="#333333",
        parent=None,
    ):
        super().__init__()

        if parent is not None:
            self.setParent(parent)

        # SET STYLESHEET
        self.set_stylesheet(bg_color, text_color)
        
        self.setReadOnly(True)  # Make the text browser read-only

    # SET STYLESHEET
    def set_stylesheet(
        self,
        bg_color,
        text_color,
    ):
        # APPLY STYLESHEET
        style_format = style.format(
            _bg_color=bg_color,
            _color=text_color,
        )
        self.setStyleSheet(style_format)