import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "software"))

import app

# Test instantiating the app with withdrawn root to verify all UI widgets build cleanly
def test_app():
    a = app.ASLTranslatorApp()
    a.withdraw()  # don't pop up window
    print("ASLTranslatorApp successfully initialized with HandVisualizerWidget and Telemetry Tab!")
    a.update()
    a.on_close()
    print("Clean exit succeeded.")

if __name__ == "__main__":
    test_app()
