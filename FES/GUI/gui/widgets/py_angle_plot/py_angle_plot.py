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

# IMPORT NUMPY
# ///////////////////////////////////////////////////////////////
import numpy as np
from collections import deque

# IMPORT PYQTGRAPH
# ///////////////////////////////////////////////////////////////
import pyqtgraph as pg

# This is a bit weird, but I think it is better to directly get the data from the calibrator
from angle_calibrator import AngleCalibrator

MAX_ANGLE = 100
FLEXION_ANGLE = 60
EXTENSION_ANGLE = 10


# PY ANGLE PLOT
# ///////////////////////////////////////////////////////////////
class PyAnglePlot(pg.PlotWidget):
    def __init__(
        self,
        calibrator: AngleCalibrator,
        axis_color="#8a95aa",
        background_color="#21252d",
        line_color_left="#f1fa8c",
        line_color_right="#ff5555",
        max_points=200,
        fix_y_range=False,
        parent=None,
    ):
        super().__init__(parent)

        # SET PARAMETRES
        self.max_points = max_points
        self.ptr = 0
        self.scale_factor_left = 1.0
        self.scale_factor_right = 1.0
        # Use deques for O(1) append and automatic size limiting
        self._time = deque(maxlen=max_points)
        self._left_knee = deque(maxlen=max_points)
        self._right_knee = deque(maxlen=max_points)
        self.left_knee_enabled = False
        self.right_knee_enabled = False
        self.calibrator = calibrator

        # Disable dragging
        self.setMouseEnabled(x=False, y=True)

        # SET STYLE
        # Fix ranges
        self.setXRange(0, self.max_points, padding=0)
        if fix_y_range:
            self.setYRange(-MAX_ANGLE, MAX_ANGLE, padding=0)

        # Set background color
        self.setBackground(background_color)

        # Color of the axes and text
        axis_pen = pg.mkPen(color=axis_color)
        for axis in ("bottom", "left"):
            ax = self.getAxis(axis)
            ax.setPen(axis_pen)
            ax.setTextPen(axis_pen)

        # Set the olor of the plot line
        pen_left = pg.mkPen(color=line_color_left, width=3)
        self.left_knee_curve = self.plot(pen=pen_left)
        pen_right = pg.mkPen(color=line_color_right, width=3)
        self.right_knee_curve = self.plot(pen=pen_right)

        # Add horizontal lines (initially at y = 30 and y = -30 for example)
        self.upper_line_left = pg.InfiniteLine(pos=FLEXION_ANGLE, angle=0, pen=pg.mkPen(line_color_left, width=1))
        self.lower_line_left = pg.InfiniteLine(pos=EXTENSION_ANGLE, angle=0, pen=pg.mkPen(line_color_left, width=1, dash=[2, 4]))
        self.upper_line_right = pg.InfiniteLine(pos=FLEXION_ANGLE, angle=0, pen=pg.mkPen(line_color_right, width=1))
        self.lower_line_right = pg.InfiniteLine(pos=EXTENSION_ANGLE, angle=0, pen=pg.mkPen(line_color_right, width=1, dash=[2, 4]))

        # Hide the lines initially
        self.upper_line_left.setVisible(False)
        self.lower_line_left.setVisible(False)
        self.upper_line_right.setVisible(False)
        self.lower_line_right.setVisible(False)
        self.addItem(self.upper_line_left)
        self.addItem(self.lower_line_left)
        self.addItem(self.upper_line_right)
        self.addItem(self.lower_line_right)

    def show_left_knee_angle(self, do_show: bool = False):
        self.left_knee_enabled = do_show

    def show_right_knee_angle(self, do_show: bool = False):
        self.right_knee_enabled = do_show

    def invert_angle(self, left: bool):
        if left:
            self.scale_factor_left *= -1
        else:
            self.scale_factor_right *= -1

    def get_scale_factors(self) -> tuple[float, float]:
        """
        Returns the current scale factors for left and right knee angles.
        """
        return self.scale_factor_left, self.scale_factor_right

    def set_scale_factor(self, scale_factor: float, left: bool):
        # Clamp the scale factor to a reasonable range
        scale_factor = max(0.1, min(scale_factor, 4.0))
        if left:
            # If the angle was inverted before, we need to adjust the scale factor accordingly
            if self.scale_factor_left < 0:
                self.scale_factor_left = -scale_factor
            else:
                self.scale_factor_left = scale_factor
        else:
            # If the angle was inverted before, we need to adjust the scale factor accordingly
            if self.scale_factor_right < 0:
                self.scale_factor_right = -scale_factor
            else:
                self.scale_factor_right = scale_factor
                
    def set_target_extension_angle(self, angle: float, left: bool):
        # Set the target extension angle for the specified knee
        if left:
            self.lower_line_left.setPos(angle)
        else:
            self.lower_line_right.setPos(angle)
            
    def set_target_flexion_angle(self, angle: float, left: bool):
        # Set the target bend angle for the specified knee
        if left:
            self.upper_line_left.setPos(angle)
        else:
            self.upper_line_right.setPos(angle)

    def reset_plot(self):
        self.ptr = 0
        self._time.clear()
        self._left_knee.clear()
        self._right_knee.clear()
        self.left_knee_curve.clear()
        self.right_knee_curve.clear()
        self.upper_line_left.setVisible(True)
        self.lower_line_left.setVisible(True)
        self.upper_line_right.setVisible(True)
        self.lower_line_right.setVisible(True)
        self.setXRange(0, self.max_points, padding=0)

    def update_plot(self):
        # Get the latest angles from the calibrator
        left_knee_angle, right_knee_angle = self.calibrator.get_latest_data()

        self.ptr += 1
        self._time.append(self.ptr)

        if self.left_knee_enabled and np.ndim(left_knee_angle) == 0 and left_knee_angle.size > 0:
            self._left_knee.append(float(left_knee_angle))
        elif self.left_knee_enabled and np.asarray(left_knee_angle).size > 0:
            self._left_knee.append(float(np.asarray(left_knee_angle).flat[0]))
        else:
            self._left_knee.append(self._left_knee[-1] if self._left_knee else 0.0)

        if self.right_knee_enabled and np.asarray(right_knee_angle).size > 0:
            self._right_knee.append(float(np.asarray(right_knee_angle).flat[0]))
        else:
            self._right_knee.append(self._right_knee[-1] if self._right_knee else 0.0)

        t = np.array(self._time, dtype=float)
        lk = np.array(self._left_knee, dtype=float) * self.scale_factor_left
        rk = np.array(self._right_knee, dtype=float) * self.scale_factor_right

        self.left_knee_curve.setData(t, lk)
        self.right_knee_curve.setData(t, rk)

        # Dynamic X range: always follows the newest ptr
        if self.ptr > self.max_points:
            self.setXRange(self.ptr - self.max_points, self.ptr, padding=0)
        else:
            self.setXRange(0, self.max_points, padding=0)
