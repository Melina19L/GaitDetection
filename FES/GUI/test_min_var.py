import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

q_sh = d["raw_right_shank_quat"]
if len(q_sh) > 0:
    n_samples = 60 # 1 second at 60 Hz
    variances = []
    for i in range(0, len(q_sh) - n_samples, 10):
        window = q_sh[i:i+n_samples]
        # Calculate sum of variances of the 4 quaternion components
        var = np.sum(np.var(window, axis=0))
        variances.append(var)
    
    min_idx = np.argmin(variances) * 10
    print(f"Lowest variance window starts at index {min_idx}, variance = {variances[np.argmin(variances)]}")
    
    # print timestamps of this window
    ts = d["raw_right_shank_timestamps"]
    print(f"Time range: {ts[min_idx]} to {ts[min_idx+n_samples]}")

