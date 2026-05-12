import re

with open("angle_calibrator.py", "r") as f:
    content = f.read()

# Let's check how _acc is initialized.
match = re.search(r"self._acc\s*=\s*\{([^}]+)\}", content)
if match:
    print(match.group(0))

