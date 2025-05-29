import eventlet
eventlet.monkey_patch()

import difflib
import hashlib
import io
import json
import logging
import os
import queue
import re
import requests
import secrets
import sqlite3
import threading
import time
import traceback
import uuid
import magic

from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
    session,
)
from flask_login import current_user, login_required
from flask_socketio import SocketIO, emit
from flask_wtf import FlaskForm
from tradingview_ta import Interval, TA_Handler
from werkzeug.utils import secure_filename
from wtforms import IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, Length, NumberRange

from blueprints.auth import auth
from cache import (
    cache_db_query,
    cached,
    get_cached_query,
    invalidate_cache_pattern,
    redis_client,
)
from config import csrf, limiter, COMMON_STOCKS, CRYPTO_SYMBOLS, ALPHA_VANTAGE_API_KEY, BASE_URL, symbols_db_pool
from extensions import db
from models import (
    AIOperation,
    Chat,
    ChatImage,
    ChatMessage,
    RedemptionKey,
    StockWatchlist,
    Subscription,
    User,
    UserSession,
    News,
)
from services.ai_service import AIService
from services.news_service import NewsService
from services.tools import format_stock_data, get_system_prompt, google_tools
from services.stockrecommender import StockRecommender
from utils.analytics import send_ga_event
from utils.ip import get_ip

LANGUAGES = {
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
    "ru": "Русский",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "ar": "العربية",
    "hi": "हिन्दी",
    "nl": "Nederlands",
    "sv": "Svenska",
    "tr": "Türkçe",
    "pl": "Polski",
    "el": "Ελληνικά",
    "id": "Bahasa Indonesia",
    "ms": "Bahasa Melayu",
    "th": "ภาษาไทย",
    "vi": "Tiếng Việt",
    "uk": "Українська",
    "ro": "Română",
    "cs": "Čeština",
    "da": "Dansk",
    "fi": "Suomi",
    "no": "Norsk",
    "hu": "Magyar",
    "sk": "Slovenčina",
    "bg": "Български",
    "hr": "Hrvatski",
    "lt": "Lietuvių",
    "lv": "Latviešu",
    "et": "Eesti",
    "sr": "Српски",
    "sl": "Slovenščina",
    "sq": "Shqip",
    "mk": "Македонски",
    "be": "Беларуская",
    "az": "Azərbaycan",
    "ka": "ქართული",
    "hy": "Հայերեն",
    "kk": "Қазақ тілі",
    "ky": "Кыргызча",
    "tg": "Тоҷикӣ",
    "tk": "Türkmen dili",
    "uz": "Oʻzbek tili",
    "mn": "Монгол",
    "ps": "پښتو",
    "ur": "اردو",
    "fa": "فارسی",
    "am": "አማርኛ",
    "sw": "Kiswahili",
    "xh": "isiXhosa",
    "zu": "isiZulu",
    "af": "Afrikaans",
    "ga": "Gaeilge",
    "cy": "Cymraeg",
    "lb": "Lëtzebuergesch",
    "mt": "Malti",
    "is": "Íslenska",
    "yi": "ייִדיש",
    "eo": "Esperanto",
    "eu": "Euskara",
    "gl": "Galego",
    "ca": "Català",
    "oc": "Occitan",
    "co": "Corsu",
    "gd": "Gàidhlig",
    "br": "Brezhoneg",
    "fy": "Frysk",
    "sc": "Sardu",
    "rm": "Rumantsch",
    "la": "Latina",
}

load_dotenv()

def get_symbol_suggestions(query: str, max_suggestions: int = 5) -> list:
    """Suggests stock symbols based on a query string.

    Args:
        query (str): The query string to search for symbols.
        max_suggestions (int): The maximum number of suggestions to return.

    Returns:
        list: A list of dictionaries containing symbol suggestions.
    """
    from cache import get_cached_query, cache_db_query

    query = query.upper()

    cache_key = f"symbol_suggestions:{query}:{max_suggestions}"
    cached_result = get_cached_query(cache_key)
    if cached_result:
        return cached_result

    suggestions = []

    try:
        conn = symbols_db_pool.get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT screener, exchange, symbol, desc, 1 as match_type FROM tv 
                WHERE UPPER(symbol) = ? 

                UNION ALL

                SELECT screener, exchange, symbol, desc, 2 as match_type FROM tv 
                WHERE UPPER(symbol) LIKE ? AND UPPER(symbol) != ? 

                UNION ALL

                SELECT screener, exchange, symbol, desc, 3 as match_type FROM tv 
                WHERE UPPER(symbol) LIKE ? AND UPPER(symbol) NOT LIKE ? AND UPPER(symbol) != ? 

                UNION ALL

                SELECT screener, exchange, symbol, desc, 4 as match_type FROM tv 
                WHERE UPPER(desc) LIKE ? AND UPPER(symbol) NOT LIKE ? 

                ORDER BY match_type
                LIMIT ?
            """,
                (
                    query,
                    f"{query}%",
                    query,
                    f"%{query}%",
                    f"{query}%",
                    query,
                    f"%{query}%",
                    f"%{query}%",
                    max_suggestions,
                ),
            )

            all_matches = cursor.fetchall()

            for screener, exchange, symbol, desc, _ in all_matches:
                is_crypto = screener == "crypto"

                suggestions.append(
                    {
                        "symbol": symbol,
                        "name": desc,
                        "type": "crypto" if is_crypto else "stock",
                        "exchange": exchange,
                        "screener": screener,
                    }
                )
        finally:
            symbols_db_pool.return_connection(conn)
    except Exception as e:
        print(f"Error querying symbols database: {str(e)}")
        ALL_SYMBOLS = {**COMMON_STOCKS, **CRYPTO_SYMBOLS}

        symbol_matches = difflib.get_close_matches(
            query, ALL_SYMBOLS.keys(), n=max_suggestions, cutoff=0.6
        )

        if len(symbol_matches) < max_suggestions:
            remaining_slots = max_suggestions - len(symbol_matches)
            for symbol in ALL_SYMBOLS.keys():
                if query in symbol and symbol not in symbol_matches:
                    symbol_matches.append(symbol)
                    remaining_slots -= 1
                    if remaining_slots <= 0:
                        break

        name_matches = []
        for symbol, name in ALL_SYMBOLS.items():
            if query in name.upper() and symbol not in symbol_matches:
                name_matches.append(symbol)
                if len(name_matches) >= max_suggestions:
                    break

        for symbol in (symbol_matches + name_matches)[:max_suggestions]:
            is_crypto = symbol in CRYPTO_SYMBOLS

            suggestions.append(
                {
                    "symbol": symbol,
                    "name": ALL_SYMBOLS[symbol],
                    "type": "crypto" if is_crypto else "stock",
                    "exchange": "BINANCE"
                    if is_crypto
                    else (
                        "NASDAQ"
                        if symbol
                        in [
                            "AAPL",
                            "MSFT",
                            "GOOGL",
                            "AMZN",
                            "META",
                            "NVDA",
                            "TSLA",
                            "NFLX",
                            "INTC",
                            "AMD",
                        ]
                        else "NYSE"
                    ),
                    "screener": "crypto" if is_crypto else "america",
                }
            )

    cache_db_query(cache_key, suggestions, 3600)

    return suggestions


def validate_operation_ownership(
    operation_id: str, user_id: int = None
) -> tuple[AIOperation, bool]:
    """Validate AI operation ownership and existence.

    Args:
        operation_id (str): The ID of the operation to validate.
        user_id (int, optional): User ID to validate against. Defaults to current_user.id.

    Returns:
        tuple[AIOperation, bool]: Tuple containing the operation object and validation status.
    """
    if not operation_id:
        return None, False

    operation = AIOperation.query.get(operation_id)
    if not operation:
        return None, False

    if user_id is None:
        from flask_login import current_user

        if not current_user.is_authenticated:
            return operation, False
        user_id = current_user.id

    return operation, operation.user_id == user_id


def validate_chat_ownership(chat_id: int, user_id: int = None) -> tuple[Chat, bool]:
    """Validate chat ownership and existence.

    Args:
        chat_id (int): The ID of the chat to validate.
        user_id (int, optional): User ID to validate against. Defaults to current_user.id.

    Returns:
        tuple[Chat, bool]: Tuple containing the chat object and validation status.
    """
    if not chat_id:
        return None, False

    chat = Chat.query.get(chat_id)
    if not chat:
        return None, False

    if user_id is None:
        from flask_login import current_user

        if not current_user.is_authenticated:
            return chat, False
        user_id = current_user.id

    return chat, chat.user_id == user_id


def init_routes(app: Flask) -> None:
    """Initializes the routes for the Flask application.

    Args:
        app (Flask): The Flask application instance.

    Returns:
        None
    """
    global socketio
    socketio = SocketIO(
        app,
        async_mode='eventlet',
        cors_allowed_origins=["https://yourdomain.com"],
        logger=False,
        engineio_logger=False,
        ping_timeout=20,
        ping_interval=10,
    )

    logging.getLogger('socketio').setLevel(logging.ERROR)
    logging.getLogger('engineio').setLevel(logging.ERROR)
    
    @socketio.on('connect')
    def handle_connect():
        """Handle client connection."""
        try:
            if not current_user.is_authenticated:
                return False
            session['socket_id'] = request.sid
            socketio.emit('connection_success', {'status': 'connected'}, room=request.sid)
            return True
        except Exception:
            return True

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        try:
            if 'socket_id' in session:
                del session['socket_id']
        except Exception:
            pass

    @socketio.on_error_default
    def default_error_handler(e):
        """Handle all SocketIO errors silently."""
        pass

    @socketio.on_error('/chat')
    def chat_error_handler(e):
        """Handle chat namespace errors silently."""
        pass

    app.register_blueprint(auth, url_prefix="/auth")
    
    from blueprints.payments import payments_bp
    app.register_blueprint(payments_bp)

    @app.before_request
    def update_session_activity():
        """Update the last active time for the current session."""
        if current_user.is_authenticated:
            session_token = session.get('session_token')
            user_session = None
            
            if session_token:
                user_session = UserSession.query.filter_by(
                    session_token=session_token,
                    user_id=current_user.id,
                    is_active=True
                ).first()
                
                if user_session:
                    user_session.update_activity()
                    
                    current_ip = get_ip()
                    if user_session.ip_address != current_ip:
                        user_session.ip_address = current_ip
                        db.session.commit()
            
            if not user_session:
                remember = session.get('remember', False)
                new_session = UserSession.create_session(current_user.id, remember=remember, request=request)
                session['session_token'] = new_session.session_token

    @app.route("/robots.txt")
    @app.route("/Robots.txt")
    @csrf.exempt
    def robots():
        return send_from_directory(app.root_path, "robots.txt")

    @app.route("/sitemap.xml")
    @csrf.exempt
    def sitemap():
        return send_from_directory(app.root_path, "sitemap.xml")
    
    @app.route("/BingSiteAuth.xml")
    @csrf.exempt
    def bing_site_auth():
        return send_from_directory(app.root_path, "BingSiteAuth.xml")

    @app.route("/manifest.json")
    @csrf.exempt
    def manifest():
        return send_from_directory(os.path.join(app.root_path, "static"), "manifest.json")

    @app.route("/js/service-worker.js")
    @csrf.exempt
    def service_worker():
        response = make_response(send_from_directory(os.path.join(app.root_path, "static", "js"), "service-worker.js"))
        response.headers["Content-Type"] = "application/javascript"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.route("/.well-known/security.txt")
    @csrf.exempt
    def security_txt():
        return send_from_directory(
            os.path.join(app.root_path, ".well-known"), "security.txt"
        )

    @app.route("/security-policy")
    def security_policy():
        return render_template("security-policy.html")

    @app.route("/offline")
    @csrf.exempt
    def offline():
        return render_template("offline.html")

    @app.route("/")
    @csrf.exempt
    def index():
        metrics = get_website_metrics()
        return render_template("index.html", metrics=metrics)

    @app.route("/team")
    @csrf.exempt
    def team():
        return render_template("team.html")

    @app.route("/terms")
    @csrf.exempt
    def terms():
        return render_template("terms.html", now=datetime.utcnow())

    @app.route("/stocks")
    @csrf.exempt
    def stocks():
        symbol = request.args.get("symbol")
        recommender = StockRecommender()
        
        stock_recommendations, crypto_recommendations = recommender.get_all_recommendations()
            
        return render_template(
            "stocks.html", 
            initial_symbol=symbol, 
            stock_recommendations=stock_recommendations,
            crypto_recommendations=crypto_recommendations
        )

    @app.route("/chat")
    @csrf.exempt
    @login_required
    def chat():
        return render_template("chat.html")

    @app.route("/pricing")
    @csrf.exempt
    def pricing():
        return render_template("pricing.html")

    @app.route("/news")
    @csrf.exempt
    def news():
        """Render the news page, caching the HTML output.

        Returns:
            str: Rendered HTML of the news page.
        """
        is_paid: bool = current_user.is_authenticated and current_user.subscription.name != "Free"
        cache_key: str = f"news_html:{'paid' if is_paid else 'free'}"
        cache_key_md5: str = hashlib.md5(cache_key.encode()).hexdigest()

        if redis_client:
            cached_html = redis_client.get(f"html:{cache_key_md5}")
            if cached_html:
                response = make_response(cached_html.decode('utf-8'))
                response.headers['Content-Type'] = 'text/html'
                return response

        news_service = NewsService()
        news_items = news_service.get_latest_news(is_paid=is_paid, limit=20)
        rendered_html = render_template("news.html", news_items=news_items)

        if redis_client:
            redis_client.setex(f"html:{cache_key_md5}", 3600, rendered_html)

        return rendered_html

    @app.route("/js/chat.js")
    @csrf.exempt
    @login_required
    def chat_js():
        response = make_response(render_template("js/chat.js"))
        response.headers["Content-Type"] = "application/javascript"
        return response
    
    @app.route("/js/stocks.js")
    @csrf.exempt
    def stocks_js():
        response = make_response(send_from_directory(os.path.join(app.root_path, "templates", "js"), "stocks.js"))
        response.headers["Content-Type"] = "application/javascript"
        return response
    
    @app.route("/js/team.js")
    @csrf.exempt
    def team_js():
        response = make_response(send_from_directory(os.path.join(app.root_path, "static", "js"), "team.js"))
        response.headers["Content-Type"] = "application/javascript"
        return response

    @app.route("/api/stock/suggest/<query>")
    @csrf.exempt
    @limiter.limit("20 per minute")
    def suggest_symbols(query: str):
        """API endpoint to suggest stock symbols based on a query.

        Args:
            query (str): The query string to search for symbols.

        Returns:
            jsonify: A JSON response containing the symbol suggestions.
        """
        suggestions = get_symbol_suggestions(query)
        return jsonify(suggestions)

    @app.route("/api/stock/<symbol>")
    @csrf.exempt
    @limiter.limit("30 per minute")
    @cached(timeout=300)
    def get_stock_data(symbol: str):
        """API endpoint to get stock data for a given symbol.

        Args:
            symbol (str): The stock symbol to retrieve data for.

        Returns:
            jsonify: A JSON response containing the stock data or an error message.
        """
        try:
            if ":" in symbol:
                parts = symbol.split(":")
                if len(parts) != 2:
                    suggestions = get_symbol_suggestions(symbol)
                    return (
                        jsonify(
                            {
                                "error": "Invalid symbol format. Use 'EXCHANGE:SYMBOL' or just 'SYMBOL'",
                                "suggestions": suggestions,
                            }
                        ),
                        400,
                    )
            elif not re.match(r"^[A-Za-z0-9]{1,20}$", symbol):
                suggestions = get_symbol_suggestions(symbol)
                return (
                    jsonify(
                        {
                            "error": "Please enter a valid stock symbol (1-20 alphanumeric characters)",
                            "suggestions": suggestions,
                        }
                    ),
                    400,
                )

            symbol = symbol.upper()

            if symbol == "NONE":
                suggestions = get_symbol_suggestions("")
                return (
                    jsonify(
                        {
                            "error": "Please enter a stock symbol",
                            "suggestions": suggestions,
                        }
                    ),
                    400,
                )

            analysis = get_stock_analysis(symbol)

            if analysis is None:
                suggestions = get_symbol_suggestions(symbol)
                return (
                    jsonify(
                        {
                            "error": f'Could not find stock "{symbol}". Please check the symbol and try again.',
                            "suggestions": suggestions,
                        }
                    ),
                    404,
                )

            user_id = str(current_user.id) if current_user.is_authenticated else None
            subscription_type = current_user.subscription.name if current_user.is_authenticated else "Anonymous"
            send_ga_event(
                "stock_data_retrieved",
                user_id=user_id,
                event_params={
                    "symbol": symbol,
                    "subscription_type": subscription_type,
                    "is_crypto": analysis.get("is_crypto", False),
                    "exchange": analysis.get("exchange", "unknown")
                },
            )

            return jsonify(analysis)

        except Exception as e:
            print(f"Error for {symbol}: {str(e)}")
            traceback.print_exc()
            suggestions = get_symbol_suggestions(symbol)
            return (
                jsonify(
                    {
                        "error": f"An error occurred while fetching data for {symbol}. Please try again later.",
                        "suggestions": suggestions,
                    }
                ),
                500,
            )

    @app.route("/api/watchlist", methods=["GET", "POST", "DELETE"])
    @csrf.exempt
    @login_required
    @limiter.limit("30 per minute")
    def watchlist():
        """API endpoint to manage the user's stock watchlist.

        Returns:
            jsonify: A JSON response containing the watchlist data or an error message.
        """
        if request.method == "GET":
            stocks = StockWatchlist.query.filter_by(user_id=current_user.id).all()
            return jsonify(
                [
                    {
                        "symbol": stock.symbol,
                        "added_at": stock.added_at.isoformat(),
                        "notes": stock.notes,
                    }
                    for stock in stocks
                ]
            )

        elif request.method == "POST":
            data = request.get_json()
            symbol = data.get("symbol")
            notes = data.get("notes", "")

            if not symbol:
                return jsonify({"error": "Symbol is required"}), 400

            existing = StockWatchlist.query.filter_by(
                user_id=current_user.id, symbol=symbol
            ).first()

            if existing:
                return jsonify({"error": "Stock already in watchlist"}), 400

            watchlist_item = StockWatchlist(
                user_id=current_user.id, symbol=symbol, notes=notes
            )
            db.session.add(watchlist_item)
            db.session.commit()

            return jsonify(
                {
                    "symbol": symbol,
                    "added_at": watchlist_item.added_at.isoformat(),
                    "notes": notes,
                }
            )

        elif request.method == "DELETE":
            data = request.get_json()
            symbol = data.get("symbol")

            if not symbol:
                return jsonify({"error": "Symbol is required"}), 400

            watchlist_item = StockWatchlist.query.filter_by(
                user_id=current_user.id, symbol=symbol
            ).first()

            if not watchlist_item:
                return jsonify({"error": "Stock not found in watchlist"}), 404

            db.session.delete(watchlist_item)
            db.session.commit()

            return jsonify({"message": "Stock removed from watchlist"})

    @app.route("/api/chat/queue", methods=["POST"])
    @csrf.exempt
    @login_required
    @limiter.limit("20 per minute")
    def queue_chat_message():
        """Queues a chat message for processing.

        Receives message content, symbols, chat ID, and images from the request,
        performs validation, and creates a new chat if necessary.

        Returns:
            jsonify: A JSON response indicating success or failure with an appropriate HTTP status code.
        """
        try:
            data = request.form
            message = data.get("message")
            symbols = [s.strip() for s in data.get("symbols", "").split(",") if s.strip()]
            chat_id = data.get("chat_id")
            images = request.files.getlist("images")

            if not message:
                return jsonify({"error": "Message is required"}), 400

            ai_service = AIService()
            token_count = ai_service.token_count(message)
            if token_count > 500:
                return jsonify({"error": f"Message exceeds the 500 token limit (current: {token_count} tokens). Please shorten your message."}), 400

            if current_user.daily_message_count >= current_user.subscription.message_limit:
                return jsonify({"error": "Daily message limit reached"}), 403

            if len(images) > 1:
                return jsonify({"error": "Maximum 1 image per message allowed"}), 400

            if images and current_user.subscription.name == "Free":
                return jsonify({"error": "Image upload not available in Free plan"}), 403

            remaining_images = current_user.subscription.image_limit - current_user.daily_image_count
            if images and len(images) > remaining_images:
                return jsonify({"error": f"You can only upload {remaining_images} more images today"}), 403

            if chat_id:
                chat = Chat.query.get(chat_id)
                if not chat or chat.user_id != current_user.id:
                    return jsonify({"error": "Invalid chat ID"}), 404
            else:
                chat = Chat(user_id=current_user.id, title="Untitled Chat")
                db.session.add(chat)
                db.session.commit()
                chat_id = chat.id

            operation_id = str(uuid.uuid4())
            operation = AIOperation(
                id=operation_id,
                user_id=current_user.id,
                chat_id=chat_id,
                message=message,
                symbols=symbols,
                status="pending",
            )
            db.session.add(operation)

            user_message = ChatMessage(
                chat_id=chat.id,
                user_id=current_user.id,
                content=message,
                stock_symbols=symbols,
                is_user=True,
                has_image=bool(images),
            )
            db.session.add(user_message)
            db.session.flush()

            if images:
                image_data = []
                for image in images:
                    if image and image.filename:
                        filename = secure_filename(image.filename)
                        image_bytes = image.read()
                        mime = magic.Magic(mime=True)
                        mime_type = mime.from_buffer(image_bytes)

                        chat_image = ChatImage(
                            message_id=user_message.id,
                            original_filename=filename,
                            stored_filename=f"{uuid.uuid4()}_{filename}",
                            compressed_data=image_bytes,
                            mime_type=mime_type,
                        )
                        db.session.add(chat_image)

                        image_data.append({"name": filename, "mime_type": mime_type})

                if image_data:
                    operation.image_data = image_data
                    operation.message_id = user_message.id
                    current_user.daily_image_count += len(images)

            message_count = ChatMessage.query.filter_by(chat_id=chat.id).count()
            if message_count <= 1 and (chat.title == "New Chat" or chat.title == "Untitled Chat"):
                chat.title = message[:50] + "..." if len(message) > 50 else message

            current_user.daily_message_count += 1
            db.session.commit()

            invalidate_cache_pattern(f"db:*chat_messages:{chat.id}:*")
            invalidate_cache_pattern(f"db:*user_chats:{current_user.id}:*")

            db.session.flush()
            db.session.commit()

            if current_user.is_authenticated:
                send_ga_event(
                    "chat_message_sent",
                    user_id=str(current_user.id),
                    event_params={
                        "subscription_type": current_user.subscription.name,
                        "has_images": bool(images),
                        "image_count": len(images) if images else 0,
                        "symbols_count": len(symbols) if symbols else 0,
                        "message_length": len(message),
                        "token_count": token_count,
                        "daily_message_count": current_user.daily_message_count,
                        "daily_image_count": current_user.daily_image_count,
                    },
                )

            socketio.start_background_task(process_chat_operation, app=app, operation_id=operation_id)

            return jsonify(
                {
                    "operation_id": operation_id,
                    "chat_id": chat.id,
                    "messages_left": current_user.subscription.message_limit - current_user.daily_message_count,
                    "images_left": current_user.subscription.image_limit - current_user.daily_image_count,
                }
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Server error: {str(e)}"}), 500

    @app.route("/api/chat/status/<operation_id>")
    @csrf.exempt
    @login_required
    @limiter.limit("60 per minute")
    def get_chat_status(operation_id: str):
        """Get the status of a chat operation.

        Args:
            operation_id (str): The ID of the chat operation.

        Returns:
            jsonify: A JSON response containing the status of the chat operation.
        """
        operation, valid = validate_operation_ownership(operation_id)
        if not operation:
            return jsonify({"error": "Operation not found"}), 404
        if not valid:
            return jsonify({"error": "Unauthorized access to operation"}), 403

        response = {
            "status": operation.status,
            "current_step": operation.current_step,
            "steps": operation.steps,
            "created_at": operation.created_at.isoformat(),
            "updated_at": operation.updated_at.isoformat()
        }

        if operation.status == 'completed':
            response["result"] = operation.result
        elif operation.status == 'failed':
            response["error"] = operation.error

        return jsonify(response)

    @app.route("/api/chats", methods=["GET"])
    @csrf.exempt
    @login_required
    def get_chats():
        """API endpoint to get all chats for the current user.

        Returns:
            jsonify: A JSON response containing the list of chats and pagination information.
        """
        page: int = request.args.get('page', 1, type=int)
        per_page: int = request.args.get('per_page', 20, type=int)
        bypass_cache: bool = request.args.get('bypass_cache', '0') == '1'

        if per_page > 20:
            per_page = 20

        cache_key: str = f"user_chats:{current_user.id}:{page}:{per_page}"

        if not bypass_cache:
            cached_result = get_cached_query(cache_key)
            if cached_result:
                return jsonify(cached_result)

        query = (
            Chat.query
            .filter_by(user_id=current_user.id)
            .options(db.joinedload(Chat.messages))
            .order_by(Chat.updated_at.desc())
        )

        total_count: int = query.count()

        chats = query.limit(per_page).offset((page - 1) * per_page).all()

        result = {
            "chats": [{
                "id": chat.id,
                "title": chat.title,
                "created_at": chat.created_at.isoformat(),
                "updated_at": chat.updated_at.isoformat(),
                "last_message": chat.messages[-1].content if chat.messages else None
            } for chat in chats],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "pages": (total_count + per_page - 1) // per_page
            }
        }

        cache_db_query(cache_key, result, 60)

        return jsonify(result)

    @app.route("/api/chats/<int:chat_id>", methods=["GET"])
    @csrf.exempt
    @login_required
    def get_chat_messages(chat_id: int):
        """API endpoint to get all messages for a given chat.

        Args:
            chat_id (int): The ID of the chat.

        Returns:
            jsonify: A JSON response containing the chat messages.
        """
        cache_key: str = f"chat_messages:{chat_id}:{current_user.id}"
        cached_result = get_cached_query(cache_key)

        if cached_result:
            return jsonify(cached_result)

        chat, valid = validate_chat_ownership(chat_id)
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
        if not valid:
            return jsonify({"error": "Unauthorized access to chat"}), 403

        chat = (
            Chat.query.filter_by(id=chat_id, user_id=current_user.id)
            .options(db.joinedload(Chat.messages).selectinload(ChatMessage.images))
            .first_or_404()
        )

        result = {
            "id": chat.id,
            "title": chat.title,
            "messages": [
                {
                    "id": msg.id,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "stock_symbols": msg.stock_symbols if hasattr(msg, "stock_symbols") else None,
                    "is_user": msg.is_user,
                    "has_image": msg.has_image,
                    "images": [img.to_dict() for img in msg.images] if msg.has_image else [],
                }
                for msg in sorted(chat.messages, key=lambda m: m.created_at)
            ],
        }

        cache_db_query(cache_key, result, 30)

        return jsonify(result)

    @app.route("/api/news")
    @csrf.exempt
    @cached(timeout=600, include_query_params=True)
    def get_news():
        """API endpoint to get the latest news articles.

        Returns:
            jsonify: A JSON response containing the latest news articles.
        """
        from services.news_service import NewsService

        page: int = request.args.get("page", 1, type=int)
        per_page: int = request.args.get("per_page", 20, type=int)

        if per_page > 50:
            per_page = 50

        is_paid: bool = current_user.is_authenticated and current_user.subscription.name != "Free"
        news_service = NewsService()

        total_count: int = news_service.get_news_count(is_paid=is_paid)

        news_items = news_service.get_latest_news(is_paid=is_paid, page=page, per_page=per_page)

        result = {
            "news": [
                {
                    "id": news.id,
                    "title": news.title,
                    "summary": news.summary,
                    "source": news.source,
                    "source_link": news.source_link,
                    "published_at": news.published_at.isoformat(),
                    "symbols": news.symbols,
                    "urgency": news.urgency,
                    "provider": news.provider,
                }
                for news in news_items
            ],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "pages": (total_count + per_page - 1) // per_page,
            },
        }

        return jsonify(result)

    @app.route("/api/news/<int:news_id>")
    @csrf.exempt
    @cached(timeout=3600)
    def get_news_item(news_id: int):
        """API endpoint to get a specific news article by ID.

        Args:
            news_id (int): The ID of the news article.

        Returns:
            jsonify: A JSON response containing the news article.
        """
        from services.news_service import NewsService

        news_service = NewsService()
        news = news_service.get_news_by_id(news_id)

        if not news:
            return jsonify({"error": "News article not found"}), 404

        return jsonify(
            {
                "id": news.id,
                "title": news.title,
                "content": news.content,
                "summary": news.summary,
                "source": news.source,
                "source_link": news.source_link,
                "published_at": news.published_at.isoformat(),
                "symbols": news.symbols,
                "urgency": news.urgency,
                "provider": news.provider,
            }
        )

    @app.route("/api/news/update", methods=["POST"])
    @csrf.exempt
    @login_required
    @limiter.limit("5 per hour")
    def update_news():
        """API endpoint to update the news articles (Admin only).

        Returns:
            jsonify: A JSON response indicating the success of the news update.
        """
        if not current_user.subscription.name == "Admin":
            return jsonify({"error": "Unauthorized"}), 403

        from services.news_service import NewsService

        news_service = NewsService()
        news_service.update_news()
        return jsonify({"message": "News updated successfully"})

    @app.route("/api/chats/new", methods=["POST"])
    @csrf.exempt
    @login_required
    def create_new_chat():
        """API endpoint to create a new chat.

        Returns:
            jsonify: A JSON response containing the new chat ID.
        """
        chat = Chat(user_id=current_user.id, title="Untitled Chat")
        db.session.add(chat)
        db.session.commit()

        invalidate_cache_pattern(f"db:*user_chats:{current_user.id}:*")

        return jsonify({"chat_id": chat.id})

    @app.route("/api/chats/<int:chat_id>", methods=["DELETE"])
    @csrf.exempt
    @login_required
    def delete_chat(chat_id: int):
        """API endpoint to delete a chat.

        Args:
            chat_id (int): The ID of the chat to delete.

        Returns:
            jsonify: A JSON response indicating the success of the chat deletion.
        """
        chat, valid = validate_chat_ownership(chat_id)
        if not chat:
            return jsonify({"error": "Chat not found"}), 404
        if not valid:
            return jsonify({"error": "Unauthorized access to chat"}), 403

        try:
            ChatMessage.query.filter_by(chat_id=chat_id).delete()
            db.session.delete(chat)
            db.session.commit()

            invalidate_cache_pattern(f"db:*chat_messages:{chat_id}:*")

            invalidate_cache_pattern(f"db:*user_chats:{current_user.id}:*")

            return jsonify({"message": "Chat deleted successfully"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Failed to delete chat: {str(e)}"}), 500

    @app.route("/api/chats/cleanup", methods=["POST"])
    @csrf.exempt
    @login_required
    def cleanup_empty_chats():
        """API endpoint to cleanup empty chats."""
        try:
            empty_chats_subq = ~db.exists().where(ChatMessage.chat_id == Chat.id)
            Chat.query.filter(Chat.user_id == current_user.id, empty_chats_subq).delete(
                synchronize_session=False
            )

            db.session.commit()
            return jsonify({"message": "Empty chats cleaned up successfully"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Failed to cleanup chats: {str(e)}"}), 500

    @app.route("/api/chats/clear_all", methods=["DELETE"])
    @csrf.exempt
    @login_required
    def clear_all_chats():
        """API endpoint to clear all chats for the current user."""
        try:
            Chat.query.filter_by(user_id=current_user.id).delete(synchronize_session=False)
            db.session.commit()

            invalidate_cache_pattern(f"db:*user_chats:{current_user.id}:*")

            return jsonify({"message": "All chats cleared successfully"})
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing chats: {str(e)}")
            return jsonify({"error": f"Failed to clear chats: {str(e)}"}), 500

    @app.route("/api/user/language", methods=["GET", "POST"])
    @csrf.exempt
    @login_required
    def user_language():
        """Get or update the user's preferred language."""
        user = current_user

        if request.method == "POST":
            try:
                data = request.get_json()
                if not data or "language" not in data:
                    return jsonify({"error": "Language code is required"}), 400

                language = data["language"]
                if not isinstance(language, str) or len(language) > 10:
                    return jsonify({"error": "Invalid language code"}), 400

                user.preferred_language = language
                db.session.commit()
                return jsonify({"success": True, "language": language})
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        else:
            return jsonify({"language": user.preferred_language})

    @app.route("/api/metrics/usage", methods=["GET"])
    @csrf.exempt
    @login_required
    def get_usage_metrics():
        """Get current usage metrics for the user."""
        user = current_user

        if user.should_reset_limits():
            user.reset_daily_limits()
            db.session.commit()

        subscription = user.subscription
        time_until_reset = max(0, (user.next_reset - datetime.utcnow()).total_seconds())

        return jsonify(
            {
                "messages": {
                    "used": user.daily_message_count,
                    "limit": subscription.message_limit,
                    "percentage": (user.daily_message_count / subscription.message_limit) * 100
                    if subscription.message_limit > 0
                    else 0,
                },
                "images": {
                    "used": user.daily_image_count,
                    "limit": subscription.image_limit,
                    "percentage": (user.daily_image_count / subscription.image_limit) * 100
                    if subscription.image_limit > 0
                    else 0,
                },
                "next_reset": user.next_reset.isoformat(),
                "time_until_reset": time_until_reset,
                "preferred_language": user.preferred_language,
            }
        )

    @app.route("/api/metrics/admin", methods=["GET"])
    @csrf.exempt
    @login_required
    def get_admin_metrics():
        """Get system-wide usage metrics (admin only).

        Returns:
            jsonify: A JSON response containing the admin metrics.
        """
        if not current_user.subscription.name == "Admin":
            return jsonify({"error": "Unauthorized"}), 403

        near_limit_users = User.query.filter(
            User.daily_message_count >= 0.8 * User.subscription.has(Subscription.message_limit)
        ).count()

        limited_users = User.query.filter(
            User.daily_message_count >= User.subscription.has(Subscription.message_limit)
        ).count()

        return jsonify(
            {
                "users_near_limit": near_limit_users,
                "users_at_limit": limited_users,
                "next_scheduled_reset": (
                    datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                    + timedelta(days=1)
                ).isoformat(),
            }
        )

    @app.route("/api/chat/image/<int:image_id>")
    @csrf.exempt
    @login_required
    def get_chat_image(image_id: int):
        """Retrieve a specific chat image.

        Args:
            image_id (int): The ID of the chat image to retrieve.

        Returns:
            send_file: The requested chat image.
        """
        image = ChatImage.query.get_or_404(image_id)
        message = ChatMessage.query.get(image.message_id)

        if not message or message.user_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403

        return send_file(
            io.BytesIO(image.compressed_data),
            mimetype=image.mime_type,
            as_attachment=False,
            download_name=image.original_filename,
        )

    @app.route("/redeem", methods=["GET", "POST"])
    @csrf.exempt
    @login_required
    def redeem_key():
        """Route for redeeming subscription keys.

        Returns:
            render_template: Renders the redeem key template.
        """
        if request.method == "POST":
            key_value = request.form.get("key", "").strip()

            if not key_value:
                flash("Please enter a valid key", "error")
                return redirect(url_for("redeem_key"))

            redemption_key = RedemptionKey.query.filter_by(key=key_value).first()

            if not redemption_key:
                flash("Invalid key. Please check and try again.", "error")
                return redirect(url_for("redeem_key"))

            if redemption_key.is_redeemed:
                flash("This key has already been redeemed.", "error")
                return redirect(url_for("redeem_key"))

            if redemption_key.expires_at and datetime.utcnow() > redemption_key.expires_at:
                flash("This key has expired.", "error")
                return redirect(url_for("redeem_key"))

            success = redemption_key.redeem(current_user.id)

            if success:
                subscription = Subscription.query.get(redemption_key.subscription_id)
                flash(
                    f"Successfully upgraded to {subscription.name} subscription for {redemption_key.duration_days} days!",
                    "success",
                )
                
                tracking_data = {
                    'key_type': 'subscription',
                    'subscription_name': subscription.name,
                    'duration_days': redemption_key.duration_days
                }
                
                return render_template(
                    "redeem.html", 
                    now=datetime.utcnow(),
                    track_redemption=True,
                    tracking_data=tracking_data
                )
            else:
                flash("Failed to redeem key. Please try again later.", "error")

            return redirect(url_for("redeem_key"))

        return render_template("redeem.html", now=datetime.utcnow())

    @app.route("/admin/keys", methods=["GET", "POST"])
    @csrf.exempt
    @login_required
    def admin_keys():
        """Admin route for managing subscription keys.

        Returns:
            render_template: Renders the admin keys template.
        """
        if not current_user.subscription.name == "Admin":
            flash("Unauthorized access", "error")
            return redirect(url_for("index"))

        if request.method == "POST":
            subscription_id = request.form.get("subscription_id", type=int)
            quantity = request.form.get("quantity", type=int, default=1)
            duration_days = request.form.get("duration_days", type=int, default=30)

            if not subscription_id or not Subscription.query.get(subscription_id):
                flash("Invalid subscription selected", "error")
                return redirect(url_for("admin_keys"))

            if quantity < 1 or quantity > 100:
                flash("Quantity must be between 1 and 100", "error")
                return redirect(url_for("admin_keys"))

            if duration_days < 1:
                flash("Duration must be at least 1 day", "error")
                return redirect(url_for("admin_keys"))

            generated_keys = []
            for _ in range(quantity):
                key = RedemptionKey.create_key(
                    subscription_id=subscription_id,
                    duration_days=duration_days,
                    created_by_id=current_user.id,
                )
                generated_keys.append(key.key)

            if len(generated_keys) == 1:
                flash(f"Generated key: {generated_keys[0]}", "success")
            else:
                flash(f"Generated {len(generated_keys)} keys successfully", "success")

            return redirect(url_for("admin_keys"))

        subscriptions = Subscription.query.all()
        keys = RedemptionKey.query.order_by(RedemptionKey.created_at.desc()).limit(100).all()

        return render_template(
            "admin/keys.html", keys=keys, subscriptions=subscriptions, now=datetime.utcnow()
        )

    @app.route("/api/subscription/status")
    @csrf.exempt
    @login_required
    def subscription_status():
        """API endpoint to get the current user's subscription status.

        Returns:
            jsonify: A JSON response containing the subscription status.
        """
        user = User.query.get(current_user.id)
        subscription = user.subscription

        return jsonify(
            {
                "subscription": {
                    "name": subscription.name,
                    "end_date": user.subscription_end_date.isoformat()
                    if user.subscription_end_date
                    else None,
                    "is_active": True
                    if not user.subscription_end_date
                    or user.subscription_end_date > datetime.utcnow()
                    else False,
                    "days_remaining": (user.subscription_end_date - datetime.utcnow()).days
                    if user.subscription_end_date
                    and user.subscription_end_date > datetime.utcnow()
                    else 0,
                }
            }
        )


def process_chat_operation(app, operation_id):
    """Processes a chat operation.

    Args:
        app: Flask application instance.
        operation_id: The ID of the AIOperation to process.
    """
    with app.app_context():
        operation = AIOperation.query.get(operation_id)
        if not operation:
            print(f"Operation not found: {operation_id}")
            return

        try:
            user = User.query.get(operation.user_id)
            if not user:
                operation.fail("User not found")
                return

            operation.status = "processing"
            db.session.commit()

            operation.update_step("Analyzing stock symbols")
            symbols = operation.symbols if operation.symbols else []

            message_text = operation.message
            images = None

            if operation.image_data:
                operation.update_step("Processing attached images")
                images = []

                if hasattr(operation, "message_id") and operation.message_id:
                    chat_images = ChatImage.query.filter_by(message_id=operation.message_id).all()
                else:
                    user_message = ChatMessage.query.filter_by(
                        chat_id=operation.chat_id, user_id=operation.user_id, is_user=True
                    ).order_by(ChatMessage.created_at.desc()).first()

                    if user_message and user_message.has_image:
                        chat_images = ChatImage.query.filter_by(message_id=user_message.id).all()
                    else:
                        chat_images = []

                for chat_image in chat_images:
                    image_info = {
                        "name": chat_image.original_filename,
                        "mime_type": chat_image.mime_type,
                        "data": chat_image.compressed_data,
                    }
                    images.append(image_info)
                    operation.update_step(f"Retrieved image: {chat_image.original_filename}")

                if not images:
                    images = operation.image_data
                    operation.update_step("Using image metadata only (no binary data)")

            operation.update_step("Retrieving market data")
            context = ""

            if symbols and len(symbols) > 0:
                stock_data = {}
                for symbol in symbols:
                    try:
                        analysis = get_stock_analysis(symbol)
                        if analysis:
                            stock_data[symbol] = analysis
                    except Exception as e:
                        print(f"Error analyzing {symbol}: {e}")

                if stock_data:
                    context += "Stock Analysis:\n\n"
                    for symbol, data in stock_data.items():
                        formatted_data = format_stock_data(data)
                        context += formatted_data + "\n\n"

            chat_history = None
            if operation.chat_id:
                operation.update_step("Retrieving chat history")
                chat_messages = ChatMessage.query.filter_by(
                    chat_id=operation.chat_id
                ).order_by(ChatMessage.created_at).all()

                message_count = ChatMessage.query.filter_by(chat_id=operation.chat_id).count()
                if message_count <= 1:
                    chat = Chat.query.get(operation.chat_id)
                    if chat and (chat.title == "New Chat" or chat.title == "Untitled Chat"):
                        title = (
                            message_text[:50] + "..." if len(message_text) > 50 else message_text
                        )
                        chat.title = title
                        db.session.commit()
                        operation.update_step("Updated chat title")

                chat_messages = chat_messages[-10:] if len(chat_messages) > 10 else chat_messages

                if chat_messages:
                    chat_history = []
                    for msg in chat_messages:
                        chat_history.append({"role": "user" if msg.is_user else "assistant", "content": msg.content})
                    operation.update_step(
                        f"Retrieved {len(chat_history)} messages from chat history"
                    )

            operation.update_step("Generating AI response")
            
            preferred_language = LANGUAGES.get(user.preferred_language, user.preferred_language)
            
            ai_service = AIService(language=preferred_language)

            operation.update_step(f"Using {preferred_language} language for response")

            response = ai_service.get_response_with_tracking(
                operation_id=operation_id,
                message=message_text,
                images=images,
                symbols=symbols,
                chat_history=chat_history,
                context=context if context else None,
            )

            if not response:
                raise Exception("Failed to get response from AI service")

            ai_message = ChatMessage(
                chat_id=operation.chat_id, user_id=operation.user_id, content=response, is_user=False
            )
            db.session.add(ai_message)

            operation.status = "completed"
            operation.result = response
            operation.current_step = "Completed"

            user.daily_message_count += 1

            db.session.commit()

            invalidate_cache_pattern(f"db:*chat_messages:{operation.chat_id}:*")

            invalidate_cache_pattern(f"db:*user_chats:{operation.user_id}:*")

            socketio.emit(
                "chat_completed",
                {
                    "operation_id": operation_id,
                    "response": response,
                    "messages_left": user.subscription.message_limit - user.daily_message_count,
                },
                room=str(operation.user_id),
            )

        except Exception as e:
            print(f"Error processing operation {operation_id}: {str(e)}")
            traceback.print_exc()

            if operation:
                operation.status = "failed"
                operation.error = str(e)
                operation.current_step = "Failed"
                db.session.commit()

                socketio.emit(
                    "chat_error", {"operation_id": operation_id, "error": str(e)}, room=str(operation.user_id)
                )

def get_stock_analysis(symbol: str, interval: Interval = Interval.INTERVAL_1_DAY) -> dict:
    """Retrieves stock analysis data for a given symbol.

    Args:
        symbol (str): The stock symbol to analyze.
        interval (Interval): The interval for the analysis.

    Returns:
        dict: A dictionary containing the stock analysis data.
    """
    try:
        if symbol == "NONE" or not symbol:
            return None

        cache_key = f"stock_analysis:{symbol}:{interval}"
        cached_result = get_cached_query(cache_key)
        if cached_result:
            return cached_result

        if ":" in symbol:
            parts = symbol.split(":")
            if len(parts) == 2:
                exchange = parts[0]
                raw_symbol = parts[1]

                screener = None
                try:
                    conn = symbols_db_pool.get_connection()
                    try:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT screener FROM tv WHERE exchange = ? AND symbol = ? LIMIT 1",
                            (exchange, raw_symbol)
                        )
                        result = cursor.fetchone()
                        if result:
                            screener = result[0]
                    finally:
                        symbols_db_pool.return_connection(conn)
                except Exception as db_error:
                    print(f"Database error: {str(db_error)}")

                if not screener:
                    exchange_to_screener = {
                        "NASDAQ": "america",
                        "NYSE": "america",
                        "AMEX": "america",
                        "TSX": "canada",
                        "LSE": "uk",
                        "FWB": "germany",
                        "BINANCE": "crypto",
                        "COINBASE": "crypto",
                        "KRAKEN": "crypto",
                        "BITFINEX": "crypto",
                        "FTX": "crypto",
                        "KUCOIN": "crypto",
                        "FX": "forex",
                        "OANDA": "forex",
                        "CRYPTO": "crypto",
                    }

                    screener = exchange_to_screener.get(exchange, "america")

                try:
                    handler = TA_Handler(
                        symbol=raw_symbol,
                        screener=screener,
                        exchange=exchange,
                        interval=interval,
                    )
                    analysis = handler.get_analysis()
                except Exception as e:
                    print(f"Error analyzing {symbol}: {str(e)}")
                    return None
            else:
                return None
        else:
            try:
                conn = symbols_db_pool.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT screener, exchange, symbol, desc FROM tv WHERE UPPER(symbol) = ? LIMIT 1",
                        (symbol.upper(),)
                    )
                    result = cursor.fetchone()

                    if result:
                        screener, exchange, db_symbol, desc = result
                        try:
                            handler = TA_Handler(
                                symbol=db_symbol,
                                screener=screener,
                                exchange=exchange,
                                interval=interval,
                            )
                            analysis = handler.get_analysis()
                            name = desc
                        except Exception as e:
                            print(f"Error analyzing {symbol} from database: {str(e)}")
                            return None
                    else:
                        is_crypto = symbol in ['BTC', 'ETH', 'XRP', 'LTC', 'BCH', 'ADA', 'DOT', 'LINK', 'XLM', 'DOGE', 'UNI', 'SOL'] or \
                                    symbol.endswith('USDT') or symbol.endswith('USD') or symbol.endswith('BTC') or symbol.endswith('ETH')

                        if is_crypto:
                            original_symbol = symbol

                            if symbol == 'BTC':
                                try_symbols = ['BTCUSD', 'BTCUSDT']
                                exchanges = ['BINANCE', 'COINBASE']
                                success = False

                                for ex in exchanges:
                                    for sym in try_symbols:
                                        try:
                                            handler = TA_Handler(
                                                symbol=sym,
                                                screener="crypto",
                                                exchange=ex,
                                                interval=interval,
                                            )
                                            analysis = handler.get_analysis()
                                            symbol = sym
                                            exchange = ex
                                            screener = "crypto"
                                            success = True
                                            break
                                        except Exception as e:
                                            continue

                                    if success:
                                        break

                                if not success:
                                    print("Could not find BTC on any exchange")
                                    return None

                            elif symbol in ['ETH', 'XRP', 'LTC', 'BCH', 'ADA', 'DOT', 'LINK', 'XLM', 'DOGE', 'UNI', 'SOL', 'AVAX', 'MATIC', 'LUNA', 'SHIB', 'ATOM', 'ALGO', 'XTZ', 'FIL', 'VET', 'EOS', 'AAVE', 'MKR', 'COMP'] and \
                                    not (symbol.endswith('USDT') or symbol.endswith('USD') or symbol.endswith('BTC')):
                                symbol = f"{symbol}USDT"

                                try:
                                    handler = TA_Handler(
                                        symbol=symbol,
                                        screener="crypto",
                                        exchange="BINANCE",
                                        interval=interval,
                                    )
                                    analysis = handler.get_analysis()
                                    exchange = "BINANCE"
                                    screener = "crypto"
                                except Exception as binance_error:
                                    try:
                                        if symbol.endswith("USDT"):
                                            alt_symbol = symbol[:-4] + "USD"
                                            handler = TA_Handler(
                                                symbol=alt_symbol,
                                                screener="crypto",
                                                exchange="BINANCE",
                                                interval=interval,
                                            )
                                            analysis = handler.get_analysis()
                                            symbol = alt_symbol
                                            exchange = "BINANCE"
                                            screener = "crypto"
                                        else:
                                            handler = TA_Handler(
                                                symbol=symbol,
                                                screener="crypto",
                                                exchange="COINBASE",
                                                interval=interval,
                                            )
                                            analysis = handler.get_analysis()
                                            exchange = "COINBASE"
                                            screener = "crypto"
                                    except Exception as coinbase_error:
                                        print(f"Crypto {symbol} not found in BINANCE or COINBASE")
                                        return None
                            else:
                                try:
                                    handler = TA_Handler(
                                        symbol=symbol,
                                        screener="crypto",
                                        exchange="BINANCE",
                                        interval=interval,
                                    )
                                    analysis = handler.get_analysis()
                                    exchange = "BINANCE"
                                    screener = "crypto"
                                except Exception as binance_error:
                                    try:
                                        handler = TA_Handler(
                                            symbol=symbol,
                                            screener="crypto",
                                            exchange="COINBASE",
                                            interval=interval,
                                        )
                                        analysis = handler.get_analysis()
                                        exchange = "COINBASE"
                                        screener = "crypto"
                                    except Exception as coinbase_error:
                                        print(f"Crypto {symbol} not found in BINANCE or COINBASE")
                                        return None
                        else:
                            try:
                                handler = TA_Handler(
                                    symbol=symbol,
                                    screener="america",
                                    exchange="NASDAQ",
                                    interval=interval,
                                )
                                analysis = handler.get_analysis()
                                exchange = "NASDAQ"
                                screener = "america"
                            except Exception as nasdaq_error:
                                try:
                                    handler = TA_Handler(
                                        symbol=symbol,
                                        screener="america",
                                        exchange="NYSE",
                                        interval=interval,
                                    )
                                    analysis = handler.get_analysis()
                                    exchange = "NYSE"
                                    screener = "america"
                                except Exception as nyse_error:
                                    try:
                                        handler = TA_Handler(
                                            symbol=symbol,
                                            screener="america",
                                            exchange="AMEX",
                                            interval=interval,
                                        )
                                        analysis = handler.get_analysis()
                                        exchange = "AMEX"
                                        screener = "america"
                                    except Exception as amex_error:
                                        print(f"Stock {symbol} not found in US exchanges")
                                        return None
                finally:
                    symbols_db_pool.return_connection(conn)
            except Exception as db_error:
                print(f"Database error: {str(db_error)}")
                return None

        indicators = analysis.indicators

        if 'name' not in locals() or not name:
            try:
                conn = symbols_db_pool.get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT desc FROM tv WHERE exchange = ? AND symbol = ? LIMIT 1",
                        (exchange, symbol)
                    )
                    result = cursor.fetchone()
                    if result:
                        name = result[0]
                    else:
                        name = COMMON_STOCKS.get(symbol, f"{exchange}:{symbol}")
                finally:
                    symbols_db_pool.return_connection(conn)
            except Exception:
                name = COMMON_STOCKS.get(symbol, f"{exchange}:{symbol}")

        if exchange in ["BINANCE", "COINBASE", "KRAKEN", "CRYPTO"] or screener == "crypto":
            base_currency = symbol
            quote_currency = ""

            if "USDT" in symbol:
                base_currency = symbol.split('USDT')[0]
                quote_currency = "USDT"
            elif "USD" in symbol:
                base_currency = symbol.split('USD')[0]
                quote_currency = "USD"
            elif "BTC" in symbol and symbol != "BTC":
                parts = symbol.split('BTC')
                if len(parts) > 1 and not parts[1]:
                    base_currency = parts[0]
                    quote_currency = "BTC"

            if quote_currency:
                name = f"{base_currency} / {quote_currency}"
            else:
                if 'original_symbol' in locals() and original_symbol in CRYPTO_SYMBOLS:
                    name = CRYPTO_SYMBOLS.get(original_symbol)
                else:
                    name = CRYPTO_SYMBOLS.get(symbol, name)

        original_symbol = locals().get('original_symbol', symbol)

        response_data = {
            "symbol": original_symbol,
            "exchange": exchange,
            "screener": screener,
            "display_symbol": symbol,
            "name": name,
            "price": indicators.get("close", 0),
            "change": indicators.get("change", 0) / 100,
            "volume": int(indicators.get("volume", 0)),
            "marketCap": 0,
            "peRatio": None,
            "dayHigh": indicators.get("high", 0),
            "dayLow": indicators.get("low", 0),
            "technical_analysis": {
                "summary": analysis.summary,
                "oscillators": analysis.oscillators,
                "moving_averages": analysis.moving_averages,
            },
            "indicators": {
                "rsi": indicators.get("RSI", None),
                "macd": indicators.get("MACD.macd", None),
                "stoch_k": indicators.get("Stoch.K", None),
                "stoch_d": indicators.get("Stoch.D", None),
                "bb_upper": indicators.get("BB.upper", None),
                "bb_lower": indicators.get("BB.lower", None),
            },
            "is_crypto": exchange in ["BINANCE", "COINBASE", "KRAKEN", "CRYPTO"] or screener == "crypto"
        }

        cache_db_query(cache_key, response_data, 300)

        return response_data

    except Exception as e:
        print(f"Error analyzing {symbol}: {str(e)}")
        traceback.print_exc()
        return None

def get_total_users_count():
    """Gets the total count of users from the database and caches in Redis.

    Returns:
        int: Number of total users.
    """
    cache_key: str = "total_users_count"

    if redis_client:
        cached_value = redis_client.get(cache_key)
        if cached_value:
            return int(cached_value.decode("utf-8"))

    try:
        count = db.session.query(db.func.count(User.id)).scalar()

        if redis_client:
            redis_client.setex(cache_key, 86400, str(count))

        return count
    except Exception as e:
        logging.error(f"Error getting total users count: {str(e)}")
        return 0


def get_website_metrics():
    """Gets website metrics from cache or loads them from the metrics file.

    Returns:
        dict: Metrics data including user count and other statistics.
    """
    cache_key: str = "website_metrics"

    if redis_client:
        cached_value = redis_client.get(cache_key)
        if cached_value:
            return json.loads(cached_value)

    try:
        metrics_file: str = os.path.join(os.path.dirname(__file__), "static", "metrics.json")

        if os.path.exists(metrics_file):
            with open(metrics_file, "r") as f:
                metrics: dict = json.load(f)

            last_updated_str = metrics["last_updated"].replace("Z", "")
            last_updated = datetime.fromisoformat(last_updated_str)
            current_time = datetime.utcnow()
            
            if (current_time - last_updated).total_seconds() > 1200:
                metrics["last_updated"] = current_time.isoformat()

                with open(metrics_file, "w") as f:
                    json.dump(metrics, f, indent=2)
        else:
            metrics: dict = {
                "accuracy_rate": "99%",
                "hours_support": "24/7",
                "stocks_analyzed": "10K",
                "last_updated": datetime.utcnow().isoformat().replace("+00:00", "Z"),
            }

            with open(metrics_file, "w") as f:
                json.dump(metrics, f, indent=2)

        user_count: int = get_total_users_count()
        metrics["total_users"] = user_count

        if redis_client:
            redis_client.setex(cache_key, 1200, json.dumps(metrics))

        return metrics
    except Exception as e:
        logging.error(f"Error getting website metrics: {str(e)}")
        return {
            "accuracy_rate": "99%",
            "hours_support": "24",
            "stocks_analyzed": "10K",
            "daily_users": "1K",
            "last_updated": datetime.utcnow().isoformat(),
        }
