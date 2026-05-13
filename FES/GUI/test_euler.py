from scipy.spatial.transform import Rotation as R
import numpy as np

# Pure Y rotation
theta = np.linspace(-60, 60, 100)
q = R.from_euler('Y', theta, degrees=True)
eulers = q.as_euler('ZXY', degrees=True)
print("Max Z angle:", np.max(np.abs(eulers[:, 0])))
print("Max X angle:", np.max(np.abs(eulers[:, 1])))
print("Max Y angle:", np.max(np.abs(eulers[:, 2])))
