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

# IMPORT SVG FUNCTIONS
# ///////////////////////////////////////////////////////////////
from gui.core.functions import Functions

# IMPORT SVG EDIT FUNCTIONS
# ///////////////////////////////////////////////////////////////
from modify_svg import change_circle_color_to

# STYLE
# ///////////////////////////////////////////////////////////////
style = """
QRadioButton {{
    color: {_color_text};
}}
QRadioButton:checked {{
    color: {_color_active};
}}
QRadioButton:hover {{
    color: {_color_active};  /* Just change label color on hover */
}}
QRadioButton:disabled {{
    color: {_color_disabled};
}}"""

style_sheet = """
QRadioButton::indicator
{
    width: 13px;
    height: 13px;
}

QRadioButton::indicator::unchecked
{
   image: url(:/gui/images/svg_images/radio_btn_unchecked.svg);
}

QRadioButton::indicator:unchecked:hover
{
    image: url(:/gui/images/svg_images/radio_btn_unchecked.svg);
}

QRadioButton::indicator:unchecked:pressed
{
    image: url(:/gui/images/svg_images/radio_btn_pressed.svg);
}

QRadioButton::indicator::checked 
{
    image: url(:/gui/images/svg_images/radio_btn_checked.svg);
}

QRadioButton::indicator:checked:hover 
{
    image: url(:/gui/images/svg_images/radio_btn_hover.svg);
}

QRadioButton::indicator:checked:pressed 
{
    image: url(:/gui/images/svg_images/radio_btn_pressed.svg);
}

QRadioButton::indicator:checked:disabled
{
    image: url(:/gui/images/svg_images/radio_btn_checked_disabled.svg);
}

QRadioButton::indicator:unchecked:disabled
{
    image: url(:/gui/images/svg_images/radio_btn_unchecked_disabled.svg);
}
"""


# PY RADIO BUTTON
# ///////////////////////////////////////////////////////////////
class PyRadioButton(QRadioButton):
    def __init__(
        self,
        text,
        text_color,
        active_color,
        disabled_color,
        parent=None,
        checked=False,
    ):
        super().__init__(text, parent)

        # SET PARAMETRES
        self.setCursor(Qt.PointingHandCursor)
        self.setChecked(checked)

        # SET STYLESHEET
        custom_style = style.format(
            _color_text=text_color, 
            _color_active=active_color, 
            _color_disabled=disabled_color)
        self.setStyleSheet(style_sheet + custom_style)

    @staticmethod
    def set_style_sheet(
        checked_color="#568af2", 
        unchecked_color="#c3ccdf", 
        disabled_color="#c3ccdf", 
        bg_color="#272c36", 
        disabled_bg_color="#3c4454"
    ):
        """Used to update the color the svg images for the radio buttons.\n
        !!! IMPORTANT !!! \n
        This function will overwrite the original SVG images and will not update at runtime.\n
        If you need this, you have to recompile rc_radio_btn_images.py.\n
        --> pyside6-rcc rc_radio_btn_images.qrc -o rc_radio_btn_images.py\n

        :param checked_color: The color of the ring when checked, defaults to "#568af2"
        :type checked_color: str, optional
        :param unchecked_color: The color of the ring when unchecked, defaults to "#c3ccdf"
        :type unchecked_color: str, optional
        :param disabled_color: The color of the ring when disabled, defaults to "#c3ccdf"
        :type disabled_color: str, optional
        :param bg_color: The color of the background when enabled, defaults to "#272c36"
        :type bg_color: str, optional
        :param disabled_bg_color: The color fo the background when disabled, defaults to "#3c4454"
        :type disabled_bg_color: str, optional
        """
        paths_enabled = [
            Functions.set_svg_image("radio_btn_checked.svg"),
            Functions.set_svg_image("radio_btn_unchecked.svg"),
            Functions.set_svg_image("radio_btn_pressed.svg"),
            Functions.set_svg_image("radio_btn_hover.svg"),
        ]
        paths_disabled = [
            Functions.set_svg_image("radio_btn_checked_disabled.svg"),
            Functions.set_svg_image("radio_btn_unchecked_disabled.svg"),
        ]
        for path in paths_enabled:
            change_circle_color_to(path, 0, checked_color)
            change_circle_color_to(path, 1, bg_color)

        for path in paths_disabled:
            change_circle_color_to(path, 0, disabled_color)
            change_circle_color_to(path, 1, disabled_bg_color)

        change_circle_color_to(paths_enabled[1], 0, unchecked_color)
