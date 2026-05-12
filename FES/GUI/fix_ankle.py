with open("angle_calibrator.py", "r") as f:
    content = f.read()

bad_left = """                    self.left_ankle_offset, self._diag["left_shank"],
                    is_ankle=True,
                    proximal_axis=self.left_ankle_shank_axis,"""

good_left = """                    self.left_ankle_offset, self._diag["left_shank"],
                    is_ankle=False,
                    proximal_axis=self.left_ankle_shank_axis,"""

bad_right = """                    self.right_ankle_offset, self._diag["right_shank"],
                    is_ankle=True,
                    proximal_axis=self.right_ankle_shank_axis,"""

good_right = """                    self.right_ankle_offset, self._diag["right_shank"],
                    is_ankle=False,
                    proximal_axis=self.right_ankle_shank_axis,"""

content = content.replace(bad_left, good_left)
content = content.replace(bad_right, good_right)

with open("angle_calibrator.py", "w") as f:
    f.write(content)
