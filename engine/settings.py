from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple, Optional
from engine.ui.style import Theme, WaitIndicatorStyle

try:
    import yaml
except Exception:
    yaml = None
    
@dataclass
class WindowCfg:
    width: int = 1280
    height: int = 720
    title: str = "HORIZON"
    bg_rgb: tuple[int, int, int] = (14, 15, 18)
    
@dataclass
class TextboxCfg:
    width_frac: float = 0.4
    height_frac: float = 0.8
    
@dataclass
class InputCfg:
    scroll_wheel_pixels: int = 40
    page_scroll_frac: float = 0.9
    
@dataclass
class RevealCfg:
    per_line_delay: float = 0.15            # Wait uthis long after a line before releasing another line
    intro_duration: float = 0.18            # Fade/slide duration for each line
    intro_offset_px: int = 10               # How many pixels the new line slides up from
    stick_to_bottom_threshold_px: int = 24  # If user is within threshoild from the bottom, keep scrolling
    chars_per_sec: float = 45.0             # Float for char rate
    pause_short_s: float = 0.06             # , ; :
    pause_long_s: float = 0.25              # . ! ?
    pause_ellipsis_s: float = 0.35          # "..."
    
    
@dataclass
class AppCfg:
    fps: int = 60
    window: WindowCfg = field(default_factory=WindowCfg)
    textbox: TextboxCfg = field(default_factory=TextboxCfg)
    input: InputCfg = field(default_factory=InputCfg)
    reveal: RevealCfg = field(default_factory=RevealCfg)
    
    
def _get(d: dict, path: str, default: Any):
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

def load_settings(path: str = "game/config/defaults.yaml") -> AppCfg:
    data = {}
    p = Path(path)
    if yaml and p.exists():
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    return AppCfg(
        fps=int(_get(data, "fps", 60)),
        window=WindowCfg(
            width=int(_get(data, "window.width", 1280)),
            height=int(_get(data, "window.height", 720)),
            title=str(_get(data, "window.title", "HORIZON")),
            bg_rgb=tuple(_get(data, "window.bg_rgb", (14, 15, 18))),
        ),
        textbox=TextboxCfg(
            width_frac=float(_get(data, "ui.textbox.width_frac", 0.4)),
            height_frac=float(_get(data, "ui.textbox.height_frac", 0.8)),
        ),
        input=InputCfg(
            scroll_wheel_pixels=int(_get(data, "input.scroll_wheel_pixels", 40)),
            page_scroll_frac=float(_get(data, "input.page_scroll_frac", 0.9)),
        ),
        reveal=RevealCfg(
            per_line_delay=float(_get(data, "ui.textbox.reveal.per_line_delay", 0.15)),
            intro_duration=float(_get(data, "ui.textbox.reveal.intro_duration", 0.18)),
            intro_offset_px=float(_get(data, "ui.textbox.reveal.intro_offset_px", 10)),
            stick_to_bottom_threshold_px=float(_get(data, "ui.textbox.reveal.stick_to_bottom_threshold_px", 24)),
            chars_per_sec=float(_get(data, "ui.textbox.reveal.chars_per_sec", 45.0)),
            pause_short_s=float(_get(data, "ui.textbox.reveal.pause_short_s", 0.06)),
            pause_long_s=float(_get(data, "ui.textbox.reveal.pause_long_s", 0.25)),
            pause_ellipsis_s=float(_get(data, "ui.textbox.reveal.pause_ellipsis_s", 0.35)),
        ),
    )
    
def load_ui_defaults(path: str = "game/config/defaults.yaml") -> Dict[str, Any]:
    """ Load UI/game defaults from YAML (textbox/theme/scrollbar/backgrounds/etc). """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data

def build_theme_from_defaults(defaults: Dict[str, Any]) -> Theme:
    tdata = defaults.get("theme", {}) or {}
    th = Theme()
    
     # core
    th.font_path     = tdata.get("font_path", th.font_path)
    th.font_size     = int(tdata.get("font_size", th.font_size))
    th.text_rgb      = tuple(tdata.get("text_rgb", th.text_rgb))
    th.box_bg        = tuple(tdata.get("box_bg", getattr(th, "box_bg", (10,10,10,170))))
    th.box_border    = tuple(tdata.get("box_border", getattr(th, "box_border", (255,255,255,160))))
    th.border_radius = int(tdata.get("border_radius", th.border_radius))
    th.padding       = tuple(tdata.get("padding", th.padding))
    th.line_spacing  = int(tdata.get("line_spacing", th.line_spacing))
    th.entry_gap     = int(tdata.get("entry_gap", getattr(th, "entry_gap", 6)))

    # scrollbar
    sc = tdata.get("scrollbar", {}) or {}
    th.scrollbar.width               = int(sc.get("width", th.scrollbar.width))
    th.scrollbar.margin              = int(sc.get("margin", th.scrollbar.margin))
    th.scrollbar.radius              = int(sc.get("radius", th.scrollbar.radius))
    th.scrollbar.min_thumb_size      = int(sc.get("min_thumb_size", th.scrollbar.min_thumb_size))
    th.scrollbar.show_when_no_overflow = bool(sc.get("show_when_no_overflow", th.scrollbar.show_when_no_overflow))
    th.scrollbar.track_color         = tuple(sc.get("track_color", th.scrollbar.track_color))
    th.scrollbar.thumb_color         = tuple(sc.get("thumb_color", th.scrollbar.thumb_color))
    # optional nudge
    setattr(th.scrollbar, "offset_x", int(sc.get("offset_x", getattr(th.scrollbar, "offset_x", 0))))

    # choice panel
    ch = tdata.get("choice", {}) or {}
    setattr(th, "choice_inset_px",              int(ch.get("inset_px", getattr(th, "choice_inset_px", 12))))
    setattr(th, "choice_padding",               tuple(ch.get("padding", getattr(th, "choice_padding", (8,10,8,10)))))
    setattr(th, "choice_radius_delta",          int(ch.get("radius_delta", getattr(th, "choice_radius_delta", -4))))
    setattr(th, "choice_underline_thickness",   int(ch.get("underline_thickness", getattr(th, "choice_underline_thickness", 2))))
    setattr(th, "choice_anim_duration",         float(ch.get("anim_duration", getattr(th, "choice_anim_duration", 0.18))))
    setattr(th, "choice_slide_px",              int(ch.get("slide_px", getattr(th, "choice_slide_px", 8))))

    # wait indicator
    wi = tdata.get("wait_indicator", {}) or {}
    th.wait_indicator.enabled   = bool(wi.get("enabled", th.wait_indicator.enabled))
    th.wait_indicator.char      = wi.get("char", th.wait_indicator.char)
    th.wait_indicator.color     = tuple(wi.get("color", th.wait_indicator.color))
    th.wait_indicator.period    = float(wi.get("period", th.wait_indicator.period))
    th.wait_indicator.alpha_min = int(wi.get("alpha_min", th.wait_indicator.alpha_min))
    th.wait_indicator.alpha_max = int(wi.get("alpha_max", th.wait_indicator.alpha_max))
    th.wait_indicator.offset_x  = int(wi.get("offset_x", th.wait_indicator.offset_x))
    th.wait_indicator.offset_y  = int(wi.get("offset_y", th.wait_indicator.offset_y))
    th.wait_indicator.scale     = float(wi.get("scale", th.wait_indicator.scale))
    th.wait_indicator.font_path = wi.get("font_path", th.wait_indicator.font_path)
    return th

def textbox_fracs_from_defaults(defaults: Dict[str, Any], fallback: Tuple[float, float]) -> Tuple[float, float]:
    tb = defaults.get("textbox", {}) or {}
    return (
        float(tb.get("width_frac", fallback[0])),
        float(tb.get("height_frac", fallback[1]))
    )
    
def reveal_overrides_from_defaults(defaults: Dict[str, Any]) -> dict:
    rv = defaults.get("reveal", {}) or {}
    return {
        "per_line_delay": float(rv.get("per_line_delay", 0.15)),
        "intro_duration": float(rv.get("intro_duration", 0.18)),
        "intro_offset_px": int(rv.get("intro_offset_px", 10)),
        "stick_to_bottom_threshold_px": int(rv.get("stick_to_bottom_threshold_px", 24)),
        "chars_per_sec": float(rv.get("chars_per_sec", 45.0)),
        "pause_short_s": float(rv.get("pause_short_s", 0.06)),
        "pause_long_s": float(rv.get("pause_long_s", 0.25)),
        "pause_ellipsis_s": float(rv.get("pause_ellipsis_s", 0.35)),
    }
    
def presenter_overrides_from_defaults(defaults: Dict[str, Any]) -> dict:
    pr = defaults.get("presenter", {}) or {}
    return {
        "clear_after_nodes": int(pr.get("clear_after_nodes", 0)),
        "insert_node_separator": bool(pr.get("insert_node_separator", True)),
        "separator_text": str(pr.get("separator_text", "")),
    }