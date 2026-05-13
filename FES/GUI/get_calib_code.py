with open("angle_calibrator.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if "def __calculate_angles(" in line:
        start = i
        break
for i in range(start, len(lines)):
    if "return" in lines[i] and i > start + 5:
        print("".join(lines[start:i+2]))
        break
