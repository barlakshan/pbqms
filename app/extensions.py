from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_socketio import SocketIO

db            = SQLAlchemy()
migrate       = Migrate()
login_manager = LoginManager()
socketio      = SocketIO()

login_manager.login_view    = "auth_api.login_page"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))
