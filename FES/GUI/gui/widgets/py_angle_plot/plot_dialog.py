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
        self.reset_btn = QPushButton("Reset Graph")
        self.reset_btn.setStyleSheet(
            f"""
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
        )
        self.reset_btn.setMaximumWidth(200)
        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
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

        # Knee legend
        knee_legend = QWidget()
        knee_legend.setMaximumHeight(22)
        kl = QHBoxLayout(knee_legend)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(20)
        kl.addStretch(1)
        lbl_lk = QLabel(f"\u25a0 Left Knee")
        lbl_lk.setStyleSheet(f"font-size: 10pt; color: {themes['app_color']['yellow']};")
        lbl_rk = QLabel(f"\u25a0 Right Knee")
        lbl_rk.setStyleSheet(f"font-size: 10pt; color: {themes['app_color']['red']};")
        kl.addWidget(lbl_lk)
        kl.addWidget(lbl_rk)
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

        # Ankle legend
        ankle_legend = QWidget()
        ankle_legend.setMaximumHeight(22)
        al = QHBoxLayout(ankle_legend)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(20)
        al.addStretch(1)
        lbl_la = QLabel("\u25a0 Left Ankle")
        lbl_la.setStyleSheet("font-size: 10pt; color: #50fa7b;")
        lbl_ra = QLabel("\u25a0 Right Ankle")
        lbl_ra.setStyleSheet("font-size: 10pt; color: #bd93f9;")
        al.addWidget(lbl_la)
        al.addWidget(lbl_ra)
        al.addStretch(1)
        layout.addWidget(ankle_legend)

        # ── Timer for plot updates ──
        self.timer = QTimer(self)
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.knee_plot.update_plot)
        self.timer.timeout.connect(self.ankle_plot.update_plot)

        # ── Reset wiring ──
        self.reset_btn.clicked.connect(self._reset)

    # ────────────────────────────────────
    # Public API (called from setup_main_window)
    # ────────────────────────────────────

    def start(self):
        """Show the dialog and start the plot timer."""
        self.knee_plot.reset_plot()
        self.ankle_plot.reset_plot()
        self.timer.stop()   # ensure no double-fire if already running
        self.timer.start()
        self.show()
        self.raise_()

    def _reset(self):
        """Reset both plots and restart plotting from zero."""
        self.timer.stop()
        self.knee_plot.reset_plot()
        self.ankle_plot.reset_plot()
        self.timer.start()

    # ────────────────────────────────────
    # Overrides
    # ────────────────────────────────────

    def closeEvent(self, event):
        """Hide instead of closing so the dialog can be re-opened without crashes."""
        self.timer.stop()
        event.ignore()   # don't destroy the widget
        self.hide()

    def reject(self):
        """Intercept Escape key (QDialog default) — same behaviour as X button."""
        self.timer.stop()
        self.hide()
