#!/usr/bin/env python3
"""Synthetic-quaternion test to verify axis detection functions.

Tests realistic sensor mountings with correct sagittal-plane alignment:
  1. Legacy mounting: shank X = gravity, foot X = forward
  2. User's mounting: foot Z = gravity, Y = forward (toward toes)
  3. With yaw offset and heading mismatches

Run from the GUI directory:
    python3 verify_axis_detection.py
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stimulator.closed_loop import (
    detect_most_vertical_axis,
    detect_most_horizontal_axis,
    detect_foot_medio_lateral_axis,
    rotate_vector_by_quaternion,
    signed_ankle_angle,
    normalize,
    AXIS_VECTORS,
)
from scipy.spatial.transform import Rotation as R


def quat_wxyz(r: R) -> np.ndarray:
    """scipy Rotation → [w,x,y,z] quaternion."""
    q = r.as_quat()  # [x,y,z,w]
    return np.array([q[3], q[0], q[1], q[2]])


def test_axis_projections(q, label):
    """Print how each local axis projects into the world frame."""
    print(f"\n  {label} axis projections:")
    for name, v in AXIS_VECTORS.items():
        gv = rotate_vector_by_quaternion(v, q)
        gv_n = gv / (np.linalg.norm(gv) + 1e-9)
        vert = abs(gv_n[2])
        horiz = 1.0 - vert
        print(f"    {name}: global=[{gv[0]:+.3f}, {gv[1]:+.3f}, {gv[2]:+.3f}]  "
              f"vert={vert:.3f}  horiz={horiz:.3f}")


def run_test(test_name, q_shank, q_foot,
             expected_shank_vert, expected_foot_fwd, expected_foot_ml):
    """Run detection and verify results."""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    test_axis_projections(q_shank, "Shank")
    test_axis_projections(q_foot, "Foot")

    shank_vert = detect_most_vertical_axis(q_shank)
    foot_fwd = detect_most_horizontal_axis(q_foot, q_shank)
    foot_ml = detect_foot_medio_lateral_axis(q_foot, q_shank)
    foot_grav = detect_most_vertical_axis(q_foot)

    print(f"\n  Detected axes:")
    print(f"    Shank vertical:      {shank_vert}  (expected: {expected_shank_vert})")
    print(f"    Foot gravity:        {foot_grav}")
    print(f"    Foot forward:        {foot_fwd}  (expected: {expected_foot_fwd})")
    print(f"    Foot medio-lateral:  {foot_ml}  (expected: {expected_foot_ml})")

    ok = True
    if shank_vert != expected_shank_vert:
        print(f"  ❌ FAIL: shank_vert={shank_vert}, expected={expected_shank_vert}")
        ok = False
    if foot_fwd != expected_foot_fwd:
        print(f"  ❌ FAIL: foot_fwd={foot_fwd}, expected={expected_foot_fwd}")
        ok = False
    if foot_ml != expected_foot_ml:
        print(f"  ❌ FAIL: foot_ml={foot_ml}, expected={expected_foot_ml}")
        ok = False
    if ok:
        print(f"  ✅ PASS")
    return ok


def test_signed_ankle_angle(test_name, q_shank, q_foot, q_shank_ref, q_foot_ref,
                             foot_axis, expected_abs_deg, tolerance=3.0):
    """Test that signed_ankle_angle magnitude matches expected value."""
    angle = signed_ankle_angle(q_shank, q_foot, q_shank_ref, q_foot_ref, foot_axis)
    ok = abs(abs(angle) - expected_abs_deg) < tolerance
    status = "✅ PASS" if ok else "❌ FAIL"
    print(f"\n  Signed ankle angle test: {test_name}")
    print(f"    angle={angle:.2f}°  |angle|={abs(angle):.2f}°  expected |angle|={expected_abs_deg:.1f}°  (tol={tolerance}°)  {status}")
    return ok


# ── Rotation builders ──

TILT = 5.0  # degrees of forward shank tilt


def make_shank_quat(yaw_deg=0.0):
    """Build a shank quaternion: local X → near-gravity, tilted TILT° forward.
    
    Applies pitch first (around Y), then yaw (around Z) — extrinsic/world-frame.
    """
    # First tilt the shank so X points nearly down (85° pitch around Y)
    r_pitch = R.from_euler('y', 90 - TILT, degrees=True)
    # Then apply yaw in the world frame (extrinsic rotation around Z)
    r_yaw = R.from_euler('z', yaw_deg, degrees=True)
    return quat_wxyz(r_yaw * r_pitch)


def make_foot_user_quat(yaw_deg=0.0):
    """Build a foot quaternion for the user's mounting:
      local Z → gravity (global -Z)
      local Y → forward (global +X, toward toes)  
      local X → mediolateral (global +Y, to the left)
    """
    M = np.array([
        [0,  1,  0],
        [1,  0,  0],
        [0,  0, -1],
    ], dtype=float)
    r_base = R.from_matrix(M)
    r_yaw = R.from_euler('z', yaw_deg, degrees=True)
    return quat_wxyz(r_yaw * r_base)


def make_foot_legacy_quat(yaw_deg=0.0):
    """Legacy: local X → forward (+X), local Y → ML (+Y), local Z → up (+Z)."""
    r = R.from_euler('z', yaw_deg, degrees=True)
    return quat_wxyz(r)


def main():
    results = []

    # ── Test 1: Legacy mounting ──
    q_shank = make_shank_quat(yaw_deg=0)
    q_foot = make_foot_legacy_quat(yaw_deg=0)
    results.append(run_test(
        "Legacy mounting (shank X≈gravity, foot X=forward)",
        q_shank, q_foot,
        expected_shank_vert='X', expected_foot_fwd='X', expected_foot_ml='Y',
    ))

    # ── Test 2: User's mounting ──
    q_foot_user = make_foot_user_quat(yaw_deg=0)
    results.append(run_test(
        "User's mounting (foot Z=gravity, Y=forward, X=ML)",
        q_shank, q_foot_user,
        expected_shank_vert='X', expected_foot_fwd='Y', expected_foot_ml='X',
    ))

    # ── Test 3: Both sensors rotated 30° yaw ──
    q_shank_30 = make_shank_quat(yaw_deg=30)
    q_foot_30 = make_foot_user_quat(yaw_deg=30)
    results.append(run_test(
        "User's mounting + 30° yaw rotation (both sensors)",
        q_shank_30, q_foot_30,
        expected_shank_vert='X', expected_foot_fwd='Y', expected_foot_ml='X',
    ))

    # ── Test 4: 15° heading mismatch between sensors ──
    q_foot_mismatch = make_foot_user_quat(yaw_deg=15)
    results.append(run_test(
        "User's mounting + 15° yaw mismatch between sensors",
        q_shank, q_foot_mismatch,
        expected_shank_vert='X', expected_foot_fwd='Y', expected_foot_ml='X',
    ))

    # ── Test 5: signed_ankle_angle at neutral ──
    q_shank_ref = q_shank
    q_foot_ref = q_foot_user
    results.append(test_signed_ankle_angle(
        "Neutral pose (should be 0°)",
        q_shank, q_foot_user, q_shank_ref, q_foot_ref,
        foot_axis='X', expected_abs_deg=0.0,
    ))

    # ── Test 6: 15° rotation around foot-X ──
    M_base = np.array([[0,1,0],[1,0,0],[0,0,-1]], dtype=float)
    r_foot_base = R.from_matrix(M_base)
    r_dorsi = R.from_euler('x', 15, degrees=True)
    q_foot_dorsi = quat_wxyz(r_foot_base * r_dorsi)
    results.append(test_signed_ankle_angle(
        "15° rotation around foot-X (ML axis)",
        q_shank, q_foot_dorsi, q_shank_ref, q_foot_ref,
        foot_axis='X', expected_abs_deg=15.0, tolerance=3.0,
    ))

    # ── Test 7: 20° rotation around foot-X ──
    r_plantar = R.from_euler('x', -20, degrees=True)
    q_foot_plantar = quat_wxyz(r_foot_base * r_plantar)
    results.append(test_signed_ankle_angle(
        "20° rotation around foot-X (ML axis)",
        q_shank, q_foot_plantar, q_shank_ref, q_foot_ref,
        foot_axis='X', expected_abs_deg=20.0, tolerance=3.0,
    ))

    # ── Summary ──
    print(f"\n{'='*60}")
    n_pass = sum(results)
    n_total = len(results)
    print(f"RESULTS: {n_pass}/{n_total} tests passed")
    if all(results):
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    print(f"{'='*60}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
