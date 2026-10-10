"""Core logic: geometry maths and multimon_config.sii generation.

This module deliberately has no GUI/Qt dependency so it can be unit-tested
and reused from a CLI if desired.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

ETS2_FOLDER_NAME = "Euro Truck Simulator 2"


# ============================================================
# MATHS
# ============================================================

def fov_degrees(size_mm: float, distance_mm: float) -> float:
    """Field of view (degrees) of a screen dimension seen from a distance."""
    if size_mm <= 0:
        raise ValueError("The monitor size must be greater than 0.")
    if distance_mm <= 0:
        raise ValueError("The eye distance must be greater than 0.")
    return math.degrees(2.0 * math.atan((size_mm / 2.0) / distance_mm))


def size_from_diagonal(diagonal_inch: float) -> tuple[float, float]:
    """Width and height (mm) of a 16:9 screen from its diagonal in inches."""
    if diagonal_inch <= 0:
        raise ValueError("The diagonal must be greater than 0.")
    scale = diagonal_inch * 25.4 / math.hypot(16, 9)
    return 16 * scale, 9 * scale


def bezel_angle_degrees(width_mm: float, distance_mm: float, bezel_mm: float) -> float:
    """Angular correction (degrees) produced by the bezel between two monitors."""
    if bezel_mm <= 0 or width_mm <= 0 or distance_mm <= 0:
        return 0.0
    without_bezel = math.atan((width_mm / 2.0) / distance_mm)
    with_bezel = math.atan(((width_mm + bezel_mm) / 2.0) / distance_mm)
    return math.degrees(with_bezel - without_bezel)


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class Settings:
    # Physical dimensions
    width_mm: float = 700.0
    height_mm: float = 395.0
    bezel_mm: float = 15.0
    distance_mm: float = 700.0
    side_angle: float = 54.0

    # Camera
    camera_x: float = 0.0
    camera_y: float = 0.0
    camera_z: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0

    # FOV
    auto_fov: bool = True
    fov_h: float = 53.13
    fov_v: float = 31.36
    center_h_rel: float = 0.0
    left_h_rel: float = 0.0
    right_h_rel: float = 0.0
    center_v_rel: float = 0.0
    left_v_rel: float = 0.0
    right_v_rel: float = 0.0

    # Advanced
    render_interior: bool = True
    render_exterior: bool = True
    frustum_x: float = 0.0
    frustum_y: float = 0.0
    frustum_w: float = 1.0
    frustum_h: float = 1.0

    def validate(self) -> None:
        if self.width_mm <= 0:
            raise ValueError("The width must be greater than 0.")
        if self.height_mm <= 0:
            raise ValueError("The height must be greater than 0.")
        if self.distance_mm <= 0:
            raise ValueError("The distance must be greater than 0.")
        if self.bezel_mm < 0:
            raise ValueError("The bezel cannot be negative.")
        if not 0 < self.side_angle < 90:
            raise ValueError("The angle must be between 0 and 90 degrees.")


@dataclass(frozen=True)
class Geometry:
    fov_h: float
    fov_v: float
    bezel_angle: float
    left_heading: float
    right_heading: float


def compute_geometry(s: Settings) -> Geometry:
    s.validate()
    bezel_angle = bezel_angle_degrees(s.width_mm, s.distance_mm, s.bezel_mm)

    if s.auto_fov:
        fov_h = fov_degrees(s.width_mm, s.distance_mm)
        fov_v = fov_degrees(s.height_mm, s.distance_mm)
    else:
        fov_h, fov_v = s.fov_h, s.fov_v

    # The bezel angle is added to the physical angle.
    left = s.side_angle + bezel_angle
    return Geometry(
        fov_h=fov_h,
        fov_v=fov_v,
        bezel_angle=bezel_angle,
        left_heading=left,
        right_heading=-left,
    )


# ============================================================
# SII GENERATION
# ============================================================

def _bool(value: bool) -> str:
    return "true" if value else "false"


def _monitor_block(
    name: str,
    normalized_x: str,
    heading: float,
    h_rel: float,
    v_rel: float,
    s: Settings,
    g: Geometry,
) -> str:
    return f"""monitor_config : _nameless.{name} {{
 name: {name}

 normalized_x: {normalized_x}
 normalized_y: 0.000000
 normalized_width: 0.333333
 normalized_height: 1.000000

 heading_offset: {heading:.6f}
 pitch_offset: {s.pitch:.6f}
 roll_offset: {s.roll:.6f}

 camera_space_offset: ({s.camera_x:.6f}, {s.camera_y:.6f}, {s.camera_z:.6f})

 horizontal_fov_relative_offset: {h_rel:.6f}
 vertical_fov_relative_offset: {v_rel:.6f}

 horizontal_fov_override: {g.fov_h:.6f}
 vertical_fov_override: {g.fov_v:.6f}

 frustum_subrect_x: {s.frustum_x:.6f}
 frustum_subrect_y: {s.frustum_y:.6f}
 frustum_subrect_width: {s.frustum_w:.6f}
 frustum_subrect_height: {s.frustum_h:.6f}

 render_interior: {_bool(s.render_interior)}
 render_exterior: {_bool(s.render_exterior)}
}}
"""


def generate_sii(s: Settings) -> str:
    g = compute_geometry(s)

    center = _monitor_block("center", "0.333333", 0.0, s.center_h_rel, s.center_v_rel, s, g)
    left = _monitor_block("left", "0.000000", g.left_heading, s.left_h_rel, s.left_v_rel, s, g)
    right = _monitor_block("right", "0.666667", g.right_heading, s.right_h_rel, s.right_v_rel, s, g)

    header = """SiiNunit
{
multimon_config : _nameless.0 {
 normalized_ui_x: 0.333333
 normalized_ui_width: 0.333333

 monitors: 3
 monitors[0]: _nameless.center
 monitors[1]: _nameless.left
 monitors[2]: _nameless.right
}
"""
    return f"{header}\n{center}\n{left}\n{right}}}\n"


# ============================================================
# TEXT SUMMARIES
# ============================================================

def preview_text(s: Settings, g: Geometry) -> str:
    rule = "-" * 28

    def row(label: str, value: str) -> str:
        return f"{label:<20}{value:>10}"

    lines = [
        "GEOMETRY",
        rule,
        row("Physical angle:", f"{s.side_angle:.3f}°"),
        row("Bezel correction:", f"{g.bezel_angle:.3f}°"),
        row("Left heading:", f"+{g.left_heading:.3f}°"),
        row("Center heading:", "0.000°"),
        row("Right heading:", f"{g.right_heading:.3f}°"),
        "",
        "FOV",
        rule,
        row("Horizontal:", f"{g.fov_h:.3f}°"),
        row("Vertical:", f"{g.fov_v:.3f}°"),
        "",
        "CAMERA",
        rule,
        row("X:", f"{s.camera_x:.3f} m"),
        row("Y:", f"{s.camera_y:.3f} m"),
        row("Z:", f"{s.camera_z:.3f} m"),
        row("Pitch:", f"{s.pitch:.3f}°"),
        row("Roll:", f"{s.roll:.3f}°"),
        "",
        "FRUSTUM",
        rule,
        row("X:", f"{s.frustum_x:.3f}"),
        row("Y:", f"{s.frustum_y:.3f}"),
        row("Width:", f"{s.frustum_w:.3f}"),
        row("Height:", f"{s.frustum_h:.3f}"),
    ]
    return "\n".join(lines)


# ============================================================
# PLATFORM HELPERS
# ============================================================

def ets2_user_dir(documents: Path | None = None) -> Path:
    """Best guess for the ETS2 user-data folder, falling back to Documents/home."""
    home = Path.home()
    fallback = documents if documents and documents.is_dir() else home

    if sys.platform == "win32":
        candidate = (documents or home / "Documents") / ETS2_FOLDER_NAME
    elif sys.platform == "darwin":
        candidate = home / "Library" / "Application Support" / ETS2_FOLDER_NAME
    else:
        candidate = home / ".local" / "share" / ETS2_FOLDER_NAME

    return candidate if candidate.is_dir() else fallback
