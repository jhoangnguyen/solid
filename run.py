from pathlib import Path

try:
    import yaml
except Exception:
    yaml = None
    
from engine.app import GameApp
from engine.settings import load_settings

def main():
    app = GameApp(load_settings())
    app.run()

if __name__ == "__main__":
    main()
    