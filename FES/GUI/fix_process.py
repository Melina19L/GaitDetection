import re

with open("angle_calibrator.py", "r") as f:
    content = f.read()

start_idx = content.find("        # ── 2. Snapshot pelvis (shared between both hips) ─────────────────────")
end_idx = content.find("        if self.left_angle_data.size > MAX_BUFFER:")

if start_idx == -1 or end_idx == -1:
    print("Could not find start or end bounds.")
    exit(1)

# Find the end of the except block for the IndexError
end_block = content.find("        except IndexError:", start_idx)
if end_block != -1:
    end_print = content.find('print("Warning: Attempted to pop from empty accumulation queue.")', end_block)
    if end_print != -1:
        end_idx = end_print + len('print("Warning: Attempted to pop from empty accumulation queue.")') + 1

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
                for _ in range(c_f): self._acc["r_ankle_foot"].popleft()
"""

new_content = content[:start_idx] + new_process + "\n        " + content[end_idx:]

with open("angle_calibrator.py", "w") as f:
    f.write(new_content)

print("Process block updated.")
