import re

with open("angle_calibrator.py", "r") as f:
    content = f.read()

# Replace 1: _BUF = 1000 and self._acc = { ... }
old_acc = """        # Max 300 samples ≈ 3 s at 100 Hz — enough headroom without memory risk.
        _BUF = 300
        self._acc = {
            name: deque(maxlen=_BUF)
            for name in ("left_thigh", "left_shank", "left_foot",
                          "right_thigh", "right_shank", "right_foot",
                          "pelvis")
        }"""
new_acc = """        # Max 1000 samples ≈ 16 s at 60 Hz — extremely resilient to BT dropouts.
        _BUF = 1000
        self._acc = {
            "l_hip_pelvis": deque(maxlen=_BUF),
            "l_hip_thigh": deque(maxlen=_BUF),
            "r_hip_pelvis": deque(maxlen=_BUF),
            "r_hip_thigh": deque(maxlen=_BUF),
            
            "l_knee_thigh": deque(maxlen=_BUF),
            "l_knee_shank": deque(maxlen=_BUF),
            "r_knee_thigh": deque(maxlen=_BUF),
            "r_knee_shank": deque(maxlen=_BUF),
            
            "l_ankle_shank": deque(maxlen=_BUF),
            "l_ankle_foot": deque(maxlen=_BUF),
            "r_ankle_shank": deque(maxlen=_BUF),
            "r_ankle_foot": deque(maxlen=_BUF),
        }"""
content = content.replace(old_acc, new_acc)

# Replace 2: record_data
old_record = """                self._acc[key].extend(paired)
                self._diag[key]["count"]  += len(samples)
                self._diag[key]["last_ts"] = now
                if hasattr(self, '_raw_log') and key in self._raw_log:
                    # Save raw samples with arrival timestamp for debugging
                    for ts, s in paired:
                        self._raw_log[key].append([ts] + list(s))"""
new_record = """                # Distribute into strictly independent queues to prevent multi-consumer popping bugs
                if key == "pelvis":
                    self._acc["l_hip_pelvis"].extend(paired)
                    self._acc["r_hip_pelvis"].extend(paired)
                elif key == "left_thigh":
                    self._acc["l_hip_thigh"].extend(paired)
                    self._acc["l_knee_thigh"].extend(paired)
                elif key == "right_thigh":
                    self._acc["r_hip_thigh"].extend(paired)
                    self._acc["r_knee_thigh"].extend(paired)
                elif key == "left_shank":
                    self._acc["l_knee_shank"].extend(paired)
                    self._acc["l_ankle_shank"].extend(paired)
                elif key == "right_shank":
                    self._acc["r_knee_shank"].extend(paired)
                    self._acc["r_ankle_shank"].extend(paired)
                elif key == "left_foot":
                    self._acc["l_ankle_foot"].extend(paired)
                elif key == "right_foot":
                    self._acc["r_ankle_foot"].extend(paired)
                    
                self._diag[key]["count"]  += len(samples)
                self._diag[key]["last_ts"] = now
                if hasattr(self, '_raw_log') and key in self._raw_log:
                    # Save raw samples with arrival timestamp for debugging
                    for ts, s in paired:
                        self._raw_log[key].append([ts] + list(s))"""
content = content.replace(old_record, new_record)

# Replace 3: _process_data
import re
start_match = re.search(r"        # ── 2\. Snapshot pelvis", content)
end_match = re.search(r"            print\(\"Warning: Attempted to pop from empty accumulation queue\.\"\)", content)
if start_match and end_match:
    start_idx = start_match.start()
    end_idx = end_match.end()
    
    new_process = """        # ── 2. Process LEFT LEG ───────────────────────────────────────────────

        # Hip LEFT
        if self.pelvis_inlet and self.left_thigh_inlet:
            q_p = list(self._acc["l_hip_pelvis"])
            q_t = list(self._acc["l_hip_thigh"])
            p_s, p_ts, t_s, t_ts, c_p, c_t = self._match_snapshots(q_p, q_t)
            if p_s:
                hip_angles = self.__compute_angles_from_data(
                    p_s, p_ts, t_s, t_ts,
                    self.left_hip_offset, self._diag["pelvis"],
                )
                self.left_hip_data = np.append(self.left_hip_data, hip_angles)
                self.left_hip_timestamps = np.append(self.left_hip_timestamps, t_ts)
                for _ in range(c_p): self._acc["l_hip_pelvis"].popleft()
                for _ in range(c_t): self._acc["l_hip_thigh"].popleft()

        # Knee LEFT
        if self.left_thigh_inlet and self.left_shank_inlet:
            q_t = list(self._acc["l_knee_thigh"])
            q_s = list(self._acc["l_knee_shank"])
            t_s, t_ts, s_s, s_ts, c_t, c_s = self._match_snapshots(q_t, q_s)
            if t_s:
                angles = self.__compute_angles_from_data(
                    t_s, t_ts, s_s, s_ts,
                    self.left_angle_offset, self._diag["left_thigh"],
                )
                self.left_angle_data = np.append(self.left_angle_data, angles)
                self.left_angle_timestamps = np.append(self.left_angle_timestamps, s_ts)
                for _ in range(c_t): self._acc["l_knee_thigh"].popleft()
                for _ in range(c_s): self._acc["l_knee_shank"].popleft()

        # Ankle LEFT
        if self.left_shank_inlet and self.left_foot_inlet:
            q_s = list(self._acc["l_ankle_shank"])
            q_f = list(self._acc["l_ankle_foot"])
            s_s, s_ts, f_s, f_ts, c_s, c_f = self._match_snapshots(q_s, q_f)
            if s_s:
                ankle_angles = self.__compute_angles_from_data(
                    s_s, s_ts, f_s, f_ts,
                    self.left_ankle_offset, self._diag["left_shank"],
                    is_ankle=True,
                    proximal_axis=self.left_ankle_shank_axis,
                    distal_axis=self.left_ankle_foot_axis,
                    q_proximal_ref=getattr(self, 'left_ankle_qshank_ref', None),
                    q_distal_ref=getattr(self, 'left_ankle_qfoot_ref', None),
                    hinge_axis=getattr(self, 'left_ankle_hinge_axis', None),
                )
                self.left_ankle_data = np.append(self.left_ankle_data, ankle_angles)
                self.left_ankle_timestamps = np.append(self.left_ankle_timestamps, f_ts)
                for _ in range(c_s): self._acc["l_ankle_shank"].popleft()
                for _ in range(c_f): self._acc["l_ankle_foot"].popleft()

        # ── 3. Process RIGHT LEG ──────────────────────────────────────────────

        # Hip RIGHT
        if self.pelvis_inlet and self.right_thigh_inlet:
            q_p = list(self._acc["r_hip_pelvis"])
            q_t = list(self._acc["r_hip_thigh"])
            p_s, p_ts, t_s, t_ts, c_p, c_t = self._match_snapshots(q_p, q_t)
            if p_s:
                hip_angles = self.__compute_angles_from_data(
                    p_s, p_ts, t_s, t_ts,
                    self.right_hip_offset, self._diag["pelvis"],
                )
                self.right_hip_data = np.append(self.right_hip_data, hip_angles)
                self.right_hip_timestamps = np.append(self.right_hip_timestamps, t_ts)
                for _ in range(c_p): self._acc["r_hip_pelvis"].popleft()
                for _ in range(c_t): self._acc["r_hip_thigh"].popleft()

        # Knee RIGHT
        if self.right_thigh_inlet and self.right_shank_inlet:
            q_t = list(self._acc["r_knee_thigh"])
            q_s = list(self._acc["r_knee_shank"])
            t_s, t_ts, s_s, s_ts, c_t, c_s = self._match_snapshots(q_t, q_s)
            if t_s:
                angles = self.__compute_angles_from_data(
                    t_s, t_ts, s_s, s_ts,
                    self.right_angle_offset, self._diag["right_thigh"],
                )
                self.right_angle_data = np.append(self.right_angle_data, angles)
                self.right_angle_timestamps = np.append(self.right_angle_timestamps, s_ts)
                for _ in range(c_t): self._acc["r_knee_thigh"].popleft()
                for _ in range(c_s): self._acc["r_knee_shank"].popleft()

        # Ankle RIGHT
        if self.right_shank_inlet and self.right_foot_inlet:
            q_s = list(self._acc["r_ankle_shank"])
            q_f = list(self._acc["r_ankle_foot"])
            s_s, s_ts, f_s, f_ts, c_s, c_f = self._match_snapshots(q_s, q_f)
            if s_s:
                ankle_angles = self.__compute_angles_from_data(
                    s_s, s_ts, f_s, f_ts,
                    self.right_ankle_offset, self._diag["right_shank"],
                    is_ankle=True,
                    proximal_axis=self.right_ankle_shank_axis,
                    distal_axis=self.right_ankle_foot_axis,
                    q_proximal_ref=getattr(self, 'right_ankle_qshank_ref', None),
                    q_distal_ref=getattr(self, 'right_ankle_qfoot_ref', None),
                    hinge_axis=getattr(self, 'right_ankle_hinge_axis', None),
                )
                self.right_ankle_data = np.append(self.right_ankle_data, ankle_angles)
                self.right_ankle_timestamps = np.append(self.right_ankle_timestamps, f_ts)
                for _ in range(c_s): self._acc["r_ankle_shank"].popleft()
                for _ in range(c_f): self._acc["r_ankle_foot"].popleft()"""
    content = content[:start_idx] + new_process + content[end_idx:]

with open("angle_calibrator.py", "w") as f:
    f.write(content)
print("Updated successfully")
