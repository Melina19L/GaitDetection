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

HEIGHT = 16

class PyToggleSmall(QCheckBox):
    def __init__(
        self,
        width = 30,
        text = "",
        bg_color = "#777", 
        circle_color = "#DDD",
        active_color = "#00BCFF",
        text_color = "#FFF",
        text_color_active = "#FFF",
        text_disabled_color = "#777",
        bg_color_disabled = "#777",
        animation_curve = QEasingCurve.OutBounce
    ):
        # Calculate the width of the text
        self._text_width = QFontMetrics(QFont("Segoe UI", 9)).horizontalAdvance(text) + 15 # 15px padding
        self._toggle_width = width
        # Set the total width to be the sum of the text width and the toggle width
        QCheckBox.__init__(self, text)
        self.setFixedSize(width + self._text_width, HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        # COLORS
        self._bg_color = bg_color
        self._circle_color = circle_color
        self._active_color = active_color
        self._text_color = text_color
        self._text_disabled_color = text_disabled_color
        self._bg_color_disabled = bg_color_disabled
        self._text_color_active = text_color_active

        self._position = 3
        self.animation = QPropertyAnimation(self, b"position")
        self.animation.setEasingCurve(animation_curve)
        self.animation.setDuration(500)
        self.stateChanged.connect(self.setup_animation)

    @Property(float)
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        self._position = pos
        self.update()

    # START STOP ANIMATION
    def setup_animation(self, value):
        self.animation.stop()
        if value:
            self.animation.setEndValue(self._toggle_width - HEIGHT)
        else:
            self.animation.setEndValue(4)
        self.animation.start()
    
    def hitButton(self, pos: QPoint):
        return self.contentsRect().contains(pos)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(QFont("Segoe UI", 9))

        # SET PEN
        p.setPen(Qt.NoPen)

        # DRAW RECT
        rect = QRect(0, 0, self._toggle_width, HEIGHT)        

        if not self.isChecked():
            if self.isEnabled():
                p.setBrush(QColor(self._bg_color))
            else:
                p.setBrush(QColor(self._bg_color_disabled))
            p.drawRoundedRect(0,0,rect.width(), HEIGHT, HEIGHT/2, HEIGHT/2)
            p.setBrush(QColor(self._circle_color))
            p.drawEllipse(self._position, 2, HEIGHT-4, HEIGHT-4)
        else:
            if self.isEnabled():
                p.setBrush(QColor(self._active_color))
            else:
                p.setBrush(QColor(self._bg_color_disabled))
            p.drawRoundedRect(0,0,rect.width(), HEIGHT, HEIGHT/2, HEIGHT/2)
            p.setBrush(QColor(self._circle_color))
            p.drawEllipse(self._position, 2, HEIGHT-4, HEIGHT-4)
            
        # DRAW TEXT
        if self.isEnabled():
            if self.isChecked():
                p.setPen(QColor(self._text_color_active))
            else:
                p.setPen(QColor(self._text_color))
        else:
            p.setPen(QColor(self._text_disabled_color))
        text_rect = QRect(rect.width() + 5, 0, self._text_width - 5, rect.height())
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text())

        p.end()