import re

with open("angle_calibrator.py", "r") as f:
    content = f.read()

bad_record = """                elif key == "right_foot":
                    self._acc["r_ankle_foot"].extend(paired)

        # ── 2. Snapshot pelvis (shared between both hips) ─────────────────────"""

good_record = """                elif key == "right_foot":
                    self._acc["r_ankle_foot"].extend(paired)

                self._diag[key]["count"]  += len(samples)
                self._diag[key]["last_ts"] = now
                if hasattr(self, '_raw_log') and key in self._raw_log:
                    for ts, s in paired:
                        self._raw_log[key].append([ts] + list(s))

        # ── 2. Snapshot pelvis (shared between both hips) ─────────────────────"""

content = content.replace(bad_record, good_record)

with open("angle_calibrator.py", "w") as f:
    f.write(content)

