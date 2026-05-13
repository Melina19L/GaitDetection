import pickle
import numpy as np

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

q_sh = np.asarray(d["raw_right_shank_quat"], dtype=np.float64)

def find_npose_from_variance_first_30s(q_prox, window_len=60, max_search_samples=1800):
    if len(q_prox) < window_len: return 0, len(q_prox)
    search_end = min(len(q_prox) - window_len, max_search_samples)
    
    variances = []
    for i in range(0, search_end, 10):
        v = np.sum(np.var(q_prox[i:i+window_len], axis=0))
        variances.append(v)
    best_idx = np.argmin(variances) * 10
    return best_idx, best_idx + window_len

best_start, best_end = find_npose_from_variance_first_30s(q_sh, 60, 1800)
print(f"First 30s variance-based npose: {best_start} to {best_end}")
