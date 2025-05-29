import atexit
import os
import signal
import sys
import threading

import dotenv
from flask import Flask
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect
from flask_compress import Compress
from flask_turnstile import Turnstile

from cache import init_redis
from extensions import db, login_manager
from config import init_protections, COMPRESS_ENABLED, COMPRESS_LEVEL, COMPRESS_MIN_SIZE
from models import User, init_db
from services.scheduler import init_scheduler, scheduler, stop_event
from services.news_service import NewsService

dotenv.load_dotenv()


def signal_handler(signum: int, frame: object) -> None:
    """Handles signals for graceful shutdown.

    Args:
        signum (int): Signal number.
        frame (object): Current stack frame.
    """
    stop_event.set()

    try:
        from routes import symbols_db_pool

        symbols_db_pool.close_all()
    except (ImportError, AttributeError):
        pass

    sys.exit(0)

def initialize_database(app):
    """Initialize the database schema and default data."""
    with app.app_context():
        try:
            connection = db.engine.connect()

            inspector = db.inspect(db.engine)
            tables_exist = inspector.get_table_names()

            if not tables_exist:
                db.create_all()

                init_db(app)
            else:
                pass

            connection.close()
        except:
            pass

def initialize_recommendations(app, silent=False):
    """Initialize stock recommendations if not already cached.

    Args:
        app (Flask): The Flask application instance.
        silent (bool): Whether to suppress log messages.
    """
    with app.app_context():
        try:
            from cache import redis_client
            import time
            import json

            if not redis_client:
                if not silent:
                    print("Redis not available, skipping recommendations initialization")
                return

            try:
                from services.stockrecommender import StockRecommender
            except ImportError:
                if not silent:
                    print("StockRecommender not available, skipping recommendations initialization")
                return

            lock_key = "init_recommendations_lock"
            lock_value = redis_client.set(
                lock_key,
                "1",
                ex=10,
                nx=True
            )

            if not lock_value:
                if os.getenv("APP_ENV") == "development" and not silent:
                    print("Another worker is initializing recommendations, skipping...")
                return

            try:
                recommender = StockRecommender()
                stocks = recommender.get_cached_recommendations(asset_type="stock")
                cryptos = recommender.get_cached_recommendations(asset_type="crypto")

                force_refresh = False

                if stocks:
                    for stock in stocks:
                        if not stock.symbol or stock.symbol == '--' or stock.name == 'N/A':
                            if not silent:
                                print("Found invalid stock data in cache, forcing refresh")
                            force_refresh = True
                            break

                if cryptos and not force_refresh:
                    for crypto in cryptos:
                        if not crypto.symbol or crypto.symbol == '--' or crypto.name == 'N/A':
                            if not silent:
                                print("Found invalid crypto data in cache, forcing refresh")
                            force_refresh = True
                            break

                if not stocks or not cryptos or force_refresh:
                    if not silent:
                        print("Generating initial stock and crypto recommendations...")
                    stocks, cryptos = recommender.get_all_recommendations()
                    if not silent:
                        print(f"Initialized {len(stocks)} stock and {len(cryptos)} crypto recommendations!")
                else:
                    if not silent and (stocks or cryptos):
                        existing = []
                        if stocks:
                            existing.append(f"{len(stocks)} stocks")
                        if cryptos:
                            existing.append(f"{len(cryptos)} cryptos")
                        print(f"Recommendations already cached: {', '.join(existing)}")
            finally:
                redis_client.delete(lock_key)

        except Exception as e:
            if not silent:
                print(f"Error initializing recommendations: {str(e)}")

def init_news_thread(app, silent=False):
    """Initialize news service in a separate thread with proper application context.

    Args:
        app (Flask): The Flask application instance.
        silent (bool): Whether to suppress log messages.
    """
    with app.app_context():
        try:
            news_service = NewsService()
            news_service.reindex_news()
            news_service.start()
            if not silent:
                print("News service initialized successfully")
        except Exception as e:
            if not silent:
                print(f"Error initializing news service: {str(e)}")

def create_app() -> Flask:
    """Creates and configures the Flask application.

    Returns:
        Flask: Configured Flask application.
    """
    app = Flask(
        __name__, static_url_path="", static_folder="static", template_folder="templates"
    )

    compress = Compress()
    app.config['COMPRESS_ENABLED']      = COMPRESS_ENABLED
    app.config['COMPRESS_LEVEL']        = COMPRESS_LEVEL
    app.config['COMPRESS_MIMETYPES']    = [
        'text/html',
        'text/css',
        'text/xml',
        'application/json',
        'application/javascript',
        'text/javascript',
        'application/x-javascript'
    ]
    app.config['COMPRESS_ALGORITHM']    = 'gzip'
    app.config['COMPRESS_MIN_SIZE']     = COMPRESS_MIN_SIZE
    compress.init_app(app)

    app.config['TURNSTILE_ENABLED']     = os.getenv('CF_TURNSTILE_ENABLED', 'true').lower() == 'true'
    app.config['TURNSTILE_SITE_KEY']    = os.getenv('CF_SITE_KEY')
    app.config['TURNSTILE_SECRET_KEY']  = os.getenv('CF_SECRET_KEY')
    turnstile                           = Turnstile()
    turnstile.init_app(app)

    atexit.register(lambda: scheduler.shutdown() if scheduler.running else None)

    def cleanup_sqlite_pool():
        try:
            from routes import symbols_db_pool

            symbols_db_pool.close_all()
        except (ImportError, AttributeError):
            pass

    atexit.register(cleanup_sqlite_pool)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY", os.getenv("FLASK_SECRET_KEY")
    )

    # IMPORTANT: Set SERVER_NAME in .env file for your domain
    app.config['SERVER_NAME'] = os.getenv('SERVER_NAME')
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.config['APPLICATION_ROOT'] = '/'

    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    db_provider     = os.getenv("DB_PROVIDER")
    mysql_user      = os.getenv("MYSQL_USER")
    mysql_password  = os.getenv("MYSQL_PASSWORD")
    mysql_host      = os.getenv("MYSQL_HOST")
    mysql_db        = os.getenv("MYSQL_DB")
    aurora_user     = os.getenv("AURORA_USER")
    aurora_password = os.getenv("AURORA_PASSWORD")
    aurora_host     = os.getenv("AURORA_HOST")
    aurora_port     = os.getenv("AURORA_PORT")
    aurora_db       = os.getenv("AURORA_DB")

    if db_provider == "aurora":
        cert_path = os.path.join(os.path.dirname(__file__), "certs", "global-bundle.pem")
        ssl_params = {
            "sslmode": "verify-full",
            "sslrootcert": cert_path
        }
        db_uri = (
            f"postgresql+psycopg2://{aurora_user}:{aurora_password}@{aurora_host}:{aurora_port}"
            f"/{aurora_db}?sslmode={ssl_params['sslmode']}&sslrootcert={ssl_params['sslrootcert']}"
        )
    else:
        db_uri = f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}/{mysql_db}"

    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": 20,
        "max_overflow": 20,
        "pool_recycle": 1800,
        "pool_timeout": 30,
        "pool_pre_ping": True,
        "connect_args": ssl_params if db_provider == "aurora" else {}
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["REDIS_HOST"]    = os.environ.get("REDIS_HOST", "localhost")
    app.config["REDIS_PORT"]    = int(os.environ.get("REDIS_PORT", 6379))
    app.config["REDIS_DB"]      = int(os.environ.get("REDIS_DB", 0))

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    init_protections(app)

    db.init_app(app)
    initialize_database(app)
    migrate = Migrate(app, db)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: int) -> User:
        """Loads a user from the database.

        Args:
            user_id (int): The ID of the user to load.

        Returns:
            User: The loaded user object.
        """
        return db.session.get(User, int(user_id))

    from routes import init_routes
    init_routes(app)
    init_scheduler(app)
    init_redis(app)

    is_worker = 'gunicorn' in os.environ.get('SERVER_SOFTWARE', '') or os.environ.get('GUNICORN_WORKER', '') == 'true'
    initialize_recommendations(app, silent=is_worker)

    news_thread = threading.Thread(target=init_news_thread, args=(app, is_worker), daemon=True)
    news_thread.start()

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        initialize_database(app)

    app_env = os.getenv("APP_ENV")
    if app_env == "production":
        app.run(
            host="0.0.0.0",
            port=80,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    else:
        app.run(debug=True, use_reloader=False)
