import os
from dotenv import load_dotenv

# Load .env every time config is imported (safe to call multiple times)
load_dotenv()

# Zero-config local database: a SQLite file next to the project root.
# Used whenever DATABASE_URL isn't set, so the app runs immediately without
# requiring a MySQL server to be installed/running. Set DATABASE_URL (e.g. to
# a mysql+pymysql://... URI) to use MySQL instead — see .env.example.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SQLITE_URI = "sqlite:///" + os.path.join(_BASE_DIR, "pbqms_dev.sqlite3")


class BaseConfig:
    SECRET_KEY                     = os.environ.get("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO                = False
    REDIS_URL                      = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL              = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    SMS_PROVIDER                   = os.environ.get("SMS_PROVIDER", "mock")
    DIALOG_USER                    = os.environ.get("DIALOG_USER", "")
    DIALOG_PASS                    = os.environ.get("DIALOG_PASS", "")
    DIALOG_SENDER_ID               = os.environ.get("DIALOG_SENDER_ID", "PPLSBANK")
    MOBITEL_TOKEN                  = os.environ.get("MOBITEL_TOKEN", "")
    MOBITEL_SENDER_ID              = os.environ.get("MOBITEL_SENDER_ID", "PPLSBANK")
    TWILIO_SID                     = os.environ.get("TWILIO_SID", "")
    TWILIO_TOKEN                   = os.environ.get("TWILIO_TOKEN", "")
    TWILIO_FROM                    = os.environ.get("TWILIO_FROM", "")
    BASE_URL                       = os.environ.get("BASE_URL", "http://localhost:5000")
    MAX_CONTENT_LENGTH             = 16 * 1024 * 1024


class DevelopmentConfig(BaseConfig):
    DEBUG                      = True
    # Falls back to a local SQLite file so the app works out of the box
    # with no MySQL server required. Set DATABASE_URL to opt into MySQL.
    SQLALCHEMY_DATABASE_URI    = os.environ.get("DATABASE_URL", DEFAULT_SQLITE_URI)


class ProductionConfig(BaseConfig):
    DEBUG                      = False
    ENV                        = "production"
    # In production DATABASE_URL should always be set explicitly; this only
    # prevents a hard crash on import if it's missing.
    SQLALCHEMY_DATABASE_URI    = os.environ.get("DATABASE_URL", DEFAULT_SQLITE_URI)
    SESSION_COOKIE_SECURE      = True
    SESSION_COOKIE_HTTPONLY    = True
    REMEMBER_COOKIE_SECURE     = True
    REMEMBER_COOKIE_HTTPONLY   = True
    SESSION_COOKIE_SAMESITE    = "Lax"
    PERMANENT_SESSION_LIFETIME = 3600


class TestingConfig(BaseConfig):
    TESTING                    = True
    SQLALCHEMY_DATABASE_URI    = "sqlite:///" + os.path.join(_BASE_DIR, "pbqms_test.sqlite3")
    WTF_CSRF_ENABLED           = False


config_by_name = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     DevelopmentConfig,
}
