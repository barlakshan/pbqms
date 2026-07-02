import os
from dotenv import load_dotenv

# Load .env FIRST before anything else imports config
load_dotenv()

from app import create_app
from app.extensions import socketio

# Default to development so DATABASE_URL has a fallback
env = os.environ.get("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=(env == "development"),
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
