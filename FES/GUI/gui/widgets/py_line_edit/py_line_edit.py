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
style = '''
QLineEdit {{
	background-color: {_bg_color};
	border-radius: {_radius}px;
	border: {_border_size}px solid transparent;
	padding-left: 10px;
    padding-right: 10px;
	selection-color: {_selection_color};
	selection-background-color: {_context_color};
    color: {_color};
}}
QLineEdit:focus {{
	border: {_border_size}px solid {_context_color};
    background-color: {_bg_color_active};
}}
'''

# PY PUSH BUTTON
# ///////////////////////////////////////////////////////////////
class PyLineEdit(QLineEdit):
    focused = Signal(QLineEdit) # Custom signal emitted when the widget is focused
    
    def __init__(
        self, 
        text = "",
        place_holder_text = "",
        radius = 8,
        border_size = 2,
        color = "#FFF",
        selection_color = "#FFF",
        bg_color = "#333",
        bg_color_active = "#222",
        context_color = "#00ABE8",
        adjust_size = False,
        constraints = [0, 0, 16777215, 16777215],
    ):
        super().__init__()

        # PARAMETERS
        if text:
            self.setText(text)
        if place_holder_text:
            self.setPlaceholderText(place_holder_text)
        if adjust_size:
            self.textChanged.connect(self.adjust_size)
            self._min_width = constraints[0]
            self._min_height = constraints[1]
            self._max_width = constraints[2]
            self._max_height = constraints[3]

        # SET STYLESHEET
        self.set_stylesheet(
            radius,
            border_size,
            color,
            selection_color,
            bg_color,
            bg_color_active,
            context_color
        )

    # SET STYLESHEET
    def set_stylesheet(
        self,
        radius,
        border_size,
        color,
        selection_color,
        bg_color,
        bg_color_active,
        context_color
    ):
        # APPLY STYLESHEET
        style_format = style.format(
            _radius = radius,
            _border_size = border_size,           
            _color = color,
            _selection_color = selection_color,
            _bg_color = bg_color,
            _bg_color_active = bg_color_active,
            _context_color = context_color
        )
        self.setStyleSheet(style_format)

    def adjust_size(self):
        """Adjusts the width of the QLineEdit based on its content."""
        # Get the maximal values
        
        fm = QFontMetrics(self.font())  
        text_width = fm.horizontalAdvance(self.text()) + 30  # Add padding
        text_height = self.sizeHint().height()

        # Clip width and height to maximum values
        text_width = max(text_width, self._min_width)
        text_height = max(text_height, self._min_height)
        text_width = min(text_width, self._max_width)
        text_height = min(text_height, self._max_height)

        self.setFixedSize(QSize(text_width, text_height))
        
    def focusInEvent(self, event: QFocusEvent) -> None:
        """Override the focusInEvent to emit a custom signal."""
        super().focusInEvent(event)
        self.focused.emit(self)
        
    def as_value(self) -> int | float:
        """Convert the text to an integer or float."""
        if self.text() == "":
            return 0
        try:
            return int(self.text())
        except ValueError:
            return float(self.text())