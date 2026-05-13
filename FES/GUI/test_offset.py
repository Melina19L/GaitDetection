import pickle
with open("try6.pkl", "rb") as f:
    d = pickle.load(f)

print("right_knee_offset:", d.get("right_knee_offset", "Not found"))
print("right_hip_offset:", d.get("right_hip_offset", "Not found"))

