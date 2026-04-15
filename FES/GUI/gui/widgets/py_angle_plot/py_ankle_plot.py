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
        self.left_ankle_angle = np.array([])
        self.right_ankle_angle = np.array([])
        self.time = np.array([])
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
        self.left_ankle_angle = np.array([])
        self.right_ankle_angle = np.array([])
        self.time = np.array([])
        self.left_ankle_curve.clear()
        self.right_ankle_curve.clear()
        self.upper_line_left.setVisible(True)
        self.lower_line_left.setVisible(True)
        self.upper_line_right.setVisible(True)
        self.lower_line_right.setVisible(True)

    def update_plot(self):
        # Get the latest ankle angles from the calibrator
        left_ankle_angle, right_ankle_angle = self.calibrator.get_latest_ankle_data()

        self.ptr += 1
        self.time = np.append(self.time, self.ptr)

        if self.left_ankle_enabled and left_ankle_angle.size > 0:
            self.left_ankle_angle = np.append(self.left_ankle_angle, left_ankle_angle)
        else:
            self.left_ankle_angle = np.append(self.left_ankle_angle, 0)

        if self.right_ankle_enabled and right_ankle_angle.size > 0:
            self.right_ankle_angle = np.append(self.right_ankle_angle, right_ankle_angle)
        else:
            self.right_ankle_angle = np.append(self.right_ankle_angle, 0)

        if self.time.size > self.max_points:
            self.time = self.time[-self.max_points :]
            self.left_ankle_angle = self.left_ankle_angle[-self.max_points :]
            self.right_ankle_angle = self.right_ankle_angle[-self.max_points :]

        self.left_ankle_curve.setData(self.time, self.left_ankle_angle * self.scale_factor_left)
        self.right_ankle_curve.setData(self.time, self.right_ankle_angle * self.scale_factor_right)

        # Dynamic X range to follow data
        if self.ptr > self.max_points:
            self.setXRange(self.ptr - self.max_points, self.ptr, padding=0)
        else:
            self.setXRange(0, self.max_points, padding=0)
