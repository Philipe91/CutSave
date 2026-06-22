import os

# Qt roda sem display (headless) durante os testes.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
