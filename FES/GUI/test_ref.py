import pickle
import numpy as np

with open("try3.pkl", "rb") as f:
    d = pickle.load(f)

def qnorm(q):
    n = np.linalg.norm(q, axis=-1, keepdims=True)
    return q / (n + 1e-12)

q_th = qnorm(np.asarray(d["raw_right_thigh_quat"], dtype=np.float64))
ref = slice(1834, 1893)
q_ref_window = q_th[ref]

print("Mean of q_ref_window:", q_ref_window.mean(axis=0))
print("Std of q_ref_window:", q_ref_window.std(axis=0))

