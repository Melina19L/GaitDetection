# ///////////////////////////////////////////////////////////////
#
# PRE-TRIAL VALIDATION DIALOG — neutral-pose drift check between Start clicks.
#
# Use case: the operator calibrated once at session start, then runs multiple
# Start/Stop trials back-to-back. Between trials the Movella DOT onboard 9-DOF
# Kalman filter (or a slipped strap) can drift the heading by several degrees
# — same body pose, different reported angle. Without a check the next trial
# silently records compressed/shifted ROM. This dialog catches the drift
# BEFORE the recording starts.
#
# Protocol: subject stands still ~2 s with knees straight, feet parallel,
# ankle neutral. The dialog samples the live joint-angle stream during the
# window and reports mean drift per joint vs the calibration zero. If every
# joint stays within tolerance the operator can Continue; otherwise the
# dialog warns and offers Re-calibrate (cancels Start) or Continue Anyway.
#
# ///////////////////////////////////////////////////////////////

from qt_core import *


class PreTrialValidationDialog(QDialog):
    """Modal neutral-pose validation gate.

    Usage:
        dlg = PreTrialValidationDialog(calibrator, themes, parent=window)
        if dlg.exec() == QDialog.Accepted:
            # ... start the experiment ...
        else:
            # operator chose to re-calibrate or cancelled
    """

    SAMPLE_WINDOW_MS = 2000      # how long to average drift
    POLL_INTERVAL_MS = 200       # GUI refresh cadence
    DEFAULT_TOLERANCE_DEG = 5.0  # acceptable drift vs calibration zero

    def __init__(self, calibrator, themes: dict, parent=None,
                 tolerance_deg: float = DEFAULT_TOLERANCE_DEG):
        super().__init__(parent)
        self.calibrator = calibrator
        self.themes = themes
        self.tolerance_deg = float(tolerance_deg)
        self._elapsed_ms = 0
        self._latest: dict[str, float] = {}

        self.setWindowTitle("Pre-trial neutral-pose check")
        self.setModal(True)
        self.setMinimumWidth(440)
        bg = themes["app_color"]["bg_one"]
        fg = themes["app_color"]["text_foreground"]
        self.setStyleSheet(
            f"QDialog {{ background-color: {bg}; color: {fg}; }}"
            f"QLabel  {{ color: {fg}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Subject standing still — neutral-pose check")
        title.setStyleSheet("font-size: 13pt; font-weight: 600;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Stand still for ~2 s: knees straight, feet parallel, ankle neutral.\n"
            "Each joint should read close to 0°. Larger drift = re-calibrate."
        )
        subtitle.setStyleSheet("font-size: 9pt; color: #aaaaaa;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        # Per-joint drift readout grid
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(4)
        self._row_widgets: dict[str, tuple[QLabel, QLabel]] = {}
        for row, key in enumerate(("L_hip", "L_knee", "L_ankle",
                                   "R_hip", "R_knee", "R_ankle")):
            name = QLabel(key.replace("_", " "))
            name.setStyleSheet("font-size: 11pt;")
            val = QLabel("—")
            val.setStyleSheet("font-size: 11pt; font-family: monospace; color: #888;")
            self.grid.addWidget(name, row, 0)
            self.grid.addWidget(val,  row, 1)
            self._row_widgets[key] = (name, val)
        layout.addLayout(self.grid)

        self.status_label = QLabel("Sampling…")
        self.status_label.setStyleSheet("font-size: 10pt; color: #f39c12;")
        layout.addWidget(self.status_label)

        footer = QHBoxLayout()
        self.elapsed_label = QLabel("0.0 s")
        self.elapsed_label.setStyleSheet("font-size: 9pt; color: #888888;")
        footer.addWidget(self.elapsed_label)
        footer.addStretch(1)

        self.recal_btn = QPushButton("Re-calibrate")
        self.recal_btn.clicked.connect(self.reject)
        footer.addWidget(self.recal_btn)

        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setEnabled(False)
        self.continue_btn.clicked.connect(self.accept)
        footer.addWidget(self.continue_btn)

        layout.addLayout(footer)

        # Drain stale values so the average only sees fresh samples during the window.
        try:
            self.calibrator.flush_buffers()
        except Exception:
            pass

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self.POLL_INTERVAL_MS)

    def _tick(self) -> None:
        self._elapsed_ms += self.POLL_INTERVAL_MS
        self.elapsed_label.setText(f"{self._elapsed_ms/1000:.1f} s")
        try:
            self._latest = self.calibrator.get_neutral_pose_drift(n_samples=50)
        except Exception:
            self._latest = {}

        worst = 0.0
        for key, (_, val_lbl) in self._row_widgets.items():
            v = self._latest.get(key)
            if v is None:
                val_lbl.setText("—")
                val_lbl.setStyleSheet("font-size: 11pt; font-family: monospace; color: #666;")
                continue
            color = "#2ecc71" if abs(v) <= self.tolerance_deg else "#e74c3c"
            val_lbl.setText(f"{v:+.1f}°")
            val_lbl.setStyleSheet(f"font-size: 11pt; font-family: monospace; color: {color};")
            worst = max(worst, abs(v))

        if self._elapsed_ms >= self.SAMPLE_WINDOW_MS:
            self._timer.stop()
            self.continue_btn.setEnabled(True)
            if not self._latest:
                self.status_label.setText("No live samples received — check sensors.")
                self.status_label.setStyleSheet("font-size: 10pt; color: #e74c3c;")
            elif worst <= self.tolerance_deg:
                self.status_label.setText(f"✓ All joints within ±{self.tolerance_deg:.0f}°.")
                self.status_label.setStyleSheet("font-size: 10pt; color: #2ecc71;")
                self.continue_btn.setDefault(True)
            else:
                self.status_label.setText(
                    f"⚠ Drift up to {worst:.1f}° — recalibration recommended."
                )
                self.status_label.setStyleSheet("font-size: 10pt; color: #e74c3c;")
                self.recal_btn.setDefault(True)
