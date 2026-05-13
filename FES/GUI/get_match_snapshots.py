with open("angle_calibrator.py") as f:
    in_func = False
    for line in f:
        if line.strip().startswith("def _match_snapshots"):
            in_func = True
        if in_func:
            print(line, end='')
            if line.strip().startswith("return"):
                break
