# Save this file as api/index.py in your repo root (Vercel Python entrypoint).
# It must sit NEXT TO app.py, not inside it. Vercel maps /api/index.py -> all routes.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app  # noqa: E402  Flask app, routes defined in app.py
# Vercel looks for `app` in this module.
