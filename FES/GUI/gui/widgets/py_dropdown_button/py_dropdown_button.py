# ///////////////////////////////////////////////////////////////
#
# BY: DOMINIK HELBING
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
QToolButton {{
	border: none;
    padding-left: 10px;
    padding-right: 5px;
    color: {_color};
	border-radius: {_radius};	
	background-color: {_bg_color};
}}
QToolButton:hover {{
	background-color: {_bg_color_hover};
}}
QToolButton:pressed {{	
	background-color: {_bg_color_pressed};
}}
"""


# PY DROPDOWN BUTTON
# ///////////////////////////////////////////////////////////////
class PyDropDownButton(QToolButton):
    action_selected = Signal(QToolButton, QAction)

    def __init__(
        self,
        text,
        radius,
        color,
        bg_color,
        bg_color_hover,
        bg_color_pressed,
        actions=[],
        parent=None,
    ):
        super().__init__()

        # SET DEFAULT PARAMETERS
        self.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setCursor(Qt.PointingHandCursor)
        self.setText(text)
        if parent is not None:
            self.setParent(parent)

        # SETUP TRIGGER
        self.triggered.connect(self.on_action_triggered)

        # SET STYLESHEET
        custom_style = style.format(
            _color=color, _radius=radius, _bg_color=bg_color, _bg_color_hover=bg_color_hover, _bg_color_pressed=bg_color_pressed
        )
        self.setStyleSheet(custom_style)

        # ADD ACTIONS
        self._menu = QMenu()
        for action in actions:
            self._menu.addAction(action)
        self.setMenu(self._menu)

        self._min_width = 10000
        self._max_width = 0

    def on_action_triggered(self, action: QAction):
        # Set the text to the selected action's text
        self.setText(action.text())
        self.adjustSizeToText()  # Adjust the size of the button to fit the text
        self.action_selected.emit(self, action)

    def adjustSizeToText(self):
        # Update minimum and maximum width (done like this to only update the first time)
        if self._min_width > self.minimumWidth():
            self._min_width = self.minimumWidth()
        if self._max_width < self.maximumWidth():
            self._max_width = self.maximumWidth()

        # Adjust the size of the button based on the text width
        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self.text()) + 40  # Add padding

        # Clip width and height to maximum values
        text_width = max(text_width, self._min_width)
        text_width = min(text_width, self._max_width)

        self.setMinimumWidth(text_width)

    def set_actions(self, actions: list[QAction]):
        # Clear existing actions and add new ones
        self._menu.clear()
        
        for action in actions:
            action.setParent(self._menu)
            self._menu.addAction(action)
            
        # Trigger the first action by default
        self.on_action_triggered(actions[0])
