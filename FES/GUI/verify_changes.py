"""Verifica le ultime modifiche al codice. Cross-platform (Windows + macOS).

Uso (Windows PowerShell o cmd):
    cd "...\FES\GUI"
    python verify_changes.py

Uso (macOS / Linux):
    cd ".../FES/GUI"
    python verify_changes.py

Stampa una riga per modifica con [OK] o [FAIL]. Riepilogo finale a fondo pagina.
Non dipende da grep / findstr — fa la ricerca direttamente in Python.
"""

import os
import re
import sys

# Always operate from the directory this script lives in
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)


def count_in_file(path: str, pattern: str, regex: bool = False) -> int:
    """Return the number of LINES that match `pattern` in the file (like `grep -c`).

    `regex=True` interprets `pattern` as a regex; otherwise treats it as a literal string.
    Returns -1 if the file does not exist.
    """
    if not os.path.isfile(path):
        return -1
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        return -1
    if regex:
        try:
            rx = re.compile(pattern, re.MULTILINE)
        except re.error:
            return -1
        return len(rx.findall(text))
    # Literal string: count matching lines
    return sum(1 for line in text.splitlines() if pattern in line)


# Each check: (label, file, pattern, regex_flag, ok_fn)
CHECKS = [
    ("01 pelvis_inlet",                   "angle_calibrator.py",                                  "self.pelvis_inlet",                False, lambda v: v > 0),
    ("02 Pelvis LSL stream",              "angle_calibrator.py",                                  '"Pelvis"',                         False, lambda v: v > 0),
    ("03 pelvis_fsm in stimulator",       "stimulator/stimulation_classes.py",                    r"pelvis_fsm[12]",                  True,  lambda v: v > 0),
    ("04 page_11 widget created",         "gui/uis/windows/main_window/setup_main_window.py",     "page_11 = QWidget",                False, lambda v: v >= 1),
    ("05 page_11 nav routes (>=5)",       "gui/uis/windows/main_window/setup_main_window.py",     r"set_page.*page_11",               True,  lambda v: v >= 5),
    ("06 export_csv_logs def REMOVED",    "stimulator/stimulation_classes.py",                    "def export_csv_logs",              False, lambda v: v == 0),
    ("07 'import csv' REMOVED",           "stimulator/stimulation_classes.py",                    r"^import csv\b",                   True,  lambda v: v == 0),
    ("08 plot 3-column helper",           "gui/uis/windows/main_window/setup_main_window.py",     "_plot_column",                     False, lambda v: v > 0),
    ("10 Gait_Events_FSR sheet",          "stimulator/stimulation_classes.py",                    "Gait_Events_FSR",                  False, lambda v: v > 0),
    ("11 Gait_Events_IMU sheet",          "stimulator/stimulation_classes.py",                    "Gait_Events_IMU",                  False, lambda v: v > 0),
    ("12 PlotDialog update_readouts",     "gui/widgets/py_angle_plot/plot_dialog.py",             "update_readouts",                  False, lambda v: v > 0),
    ("13 Page10 readouts slot",           "gui/uis/windows/main_window/main_window.py",           "_update_page10_angle_readouts",    False, lambda v: v > 0),
    ("14 pelvis skip in phase_detection", "stimulator/stimulation_classes.py",                    'side == "pelvis"',                 False, lambda v: v >= 2),
    ("15 FSRIMU None inlet guard",        "stimulator/gait_detection_imu_fsr.py",                 "self.inlet_imu is None",           False, lambda v: v >= 1),
    ("16 detect_most_vertical_axis",      "stimulator/closed_loop.py",                            "def detect_most_vertical_axis",    False, lambda v: v == 1),
    ("17 detect_most_horizontal_axis",    "stimulator/closed_loop.py",                            "def detect_most_horizontal_axis",  False, lambda v: v == 1),
    ("18 ankle axes params (>=2)",        "stimulator/closed_loop.py",                            "foot_axis: str = 'X'",             False, lambda v: v >= 2),
    ("19 ROM.set_ankle_axes",             "stimulator/closed_loop.py",                            "def set_ankle_axes",               False, lambda v: v == 1),
    ("20 calibrator stores ankle axes",   "angle_calibrator.py",                                  r"(left|right)_ankle_foot_axis",    True,  lambda v: v > 0),
    ("21 task_dict has ankle axes",       "gui/uis/windows/main_window/setup_main_window.py",     "ankle_left_foot_axis",             False, lambda v: v > 0),
    ("22 stim ROM gets axes (>=2)",       "stimulator/stimulation_classes.py",                    "set_ankle_axes",                   False, lambda v: v >= 2),
    ("24 flush_buffers in calibrator",    "angle_calibrator.py",                                  "def flush_buffers",                False, lambda v: v == 1),
    ("25 is_all_sensors_streaming",       "angle_calibrator.py",                                  "def is_all_sensors_streaming",     False, lambda v: v == 1),
    ("26 confirm_clicked uses dialog",    "gui/uis/windows/main_window/setup_main_window.py",     "SensorReadinessDialog",            False, lambda v: v > 0),
    ("29 istruzioni milestone 19",        "istruzioni.md",                                        r"^19\.",                           True,  lambda v: v >= 1),
]

# Files that must simply exist
FILE_CHECKS = [
    ("23 SensorReadinessDialog file", "gui/widgets/sensor_readiness_dialog.py"),
    ("28 plot_gait_cycle.py",         "plot_gait_cycle.py"),
]

# Special multi-step check: calibrator NOT stopped in start_clicked
def check_calibrator_not_stopped() -> tuple[bool, str]:
    """Inside the start_clicked() function, there should be NO call to
    self.angle_calibrator.stop(). Returns (ok, msg)."""
    path = "gui/uis/windows/main_window/setup_main_window.py"
    if not os.path.isfile(path):
        return False, "file missing"
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    # Find the start_clicked function body (until next 'def ' at same indent)
    m = re.search(r"def start_clicked\(\s*\):\n((?:[^\S\n]+.*\n|\n)+)", text)
    if not m:
        return False, "start_clicked not found"
    body = m.group(1)
    if re.search(r"^\s*self\.angle_calibrator\.stop\s*\(\)", body, re.MULTILINE):
        return False, "still calling self.angle_calibrator.stop() in start_clicked"
    return True, "calibrator NOT stopped (correct)"


def main():
    passed = 0
    failed = 0
    print(f"Working dir: {HERE}\n")
    print("─── Pattern checks " + "─" * 50)
    for label, path, pattern, regex, ok in CHECKS:
        n = count_in_file(path, pattern, regex=regex)
        if n < 0:
            print(f"  [FAIL] {label:38s} -> file missing: {path}")
            failed += 1
            continue
        if ok(n):
            print(f"  [OK ] {label:38s} -> {n}")
            passed += 1
        else:
            print(f"  [FAIL] {label:38s} -> {n} (expected by rule)")
            failed += 1

    print("\n─── File-existence checks " + "─" * 43)
    for label, path in FILE_CHECKS:
        if os.path.isfile(path):
            print(f"  [OK ] {label:38s} -> present ({path})")
            passed += 1
        else:
            print(f"  [FAIL] {label:38s} -> MISSING ({path})")
            failed += 1

    print("\n─── Composite checks " + "─" * 49)
    ok27, msg27 = check_calibrator_not_stopped()
    if ok27:
        print(f"  [OK ] 27 calibrator alive in start_clicked  -> {msg27}")
        passed += 1
    else:
        print(f"  [FAIL] 27 calibrator alive in start_clicked  -> {msg27}")
        failed += 1

    total = passed + failed
    print("\n" + "═" * 70)
    print(f"  Total: {passed}/{total} OK   ({failed} FAIL)")
    print("═" * 70)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
