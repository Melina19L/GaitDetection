with open("angle_calibrator.py", "r") as f:
    content = f.read()

bad_indent = """                if self.left_angle_data.size > MAX_BUFFER:
            self.left_angle_data       = self.left_angle_data[-MAX_BUFFER:]"""
            
good_indent = """        if self.left_angle_data.size > MAX_BUFFER:
            self.left_angle_data       = self.left_angle_data[-MAX_BUFFER:]"""

content = content.replace(bad_indent, good_indent)

with open("angle_calibrator.py", "w") as f:
    f.write(content)
