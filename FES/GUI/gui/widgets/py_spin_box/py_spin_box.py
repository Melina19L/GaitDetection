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
QSpinBox, QDoubleSpinBox {{
	background-color: {_bg_color};
    color: {_color};        
}}
"""

# PY SPIN BOX
# ///////////////////////////////////////////////////////////////
class PySpinBox(QSpinBox):
    def __init__(
        self,
        text_color="#FFFFFF",
        bg_color="#333333",
        value_range = (0, 100),
        step_size = 1,
        value = 0, 
        parent=None,
    ):
        
        super().__init__(parent=parent)
            
        # Remove the frame
        self.setFrame(False)
        
        # Set minimum height
        self.setMinimumHeight(25)
        
        # Set range, decimals, step and value
        self.setRange(*value_range)
        self.setSingleStep(step_size)
        self.setValue(value)

        # SET STYLESHEET
        self.setStyleSheet(style.format(
            _bg_color=bg_color,
            _color=text_color,
        ))