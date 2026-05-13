with open("angle_calibrator.py") as f:
    in_func = False
    for line in f:
        if line.startswith("    def _match_snapshots("):
            in_func = True
        if in_func:
            print(line, end='')
            if line.strip() == "return q_prox_sync, ts_prox_sync, q_dist_sync, ts_dist_sync, used_prox, used_dist":
                break
