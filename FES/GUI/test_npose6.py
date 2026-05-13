import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

q_sh = np.asarray(d["raw_right_shank_quat"], dtype=np.float64)

def find_npose_from_variance(q_prox, q_dist, window_len=60):
    if len(q_prox) < window_len: return 0, len(q_prox)
    variances = []
    # step by 10 to speed up
    for i in range(0, len(q_prox) - window_len, 10):
        v1 = np.sum(np.var(q_prox[i:i+window_len], axis=0))
        if q_dist is not None:
            v2 = np.sum(np.var(q_dist[i:i+window_len], axis=0))
            variances.append(v1 + v2)
        else:
            variances.append(v1)
    best_idx = np.argmin(variances) * 10
    return best_idx, best_idx + window_len

best_start, best_end = find_npose_from_variance(q_sh, None, 60)
print(f"Variance-based npose: {best_start} to {best_end}")

