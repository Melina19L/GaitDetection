# ///////////////////////////////////////////////////////////////
#
# ANKLE ANGLE PLOT WIDGET
# Displays real-time ankle angle (shank-foot) alongside knee angle.
# Same architecture as PyAnglePlot but reads ankle data from the calibrator.
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

from angle_calibrator import AngleCalibrator

MAX_ANKLE_ANGLE = 60
DORSIFLEXION_ANGLE = -10
PLANTARFLEXION_ANGLE = 20


# PY ANKLE PLOT
# ///////////////////////////////////////////////////////////////
class PyAnklePlot(pg.PlotWidget):
    def __init__(
        self,
        calibrator: AngleCalibrator,
        axis_color="#8a95aa",
        background_color="#21252d",
        line_color_left="#50fa7b",
        line_color_right="#bd93f9",
        max_points=200,
        fix_y_range=False,
        parent=None,
    ):
        super().__init__(parent)

        # SET PARAMETERS
        self.max_points = max_points
        self.ptr = 0
        self.scale_factor_left = 1.0
        self.scale_factor_right = 1.0
        # Use deques for O(1) append and automatic size limiting
        self._time = deque(maxlen=max_points)
        self._left_ankle = deque(maxlen=max_points)
        self._right_ankle = deque(maxlen=max_points)
        self.left_ankle_enabled = False
        self.right_ankle_enabled = False
        self.calibrator = calibrator

        # Disable dragging
        self.setMouseEnabled(x=False, y=True)

        # SET STYLE
        # Fix ranges
        self.setXRange(0, self.max_points, padding=0)
        if fix_y_range:
            self.setYRange(-MAX_ANKLE_ANGLE, MAX_ANKLE_ANGLE, padding=0)

        # Set background color
        self.setBackground(background_color)

        # Color of the axes and text
        axis_pen = pg.mkPen(color=axis_color)
        for axis in ("bottom", "left"):
            ax = self.getAxis(axis)
            ax.setPen(axis_pen)
            ax.setTextPen(axis_pen)

        # Set the color of the plot lines
        pen_left = pg.mkPen(color=line_color_left, width=3)
        self.left_ankle_curve = self.plot(pen=pen_left)
        pen_right = pg.mkPen(color=line_color_right, width=3)
        self.right_ankle_curve = self.plot(pen=pen_right)

        # Add horizontal reference lines for ankle targets
        self.upper_line_left = pg.InfiniteLine(pos=PLANTARFLEXION_ANGLE, angle=0, pen=pg.mkPen(line_color_left, width=1))
        self.lower_line_left = pg.InfiniteLine(pos=DORSIFLEXION_ANGLE, angle=0, pen=pg.mkPen(line_color_left, width=1, dash=[2, 4]))
        self.upper_line_right = pg.InfiniteLine(pos=PLANTARFLEXION_ANGLE, angle=0, pen=pg.mkPen(line_color_right, width=1))
        self.lower_line_right = pg.InfiniteLine(pos=DORSIFLEXION_ANGLE, angle=0, pen=pg.mkPen(line_color_right, width=1, dash=[2, 4]))

        # Hide the lines initially
        self.upper_line_left.setVisible(False)
        self.lower_line_left.setVisible(False)
        self.upper_line_right.setVisible(False)
        self.lower_line_right.setVisible(False)
        self.addItem(self.upper_line_left)
        self.addItem(self.lower_line_left)
        self.addItem(self.upper_line_right)
        self.addItem(self.lower_line_right)

    def show_left_ankle_angle(self, do_show: bool = False):
        self.left_ankle_enabled = do_show

    def show_right_ankle_angle(self, do_show: bool = False):
        self.right_ankle_enabled = do_show

    def invert_angle(self, left: bool):
        if left:
            self.scale_factor_left *= -1
        else:
            self.scale_factor_right *= -1

    def get_scale_factors(self) -> tuple[float, float]:
        """
        Returns the current scale factors for left and right ankle angles.
        """
        return self.scale_factor_left, self.scale_factor_right

    def set_scale_factor(self, scale_factor: float, left: bool):
        # Clamp the scale factor to a reasonable range
        scale_factor = max(0.1, min(scale_factor, 4.0))
        if left:
            if self.scale_factor_left < 0:
                self.scale_factor_left = -scale_factor
            else:
                self.scale_factor_left = scale_factor
        else:
            if self.scale_factor_right < 0:
                self.scale_factor_right = -scale_factor
            else:
                self.scale_factor_right = scale_factor

    def set_target_dorsiflexion_angle(self, angle: float, left: bool):
        if left:
            self.lower_line_left.setPos(angle)
        else:
            self.lower_line_right.setPos(angle)

    def set_target_plantarflexion_angle(self, angle: float, left: bool):
        if left:
            self.upper_line_left.setPos(angle)
        else:
            self.upper_line_right.setPos(angle)

    def reset_plot(self):
        self.ptr = 0
        self._time.clear()
        self._left_ankle.clear()
        self._right_ankle.clear()
        self.left_ankle_curve.clear()
        self.right_ankle_curve.clear()
        self.upper_line_left.setVisible(True)
        self.lower_line_left.setVisible(True)
        self.upper_line_right.setVisible(True)
        self.lower_line_right.setVisible(True)
        self.setXRange(0, self.max_points, padding=0)

    def update_plot(self):
        # Get the latest ankle angles from the calibrator
        left_ankle_angle, right_ankle_angle = self.calibrator.get_latest_ankle_data()

        self.ptr += 1
        self._time.append(self.ptr)

        if self.left_ankle_enabled and np.asarray(left_ankle_angle).size > 0:
            self._left_ankle.append(float(np.asarray(left_ankle_angle).flat[0]))
        else:
            self._left_ankle.append(self._left_ankle[-1] if self._left_ankle else 0.0)

        if self.right_ankle_enabled and np.asarray(right_ankle_angle).size > 0:
            self._right_ankle.append(float(np.asarray(right_ankle_angle).flat[0]))
        else:
            self._right_ankle.append(self._right_ankle[-1] if self._right_ankle else 0.0)

        t = np.array(self._time, dtype=float)
        la = np.array(self._left_ankle, dtype=float) * self.scale_factor_left
        ra = np.array(self._right_ankle, dtype=float) * self.scale_factor_right

        self.left_ankle_curve.setData(t, la)
        self.right_ankle_curve.setData(t, ra)

        # Dynamic X range: always follows the newest ptr
        if self.ptr > self.max_points:
            self.setXRange(self.ptr - self.max_points, self.ptr, padding=0)
        else:
            self.setXRange(0, self.max_points, padding=0)
