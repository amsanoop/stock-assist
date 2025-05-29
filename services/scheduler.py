import atexit
from datetime import datetime, timedelta
from threading import Thread, Event

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask
from flask_apscheduler import APScheduler

from models import News, User, UserSession, db
from services.news_service import NewsService
from tasks import cleanup_expired_sessions

scheduler            = APScheduler()
stop_event           = Event()
background_scheduler = BackgroundScheduler()
flask_app            = None


def init_scheduler(app: Flask) -> None:
    """Initializes the scheduler with the Flask app and starts the jobs.

    Args:
        app (Flask): The Flask application instance.
    """
    global flask_app, scheduler, stop_event
    flask_app = app

    def cleanup():
        """Stops all schedulers."""
        stop_event.set()
        scheduler.shutdown()
        background_scheduler.shutdown()

    atexit.register(cleanup)

    scheduler.init_app(app)
    scheduler.start()

    def run_news_update():
        """Runs the news update job in a separate thread."""
        while not stop_event.is_set():
            with app.app_context():
                try:
                    check_and_update_news()
                except Exception as e:
                    pass
            stop_event.wait(timeout=3600)

    update_thread = Thread(target=run_news_update, daemon=True)
    update_thread.start()

    with app.app_context():
        background_scheduler.add_job(
            reset_daily_limits_job,
            trigger=CronTrigger(minute='*/15'),
            id='reset_daily_limits',
            name='Check and reset daily message limits',
            replace_existing=True
        )
        
        background_scheduler.add_job(
            cleanup_expired_sessions_job,
            trigger=CronTrigger(minute='*/30'),
            id='cleanup_expired_sessions',
            name='Clean up expired user sessions',
            replace_existing=True
        )
        
        background_scheduler.add_job(
            update_stock_recommendations_job,
            trigger=CronTrigger(hour='*/8'),
            id='update_stocks',
            name='Update stock recommendations',
            replace_existing=True
        )
        
        background_scheduler.start()

    if not scheduler.running:
        scheduler.add_job(
            reset_daily_limits,
            trigger=CronTrigger(hour=0, minute=0),
            id='reset_daily_limits',
            name='Reset user daily message and image limits',
            replace_existing=True
        )
        
        scheduler.add_job(
            cleanup_expired_sessions,
            trigger=CronTrigger(hour=1, minute=0),
            id='cleanup_sessions',
            name='Clean up expired user sessions',
            replace_existing=True
        )

        scheduler.add_job(
            reset_daily_limits,
            trigger='date',
            run_date=datetime.now() + timedelta(seconds=5),
            id='initial_reset_check',
            name='Initial reset limits check'
        )

        scheduler.start()


def check_and_update_news():
    """Updates news and deletes old news articles."""
    try:
        news_service = NewsService()
        news_service.update_news()

        with db.session.begin():
            old_news = News.query.order_by(News.published_at.desc()).offset(50).all()
            for news in old_news:
                db.session.delete(news)
            db.session.commit()
    except:
        db.session.rollback()


def update_stock_recommendations_job():
    """Update stock recommendations scheduled job wrapper.
    Uses locking mechanism to ensure only one instance updates recommendations
    when using multiple gunicorn workers.
    """
    if flask_app is None:
        return
    
    with flask_app.app_context():
        from services.stockrecommender import StockRecommender
        from cache import redis_client
        import time
        
        if not redis_client:
            print("Redis not available, skipping recommendations update")
            return
        
        lock_key = "update_recommendations_lock"
        lock_timestamp = datetime.utcnow().timestamp()
        lock_value = redis_client.set(
            lock_key,
            str(lock_timestamp),
            ex=300,
            nx=True
        )
        
        if not lock_value:
            return
            
        try:
            recommender = StockRecommender()
            stocks = recommender.get_recommended_stocks()
            cryptos = recommender.get_recommended_crypto()
            
            if stocks and len(stocks) > 0:
                print(f"{datetime.utcnow()}: Successfully updated {len(stocks)} stock recommendations")
            else:
                print(f"{datetime.utcnow()}: WARNING - Failed to retrieve valid stock recommendations")
                
            if cryptos and len(cryptos) > 0:
                print(f"{datetime.utcnow()}: Successfully updated {len(cryptos)} crypto recommendations")
            else:
                print(f"{datetime.utcnow()}: WARNING - Failed to retrieve valid crypto recommendations")
                
        except Exception as e:
            print(f"{datetime.utcnow()}: Error updating recommendations: {str(e)}")
        finally:
            redis_client.delete(lock_key)


def reset_daily_limits_job():
    """Check and reset limits for users whose next_reset time has passed.

    Runs every 15 minutes to ensure limits are reset even after server restarts.
    Forces a reset at midnight UTC and sets next reset date appropriately.
    """
    if flask_app is None:
        return

    with flask_app.app_context():
        User.reset_all_daily_limits()


def cleanup_expired_sessions_job():
    """Clean up expired user sessions.

    Runs every 30 minutes to ensure expired sessions are cleaned up.
    """
    if flask_app is None:
        return

    with flask_app.app_context():
        count = UserSession.cleanup_expired_sessions()
        if count > 0:
            print(f"{datetime.utcnow()}: Cleaned up {count} expired sessions")


def reset_daily_limits():
    """Reset daily message and image limits for users whose limits have expired."""
    try:
        from flask import current_app

        with current_app.app_context():
            reset_count = User.reset_all_daily_limits()
            if reset_count > 0:
                print(f"{datetime.utcnow()}: Reset daily limits for {reset_count} users")
    except Exception as e:
        print(f"Error resetting daily limits: {str(e)}")