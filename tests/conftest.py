import os

# Qt widgets in tests run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
