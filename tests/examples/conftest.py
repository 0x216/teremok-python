import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Locale compilation for the pizza example happens inside the example module
# itself (examples/pizza_order_bot.py compiles .po -> .mo at import time),
# so simply importing it - as its tests do - is enough.
