with open("analyze_gait_cycle.py") as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if "Cycle (HS→HS)" in l or "Ciclo del passo" in l or "plot" in l.lower():
        print(f"{i}: {l.strip()}")

