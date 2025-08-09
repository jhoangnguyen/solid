from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None
    
from engine.app import GameApp, GameConfig

def load_config() -> GameConfig:
    cfg_path = Path("game/config/defaults.yaml")
    if yaml and cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return GameConfig(
            width=int(data.get("width", 1200)),
            height=int(data.get("heihgt", 720)),
            title=str(data.get("title", "HORIZON")),
            bg_rgb=tuple(data.get("bg_rgb", (14, 15, 18))),
            fps=int(data.get("fps", 60))
        )
    return GameConfig()

def main():
    app = GameApp(load_config())
    app.run()
    
if __name__ == "__main__":
    main()
    