# ///////////////////////////////////////////////////////////////
#
# PLOT DIALOG — Separate window for real-time angle plots
# Contains Knee Angle and Ankle Angle plots with Reset button.
# Opens when "Start Graph" is pressed on the IMU setup page.
#
# ///////////////////////////////////////////////////////////////

from qt_core import *
from gui.widgets.py_angle_plot.py_angle_plot import PyAnglePlot
from gui.widgets.py_angle_plot.py_ankle_plot import PyAnklePlot
from gui.widgets.py_angle_plot.py_hip_plot import PyHipPlot
from angle_calibrator import AngleCalibrator


class PlotDialog(QDialog):
    """Floating dialog that shows real-time knee and ankle angle plots."""

    def __init__(
        self,
        calibrator: AngleCalibrator,
        themes: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("IMU Angle Monitor")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)
        self.calibrator = calibrator
        self.themes = themes

        # --- Build UI ---
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        bg = themes["app_color"]["bg_one"]
        self.setStyleSheet(f"background-color: {bg};")

        # ── Reset button ──
        # Setup page is preview-only: data persistence happens at end of test, not here.
        self.reset_btn = QPushButton("Reset Graph")

        btn_style = f"""
            QPushButton {{
                background-color: {themes["app_color"]["dark_three"]};
                color: {themes["app_color"]["text_foreground"]};
                border: 1px solid {themes["app_color"]["context_color"]};
                border-radius: 6px;
                padding: 6px 20px;
                font-size: 11pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {themes["app_color"]["dark_four"]};
            }}
        """
        self.reset_btn.setStyleSheet(btn_style)
        self.reset_btn.setMaximumWidth(200)

        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(20)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch(1)
        btn_container.setMaximumHeight(40)
        layout.addWidget(btn_container)

        text_color = themes["app_color"]["text_foreground"]
        label_style = f"font-size: 12pt; font-weight: bold; color: {text_color};"

        # ── Knee Angle Plot ──
        knee_title = QLabel("Knee Angle")
        knee_title.setStyleSheet(label_style)
        knee_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        knee_title.setMaximumHeight(24)
        layout.addWidget(knee_title)

        self.knee_plot = PyAnglePlot(
            calibrator,
            axis_color=themes["app_color"]["text_foreground"],
            background_color=themes["app_color"]["dark_three"],
            line_color_left=themes["app_color"]["yellow"],
            line_color_right=themes["app_color"]["red"],
            max_points=1000,
        )
        layout.addWidget(self.knee_plot, 1)

        # Knee legend with live numeric readouts.
        # Format: "\u25a0 Left Knee  +12.3\u00b0    \u25a0 Right Knee  +10.5\u00b0"
        # The value labels are updated by update_readouts() on every plot timer tick.
        knee_legend = QWidget()
        knee_legend.setMaximumHeight(22)
        kl = QHBoxLayout(knee_legend)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(20)
        kl.addStretch(1)
        lbl_lk = QLabel("\u25a0 Left Knee")
        lbl_lk.setStyleSheet(f"font-size: 10pt; color: {themes['app_color']['yellow']};")
        self.lbl_lk_value = QLabel("--")
        self.lbl_lk_value.setStyleSheet(f"font-size: 10pt; font-family: monospace; color: {themes['app_color']['yellow']}; min-width: 60px;")
        lbl_rk = QLabel("\u25a0 Right Knee")
        lbl_rk.setStyleSheet(f"font-size: 10pt; color: {themes['app_color']['red']};")
        self.lbl_rk_value = QLabel("--")
        self.lbl_rk_value.setStyleSheet(f"font-size: 10pt; font-family: monospace; color: {themes['app_color']['red']}; min-width: 60px;")
        kl.addWidget(lbl_lk)
        kl.addWidget(self.lbl_lk_value)
        kl.addWidget(lbl_rk)
        kl.addWidget(self.lbl_rk_value)
        kl.addStretch(1)
        layout.addWidget(knee_legend)

        # ── Ankle Angle Plot ──
        ankle_title = QLabel("Ankle Angle")
        ankle_title.setStyleSheet(label_style)
        ankle_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ankle_title.setMaximumHeight(24)
        layout.addWidget(ankle_title)

        self.ankle_plot = PyAnklePlot(
            calibrator,
            axis_color=themes["app_color"]["text_foreground"],
            background_color=themes["app_color"]["dark_three"],
            line_color_left="#50fa7b",
            line_color_right="#bd93f9",
            max_points=1000,
        )
        layout.addWidget(self.ankle_plot, 1)

        # Ankle legend with live numeric readouts.
        ankle_legend = QWidget()
        ankle_legend.setMaximumHeight(22)
        al = QHBoxLayout(ankle_legend)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(20)
        al.addStretch(1)
        lbl_la = QLabel("\u25a0 Left Ankle")
        lbl_la.setStyleSheet("font-size: 10pt; color: #50fa7b;")
        self.lbl_la_value = QLabel("--")
        self.lbl_la_value.setStyleSheet("font-size: 10pt; font-family: monospace; color: #50fa7b; min-width: 60px;")
        lbl_ra = QLabel("\u25a0 Right Ankle")
        lbl_ra.setStyleSheet("font-size: 10pt; color: #bd93f9;")
        self.lbl_ra_value = QLabel("--")
        self.lbl_ra_value.setStyleSheet("font-size: 10pt; font-family: monospace; color: #bd93f9; min-width: 60px;")
        al.addWidget(lbl_la)
        al.addWidget(self.lbl_la_value)
        al.addWidget(lbl_ra)
        al.addWidget(self.lbl_ra_value)
        al.addStretch(1)
        layout.addWidget(ankle_legend)

        # ── Hip Angle Plot ──
        hip_title = QLabel("Hip Angle")
        hip_title.setStyleSheet(label_style)
        hip_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hip_title.setMaximumHeight(24)
        layout.addWidget(hip_title)

        self.hip_plot = PyHipPlot(
            calibrator,
            axis_color=themes["app_color"]["text_foreground"],
            background_color=themes["app_color"]["dark_three"],
            line_color_left="#8be9fd",   # cyan
            line_color_right="#ffb86c",  # orange
            max_points=1000,
        )
        layout.addWidget(self.hip_plot, 1)

        # Hip legend with live numeric readouts.
        hip_legend = QWidget()
        hip_legend.setMaximumHeight(22)
        hl = QHBoxLayout(hip_legend)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(20)
        hl.addStretch(1)
        lbl_lh = QLabel("\u25a0 Left Hip")
        lbl_lh.setStyleSheet("font-size: 10pt; color: #8be9fd;")
        self.lbl_lh_value = QLabel("--")
        self.lbl_lh_value.setStyleSheet("font-size: 10pt; font-family: monospace; color: #8be9fd; min-width: 60px;")
        lbl_rh = QLabel("\u25a0 Right Hip")
        lbl_rh.setStyleSheet("font-size: 10pt; color: #ffb86c;")
        self.lbl_rh_value = QLabel("--")
        self.lbl_rh_value.setStyleSheet("font-size: 10pt; font-family: monospace; color: #ffb86c; min-width: 60px;")
        hl.addWidget(lbl_lh)
        hl.addWidget(self.lbl_lh_value)
        hl.addWidget(lbl_rh)
        hl.addWidget(self.lbl_rh_value)
        hl.addStretch(1)
        layout.addWidget(hip_legend)

        # ── Timer for plot updates ──
        # 50 ms = 20 Hz refresh — enough for smooth gait visualization,
        # and safe for pyqtgraph rendering 1000 points without stacking callbacks.
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.knee_plot.update_plot)
        self.timer.timeout.connect(self.ankle_plot.update_plot)
        self.timer.timeout.connect(self.hip_plot.update_plot)
        self.timer.timeout.connect(self.update_readouts)

        # ── Button wiring ──
        self.reset_btn.clicked.connect(self._reset)

    @staticmethod
    def _fmt_angle(val) -> str:
        """Format a calibrator angle (numpy scalar / array / float) as ``+12.3°`` or ``--``."""
        try:
            import numpy as _np
            if val is None:
                return "--"
            if hasattr(val, "size") and val.size == 0:
                return "--"
            if hasattr(val, "item"):
                v = float(val.item())
            else:
                v = float(val)
            return f"{v:+6.1f}°"
        except Exception:
            return "--"

    @Slot()
    def update_readouts(self):
        """Read the latest knee/ankle/hip values from the calibrator and update the legend labels."""
        try:
            lk, rk = self.calibrator.get_latest_data()
            la, ra = self.calibrator.get_latest_ankle_data()
            lh, rh = self.calibrator.get_latest_hip_data()
            self.lbl_lk_value.setText(self._fmt_angle(lk))
            self.lbl_rk_value.setText(self._fmt_angle(rk))
            self.lbl_la_value.setText(self._fmt_angle(la))
            self.lbl_ra_value.setText(self._fmt_angle(ra))
            self.lbl_lh_value.setText(self._fmt_angle(lh))
            self.lbl_rh_value.setText(self._fmt_angle(rh))
        except Exception:
            # Silently ignore transient errors (e.g. calibrator stopped mid-tick)
            pass

    # ────────────────────────────────────
    # Public API (called from setup_main_window)
    # ────────────────────────────────────

    def start(self):
        """Show the dialog and start the plot timer."""
        self.knee_plot.reset_plot()
        self.ankle_plot.reset_plot()
        self.hip_plot.reset_plot()
        self.timer.stop()   # ensure no double-fire if already running
        self.timer.start()
        self.show()
        self.raise_()

    def _reset(self):
        """Reset both plots and restart plotting from zero."""
        self.timer.stop()
        self.knee_plot.reset_plot()
        self.ankle_plot.reset_plot()
        self.hip_plot.reset_plot()
        # Reset session timestamp in calibrator to align with visually reset data
        self.calibrator._session_start = __import__('time').time()
        self.timer.start()

    # ────────────────────────────────────
    # Overrides
    # ────────────────────────────────────

    def closeEvent(self, event):
        """Hide instead of closing so the dialog can be re-opened without crashes."""
        self.timer.stop()
        if hasattr(self, 'calibrator') and hasattr(self.calibrator, 'save_raw_data'):
            self.calibrator.save_raw_data()
        event.ignore()   # don't destroy the widget
        self.hide()

    def reject(self):
        """Intercept Escape key (QDialog default) — same behaviour as X button."""
        self.timer.stop()
        if hasattr(self, 'calibrator') and hasattr(self.calibrator, 'save_raw_data'):
            self.calibrator.save_raw_data()
        self.hide()
