# GaitDetection

Desktop application for the EPFL/MAPP gait study. These are working notes for
whoever takes this over: what it does, how to install and open it, and step by
step what to do on each page to get gait detection and joint-angle data out of a
session. It stays practical — for how the code is built, see `INSTRUCTIONS.md`.

## What it does, briefly

The patient wears IMU sensors (and optionally force insoles) on the legs. The
program reads them, detects which phase of the walking cycle each leg is in, and
records the joint angles (knee, ankle, hip) and gait events in real time. On the
stimulation study it also drives electrical stimulation, but this guide covers
only the gait-detection and joint-angle side.

## Installing

From this folder (`FES/GUI/`), with Anaconda:

```
conda env create --name gait --file gait.yml
```

or with pip:

```
pip install -r requirements.txt
```

The IMUs also need the Movella DOT PC SDK, installed separately:
https://base.movella.com/s/article/Movella-DOT-PC-SDK-Guide?language=en_US

## Opening it

```
python main.py
```

Keep the PC on mains power while recording — on battery the plots and the
real-time loop can lag.

## Placing the sensors

Strap the DOT sensors on the front of the leg segments (anterior), each with the
button facing up, held by the straps. Same orientation on every segment: it's
what the calibration and the angle computation assume.
Positions: foot, shank, thigh, pelvis

## Step by step through a session

### 1. Subject and save folder

On the first page enter the subject data, then choose the folder where this
session's files will be saved. Everything the run produces goes there.

### 2. Sensors and walking speed

Pick which sensors you'll use: IMUs only, or IMUs together with the FSR insoles.
Set the walking speed for the subject — use **0.5** for a patient (slow gait) and
**1.2** for a healthy subject. The detection adapts to this speed, so set it to
match how the person will actually walk.

### 3. FSR setup (only if you use the insoles)

On the FSR page, scan for the insoles, connect them, and set the insole size.
Skip this page if you're running IMUs only.

### 4. IMU setup

Open the Movella DOT window and connect the sensors there, then synchronise them
(this lines up their clocks and headings — do it every session)and do the calibration (standing + leg extended 90°) . Back on the IMU
page, use the toggles to select which joints you want to analyse (knee, ankle,
hip), turning on only the segments you actually strapped on.

### 5. Calibration

Calibration tells the system what "neutral" is and how each joint rotates; every
angle you record afterwards depends on it, so don't skip it and don't rush it.
There are two calibrations:

- **Global (standing+ seated)** — stand still and relaxed in a neutral, straight posture for about 5 seconds, then will appear a window, after you click okay, wait 3s and sit. You know when it's finished because the toogles go from grey to blue. This sets the zero reference for all joints and finds the knee and hip rotation axes.
- **Ankle (seated)** — sit with the leg out and move the foot up and
  down (dorsi/plantarflexion) for about five seconds. This finds the ankle axis.

Make the movements wide and smooth, and really do stand straight for the neutral
pose — a slightly bent posture biases every angle. After each calibration the box
on the page tells you, per joint, whether it got **SVD** or **CARD**. SVD is what
you want (a clean calibration); CARD is a fallback and means you should redo that
calibration with wider, cleaner movements.

### 6. Check the live plots

Use **Start Graph** to open the real-time angle plots and watch them for a
moment. This is where you check the offset looks right — the angles should sit
near zero in neutral and move sensibly when the leg moves. If something looks off,
recalibrate before going on.

### 7. Final page and starting the test

Move forward to the last page. When you press start and confirm, a box comes up
showing the offset and method for each joint. Check it: every joint should read
SVD (if any reads CARD, go back and recalibrate), and the offsets should look
reasonable. If any joint is red, recalibrate. Only when everything is green and
the box says it's OK do you continue — and the test begins.

### 8. During the test

Next to the plots there's a step counter that counts steps as they're detected in
real time, and below it a live readout of which gait phase each leg is currently
in. On the page before the test you can tick the audio-cues box: with it on, the
program plays a short beep on each detected gait event, so you can hear the steps
being picked up without watching the screen.

You can pause and resume, or stop, at any point. When you stop, the run is written
to the folder you chose at the start.

## The files a run produces

Stopping a run writes four files, all with the same base name, in your chosen
folder. They're two pairs — a `.pkl` for Python and a `.xlsx` for Excel — of two
different things.

| File | What's in it | When you want it |
|------|--------------|------------------|
| `<base>.pkl` | The main record: gait events, stimulation and raw sensor streams. Joint angles here are sparse (only updated when the detection logic needs them). | The complete experiment; processing in Python. |
| `<base>.xlsx` | The same main record, as a spreadsheet. | A quick look without Python (the hip-angle column is mostly empty here — that's normal). |
| `<base>_plot.pkl` | Knee/ankle/hip angles sampled continuously (~60 Hz) — the data behind the live plots. | Angle work in Python. |
| `<base>_plot.xlsx` | Those continuous angles as a spreadsheet, over a few sheets: the raw angles, a version resampled onto a uniform time grid, which calibration method each joint used, and the walking window. | Joint-angle / kinematic analysis — reach for this one. |

For the whole experiment use `<base>.pkl`; to analyse the joint angles open
`<base>_plot.xlsx` and use the resampled sheet, where all joints share one time
grid.

## Good to know

Turns are hard for the ankle: during a sharp turn the ankle angle from the foot
IMU isn't reliable, while knee and hip stay accurate, so trust the ankle mainly on
straight walking. There are two detection methods for both the IMU and FSR path —
pick whichever suits the task; the interface names them in plain terms.

## For developers

`INSTRUCTIONS.md` covers the internals: the real-time loop, the
gait-detection state machines, the quaternion angle math and how the GUI is put
together. Each source file has a docstring saying what it's for. The core is under
`stimulator/`, the live angle engine is `angle_calibrator.py`, and the pages are
built in `gui/uis/windows/main_window/setup_main_window.py`.
