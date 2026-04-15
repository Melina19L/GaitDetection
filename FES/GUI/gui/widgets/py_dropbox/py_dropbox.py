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
QComboBox {{
	background-color: {_bg_color};
	border-radius: {_radius}px;
	border: {_border_size}px solid transparent;
	padding-left: 10px;
    padding-right: 10px;
	selection-color: {_selection_color};
	selection-background-color: {_context_color};
    color: {_color};
}}
QComboBox:hover, QComboBox:open{{
	border: {_border_size}px solid {_context_color};
    background-color: {_bg_color_active};
    color: {_selection_color};
}}
QComboBox::drop-down {{
    border: none;
}}
QComboBox QAbstractItemView {{
    background-color: {_bg_color};
    color: {_color};
    border-radius: {_radius}px;
    padding: 5px;
}}
QComboBox QAbstractItemView::item {{
    padding: 2px;
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {_bg_color_active};
    color: {_selection_color};
    border-left: 2px solid {_context_color};
}}
QComboBox QListView{{
    outline: none;
}}
QComboBox::disabled {{
    background-color: {_disable_color};
}}
"""


# PY DROPBOX
# ///////////////////////////////////////////////////////////////
class PyDropbox(QComboBox):
    def __init__(
        self,
        item_list=[],
        default_value="",
        radius=8,
        border_size=2,
        color="#FFF",
        selection_color="#FFF",
        bg_color="#333",
        bg_color_active="#222",
        context_color="#00ABE8",
        disable_color="#555",
        parent=None,
    ):
        super().__init__()

        # PARAMETERS
        if parent:
            self.setParent(parent)
        if item_list:
            self.clear()
            self.addItems(item_list)
        if default_value:
            self.setCurrentText(default_value)

        # SET STYLESHEET
        self.set_stylesheet(radius, border_size, color, selection_color, bg_color, bg_color_active, context_color, disable_color)

    # SET STYLESHEET
    def set_stylesheet(self, radius, border_size, color, selection_color, bg_color, bg_color_active, context_color, disable_color):
        # APPLY STYLESHEET
        style_format = style.format(
            _radius=radius,
            _border_size=border_size,
            _color=color,
            _selection_color=selection_color,
            _bg_color=bg_color,
            _bg_color_active=bg_color_active,
            _context_color=context_color,
            _disable_color=disable_color
        )
        self.setStyleSheet(style_format)
