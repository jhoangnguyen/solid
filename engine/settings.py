from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
        ),
    )