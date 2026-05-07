# ///////////////////////////////////////////////////////////////
#
# SENSOR READINESS DIALOG — modal "warm-up" gate before the test starts.
#
# Polls AngleCalibrator.is_all_sensors_streaming() every 100 ms and shows
# per-sensor green/red indicators. Closes automatically when all connected
# sensors have produced fresh samples within the freshness window, OR when
# the user clicks Cancel, OR when the timeout expires.
#
# Used in the start-experiment flow so that:
#   1. The recording does not contain the BLE warm-up transient (some Movella
#      DOTs take 3–5 s to begin delivering samples after a connect).
#   2. The live plot starts from a clean baseline rather than catching up on
#      a backlog of stale samples.
#
# Right before dismissing successfully, the caller also calls
# AngleCalibrator.flush_buffers() to drain any leftover stale samples.
#
# ///////////////////////////////////////////////////////////////

from qt_core import *


class SensorReadinessDialog(QDialog):
    """Modal "Waiting for sensors..." dialog.

    Usage:
        dlg = SensorReadinessDialog(calibrator, themes, parent=window)
        result = dlg.exec()  # blocks; returns QDialog.Accepted on success
        if result == QDialog.Accepted:
            calibrator.flush_buffers()
            # ... start the experiment ...
    """

    POLL_INTERVAL_MS = 100      # how often we re-check sensor freshness
    DEFAULT_TIMEOUT_S = 15      # give up if a sensor never streams

    def __init__(self, calibrator, themes: dict, parent=None,
                 timeout_s: float = DEFAULT_TIMEOUT_S,
                 freshness_s: float = 0.5):
        super().__init__(parent)
        self.calibrator = calibrator
        self.themes = themes
        self.timeout_s = float(timeout_s)
        self.freshness_s = float(freshness_s)

        self.setWindowTitle("Waiting for sensors")
        self.setModal(True)
        self.setMinimumWidth(420)
        bg = themes["app_color"]["bg_one"]
        fg = themes["app_color"]["text_foreground"]
        self.setStyleSheet(
            f"QDialog {{ background-color: {bg}; color: {fg}; }}"
            f"QLabel  {{ color: {fg}; }}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.title_label = QLabel("Waiting for all sensors to stream…")
        self.title_label.setStyleSheet("font-size: 13pt; font-weight: 600;")
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(
            "The Movella DOTs need a moment to push fresh samples over BLE.\n"
            "The test starts as soon as every connected sensor is ready."
        )
        self.subtitle_label.setStyleSheet("font-size: 9pt; color: #aaaaaa;")
        self.subtitle_label.setWordWrap(True)
        layout.addWidget(self.subtitle_label)

        # Per-sensor status grid (built dynamically based on what's connected)
        self.status_grid = QGridLayout()
        self.status_grid.setHorizontalSpacing(14)
        self.status_grid.setVerticalSpacing(4)
        self._row_widgets: dict[str, tuple[QLabel, QLabel]] = {}
        connected = calibrator._connected_inlets()
        if not connected:
            warn = QLabel("⚠ No sensors connected.")
            warn.setStyleSheet("color: #e74c3c; font-weight: 600;")
            layout.addWidget(warn)
        else:
            for row, (name, _inlet, _key) in enumerate(connected):
                lbl_name = QLabel(name)
                lbl_name.setStyleSheet("font-size: 11pt;")
                lbl_state = QLabel("⏳ waiting")
                lbl_state.setStyleSheet("font-size: 10pt; color: #f39c12; font-family: monospace;")
                self.status_grid.addWidget(lbl_name,  row, 0)
                self.status_grid.addWidget(lbl_state, row, 1)
                self._row_widgets[name] = (lbl_name, lbl_state)
        layout.addLayout(self.status_grid)

        # Footer: elapsed counter + cancel button
        footer = QHBoxLayout()
        self.elapsed_label = QLabel("0.0 s")
        self.elapsed_label.setStyleSheet("font-size: 9pt; color: #888888;")
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(
            f"QPushButton {{ padding: 6px 18px; background: {themes['app_color']['dark_three']};"
            f" color: {fg}; border: 1px solid {themes['app_color']['bg_two']}; border-radius: 5px; }}"
            f"QPushButton:hover {{ background: {themes['app_color']['dark_four']}; }}"
        )
        self.cancel_btn.clicked.connect(self.reject)
        footer.addWidget(self.elapsed_label)
        footer.addStretch(1)
        footer.addWidget(self.cancel_btn)
        layout.addLayout(footer)

        # Internal state
        self._t0 = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)

    # ────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────

    def showEvent(self, event):
        import time as _time
        self._t0 = _time.time()
        # Run one poll synchronously so a fast-streaming setup auto-closes immediately.
        self._poll()
        if self.isVisible():
            self._poll_timer.start()
        super().showEvent(event)

    def closeEvent(self, event):
        self._poll_timer.stop()
        super().closeEvent(event)

    # ────────────────────────────────────────────────────────────
    # Polling
    # ────────────────────────────────────────────────────────────

    def _poll(self):
        import time as _time
        elapsed = _time.time() - (self._t0 or _time.time())
        self.elapsed_label.setText(f"{elapsed:4.1f} s")

        try:
            all_ready, status = self.calibrator.is_all_sensors_streaming(self.freshness_s)
        except Exception:
            all_ready, status = False, {}

        for name, (_lbl_name, lbl_state) in self._row_widgets.items():
            ready = status.get(name, False)
            if ready:
                lbl_state.setText("✅ streaming")
                lbl_state.setStyleSheet(
                    "font-size: 10pt; color: #27ae60; font-family: monospace; font-weight: 600;"
                )
            else:
                lbl_state.setText("⏳ waiting")
                lbl_state.setStyleSheet(
                    "font-size: 10pt; color: #f39c12; font-family: monospace;"
                )

        if all_ready and self._row_widgets:
            self._poll_timer.stop()
            self.title_label.setText("✓ All sensors streaming — starting test")
            # Tiny visual settling delay so the user sees the green state
            QTimer.singleShot(250, self.accept)
            return

        if elapsed >= self.timeout_s:
            self._poll_timer.stop()
            self.title_label.setText("⚠ Timeout — some sensors did not stream")
            self.subtitle_label.setText(
                "Check BLE / Movella DOT status and reconnect. You can also press "
                "Cancel and start again, or click Start Anyway to proceed regardless."
            )
            # Replace Cancel with two buttons
            try:
                self.cancel_btn.setText("Cancel")
                # Add a "Start anyway" button if not already present
                if not hasattr(self, "_start_anyway_btn"):
                    self._start_anyway_btn = QPushButton("Start anyway")
                    self._start_anyway_btn.setStyleSheet(
                        f"QPushButton {{ padding: 6px 18px; background: #c0392b; color: white;"
                        f" border-radius: 5px; }}"
                        f"QPushButton:hover {{ background: #e74c3c; }}"
                    )
                    self._start_anyway_btn.clicked.connect(self.accept)
                    # insert before Cancel
                    layout = self.layout()
                    footer = layout.itemAt(layout.count() - 1)
                    footer.insertWidget(footer.count() - 1, self._start_anyway_btn)
            except Exception:
                pass
