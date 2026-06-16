# FOG H5 Kinematic Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`).
> **Note:** repo has NO pytest suite (CLAUDE.md). Checkpoints are runnable verifications (stdout / saved PNG), not unit tests.

**Goal:** One standalone script reconstructing bilateral knee/hip/ankle angles, Method-1 gait detection, and per-sensor Freeze Index from a MAPP `recording_data.h5`, plotting only the 800–860 s window (calibration from first 10 s).

**Architecture:** Load H5 → parse COMETA (8×9) + WIMU (quat) → fuse COMETA orientation (imufusion) → calibrate from 0–10 s standing → compute joint angles (reuse `stimulator.closed_loop`) → Method-1 gait via standalone helpers in `stimulator.gait_detection_imu` → Freeze Index FFT → 3 PNGs.

**Tech Stack:** h5py, numpy, scipy, imufusion, matplotlib; reused `FES/GUI/stimulator` modules.

**File:** `FES/subjects/reconstruct_fog_h5.py` (single script, config constants at top).

---

### Task 1: Scaffold + loader + window/calib slicing

**Files:** Create `FES/subjects/reconstruct_fog_h5.py`

- [ ] **Step 1: Config + imports + sys.path.** Constants: `H5_PATH`, `T0=1208209.66`, `WIN=(800,860)`, `CALIB=(0,10)`, `COMETA_MAP={'R':{'thigh':0,'shin':4},'L':{'thigh':1,'shin':5}}`, `WIMU_DEV={'R_foot':'dev5','L_foot':'dev2','wrist':'dev3','cervical':'dev6','pelvis':'dev7'}`, `OUT_DIR`. Insert `FES/GUI` on `sys.path`.
- [ ] **Step 2: `load_stream(f, kind, dev=None)`** returns `(data, t_rel)` where `t_rel = raw_ts - T0`. COMETA: `Cometa/WaveX_IMU`. WIMU: `WIMU/WIMU_MK3/{data,timestamps}_{dev}`.
- [ ] **Step 3: `slice_win(data, t_rel, lo, hi)`** boolean-mask slice; returns `(data[m], t_rel[m])`.
- [ ] **Checkpoint:** run script `main()` stub printing, per stream, window n-samples + rate for WIN and CALIB. Expected: COMETA ~120k @2000Hz, each WIMU ~5–6k @~100Hz, calib slices non-empty.

```bash
FES/GUI/venv/bin/python "FES/subjects/reconstruct_fog_h5.py"
```

---

### Task 2: COMETA parse + orientation fusion

- [ ] **Step 1: `parse_cometa(data)`** → `acc (N,8,3)` g, `gyro (N,8,3)` deg/s via `data.reshape(N,8,9)[:,:,0:3]` and `[:,:,3:6]`.
- [ ] **Step 2: `fuse_block(acc_g, gyro_dps, fs=2000.0)`** → quaternion `(N,4)` w,x,y,z using `imufusion.Ahrs`; convert acc g→m/s² not needed (Ahrs uses g + deg/s). Loop `ahrs.update_no_magnetometer(gyro_row, acc_row, 1/fs)`, collect `ahrs.quaternion.wxyz`.
- [ ] **Checkpoint:** fuse block 0 over CALIB; print mean quat norm (~1.0) and that it's near-constant during 10 s standing (std per component < 0.05).

---

### Task 3: Calibration offsets (first 10 s standing)

- [ ] **Step 1: `calib_quat(qarr)`** = normalized median quaternion over CALIB slice (per segment). For COMETA: fuse the CALIB slice. For WIMU: quat cols 4-7 over CALIB.
- [ ] **Step 2:** build calib refs for all 6 segments (R/L thigh,shin COMETA; pelvis,R_foot,L_foot WIMU).
- [ ] **Checkpoint:** print 6 reference quats; assert each norm≈1.

---

### Task 4: Joint angles (reuse closed_loop)

- [ ] **Step 1: `knee_angle(q_thigh, q_shin, offset)`** per side using `ROM(offset=...)` + `ROM.compute_from_list` style, or directly `closed_loop.angle_between_quaternions`. Offset from CALIB neutral (`ROM.functional_calibration` on calib slices or `angle_between_quaternions` of refs).
- [ ] **Step 2: `hip_angle`** = `angle_between_quaternions(q_pelvis, q_thigh)` minus calib neutral, per side. Time-match COMETA→WIMU nearest-timestamp (`np.searchsorted`).
- [ ] **Step 3: `ankle_angle`** per side via `ROM.set_ankle_reference` + `get_ankle_angle` (signed/hinge), refs from calib. Time-match shin(2000Hz)→foot(100Hz).
- [ ] **Checkpoint:** compute all 6 angles over WIN; print min/max/ROM per joint. Sanity: knee ROM plausibly 0–60° walking; warn if absurd (>180 or NaN).

---

### Task 5: Verify COMETA mapping

- [ ] **Step 1: `verify_mapping(gyro)`** over WIN: per side compute gyro-norm RMS for thigh vs shin block; assert/ warn `shin_RMS > thigh_RMS`. Print table.
- [ ] **Checkpoint:** prints PASS/WARN per side. Non-fatal.

---

### Task 6: Method-1 gait detection (both feet)

- [ ] **Step 1: `foot_gyro_y(dev)`** = WIMU col 2 (gyro/motion Y) over WIN for dev5(R), dev2(L). (If cols 1-3 prove non-gyro, derive angular velocity from quaternion finite-difference; decide at checkpoint.)
- [ ] **Step 2: `detect_gait(gyro_y, fs)`** using `gait_detection_imu.identify_gait_phases` (peaks=mid-swing) + `identify_valleys`; classify each peak HS vs TO by nearest valley side per Method-1 rule (HS just after valley, TO before peak). Return HS times, TO times, and a STANCE/SWING phase timeline (TO→HS = swing, HS→TO = stance).
- [ ] **Checkpoint:** print #HS, #TO, mean cycle duration per foot; plausible cadence (cycle 0.8–2 s for FOG slow gait) else warn.

---

### Task 7: Freeze Index (13 sensors)

- [ ] **Step 1: `freeze_index(sig_norm, fs, win=4.0, step=0.25)`** sliding window; per window FFT (`np.fft.rfft`), `loco=power(0.5–3Hz)`, `freeze=power(3–8Hz)`, `FI=freeze/loco`. Return `(t_centers, FI)`.
- [ ] **Step 2:** motion-norm per sensor over WIN — COMETA: acc-norm of its block; WIMU: norm of cols 1-3. 13 series (8 COMETA + 5 WIMU).
- [ ] **Checkpoint:** print FI range per sensor; assert finite, non-negative.

---

### Task 8: Figures (3 PNGs)

- [ ] **Step 1: `fig_angles`** — 3 rows (knee/hip/ankle), R+L overlaid, x=time(s), phase shading from R-foot timeline. Save `fog002_narrow_angles_800_860.png`.
- [ ] **Step 2: `fig_gait`** — 2 rows (R,L): gyro-Y + HS (▲) + TO (▼) markers + stance/swing bands. Save `fog002_narrow_gait_800_860.png`.
- [ ] **Step 3: `fig_fi`** — 13 FI traces (grouped/colored COMETA vs WIMU) + horizontal freeze threshold (FI=2, annotate). Save `fog002_narrow_freezeindex_800_860.png`.
- [ ] **Checkpoint:** run full script; 3 PNGs exist + non-trivial size. Visually open angles PNG.

---

### Task 9: Commit

- [ ] Commit script + PNGs.

```bash
git add "FES/subjects/reconstruct_fog_h5.py"
git commit -m "Add FOG H5 kinematic reconstruction + gait + freeze index analysis"
```

## Self-review notes
- Spec coverage: bilateral angles (T4), gait both feet (T6), FI 13 sensors (T7), 800–860 window + 10 s calib (T1,T3), mapping verify (T5), PNGs (T8) — all covered.
- WIMU col-1-3 semantics resolved empirically at T6 checkpoint (gyro vs derive-from-quat).
- Cross-system time-match via searchsorted defined in T4.
