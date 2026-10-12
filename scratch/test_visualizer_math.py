import math
import numpy as np
import sys
from pathlib import Path

# Add software dir to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "software"))

from hand_visualizer import OrientationCalculator, HandKinematics

def test_orientation():
    calc = OrientationCalculator()

    # Flat rest position: Az = 16384, Ax = 0, Ay = 0
    p, r, y = calc.update([0, 0, 16384], [0, 0, 0], [0, 0, 0])
    print(f"Flat rest: pitch={math.degrees(p):.2f} deg, roll={math.degrees(r):.2f} deg")
    assert abs(math.degrees(p)) < 2.0, "Pitch should be ~0"
    assert abs(math.degrees(r)) < 2.0, "Roll should be ~0"

    # Pitch up (fingers up): +Y points to wrist so +Y points down => Ay < 0
    # Feed multiple frames so low-pass filter converges
    for _ in range(20):
        p, r, y = calc.update([0, -11585, 11585], [0, 0, 0], [0, 0, 0])
    print(f"Pitch up (45 deg): pitch={math.degrees(p):.2f} deg")
    assert math.degrees(p) > 35.0, f"Pitch should be positive, got {math.degrees(p)}"

    # Pitch down (fingers down): +Y points to wrist so +Y points up => Ay > 0
    for _ in range(20):
        p, r, y = calc.update([0, 11585, 11585], [0, 0, 0], [0, 0, 0])
    print(f"Pitch down (-45 deg): pitch={math.degrees(p):.2f} deg")
    assert math.degrees(p) < -35.0, f"Pitch should be negative, got {math.degrees(p)}"

    R = calc.get_rotation_matrix()
    assert R.shape == (3, 3)
    # Check orthogonality
    np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-5)
    print("Rotation matrix is valid SO(3) orthonormal matrix.")

def test_kinematics():
    kin = HandKinematics()

    # Test flat Left hand
    res_flat = kin.compute_skeleton("LEFT", [0.0, 0.0, 0.0, 0.0, 0.0])
    pts_flat = res_flat["points"]
    assert "index_tip" in pts_flat
    assert "middle_tip" in pts_flat
    assert "thumb_tip" in pts_flat
    print("Flat Left hand index_tip:", pts_flat["index_tip"])

    # Test bent Left hand
    res_bent = kin.compute_skeleton("LEFT", [1.0, 1.0, 1.0, 1.0, 1.0])
    pts_bent = res_bent["points"]
    print("Bent Left hand index_tip:", pts_bent["index_tip"])

    # In bent fist, tip should be curled closer to wrist in Y and lower in Z
    assert pts_bent["index_tip"][1] < pts_flat["index_tip"][1], "Bent tip Y should be shorter than flat tip Y"
    assert pts_bent["index_tip"][2] < pts_flat["index_tip"][2], "Bent tip Z should be lower (curled into palm)"

    # Test Right hand
    res_right = kin.compute_skeleton("RIGHT", [0.0, 0.0, 0.0, 0.0, 0.0])
    pts_right = res_right["points"]
    # In Right hand, thumb should be on opposite side in X compared to Left hand
    assert np.sign(pts_right["thumb_tip"][0]) == -np.sign(pts_flat["thumb_tip"][0]), "Thumb X should be mirrored for Right hand"
    print("Kinematics tests passed!")

if __name__ == "__main__":
    test_orientation()
    test_kinematics()
    print("ALL TESTS PASSED!")
