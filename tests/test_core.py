import pytest

from ets2_triple_monitor.core import (
    Settings,
    bezel_angle_degrees,
    compute_geometry,
    fov_degrees,
    generate_sii,
)


def test_fov_square_case():
    # Width == 2 * distance -> half-angle is 45 deg -> FOV is 90 deg
    assert fov_degrees(1400, 700) == pytest.approx(90.0)


def test_fov_default_monitor():
    assert fov_degrees(700, 700) == pytest.approx(53.1301, abs=1e-3)
    assert fov_degrees(395, 700) == pytest.approx(31.5121, abs=1e-3)


def test_bezel_angle_zero_cases():
    assert bezel_angle_degrees(700, 700, 0) == 0.0
    assert bezel_angle_degrees(0, 700, 15) == 0.0
    assert bezel_angle_degrees(700, 0, 15) == 0.0


def test_bezel_angle_default():
    assert bezel_angle_degrees(700, 700, 15) == pytest.approx(0.4890, abs=1e-3)


def test_geometry_headings_are_symmetric():
    g = compute_geometry(Settings())
    assert g.left_heading == pytest.approx(54.4890, abs=1e-3)
    assert g.right_heading == pytest.approx(-g.left_heading)


def test_manual_fov_is_used_when_auto_is_off():
    g = compute_geometry(Settings(auto_fov=False, fov_h=60.0, fov_v=35.0))
    assert (g.fov_h, g.fov_v) == (60.0, 35.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width_mm": 0},
        {"height_mm": -1},
        {"distance_mm": 0},
        {"bezel_mm": -0.1},
        {"side_angle": 0},
        {"side_angle": 90},
    ],
)
def test_validation_errors(kwargs):
    with pytest.raises(ValueError):
        generate_sii(Settings(**kwargs))


def test_sii_structure():
    sii = generate_sii(Settings())
    assert sii.startswith("SiiNunit\n{\n")
    assert sii.rstrip().endswith("}")
    assert sii.count("monitor_config : _nameless.") == 3
    assert "monitors: 3" in sii
    assert "heading_offset: 54.488999" in sii
    assert "heading_offset: -54.488999" in sii
    assert "horizontal_fov_override: 53.130102" in sii
    assert "render_interior: true" in sii
    # Braces must be balanced
    assert sii.count("{") == sii.count("}")


def test_sii_render_flags_and_camera():
    sii = generate_sii(Settings(render_exterior=False, camera_z=-0.25))
    assert "render_exterior: false" in sii
    assert "camera_space_offset: (0.000000, 0.000000, -0.250000)" in sii
