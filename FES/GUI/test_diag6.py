import pickle
import numpy as np

with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

for k, v in d.items():
    if "diag" in k or "ref" in k or "offset" in k:
        print(f"Found key: {k}")

if "_diag" in d:
    print("Found _diag dict!")
    for k, v in d["_diag"].items():
        print(f"  _diag[{k}] keys: {v.keys()}")

