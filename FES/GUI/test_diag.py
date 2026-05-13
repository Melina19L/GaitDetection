import pickle
import numpy as np

with open("try4.pkl", "rb") as f:
    d = pickle.load(f)

for k, v in d.items():
    if "diag" in k or "ref" in k or "offset" in k:
        print(f"Found key: {k}")

