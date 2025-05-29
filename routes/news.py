from flask import Blueprint, jsonify, render_template

from config import limiter
from models import News

news_bp = Blueprint("news", __name__)


@news_bp.route("/news")
@limiter.limit("30 per minute")
def news_page():
    """Renders the news page with a list of news items.

    Returns:
        str: The rendered HTML template for the news page.
    """
    news_items = News.query.order_by(News.published_at.desc()).limit(50).all()
    return render_template("news.html", news_items=news_items)


@news_bp.route("/api/news")
@limiter.limit("60 per minute")
def get_news():
    """Retrieves a list of news items in JSON format.

    Returns:
        jsonify: A JSON response containing a list of news items.
    """
    news_items = News.query.order_by(News.published_at.desc()).limit(50).all()
    return jsonify(
        [
            {
                "id": news.id,
                "title": news.title,
                "summary": news.summary,
                "content": news.content,
                "source": news.source,
                "source_link": news.source_link,
                "published_at": news.published_at.isoformat(),
                "symbols": news.symbols,
                "urgency": news.urgency,
                "provider": news.provider,
            }
            for news in news_items
        ]
    )


@news_bp.route("/api/news/<int:news_id>")
@limiter.limit("60 per minute")
def get_news_item(news_id: int):
    """Retrieves a specific news item by its ID.

    Args:
        news_id (int): The ID of the news item to retrieve.

    Returns:
        jsonify: A JSON response containing the details of the news item.
    """
    news = News.query.get_or_404(news_id)
    return jsonify(
        {
            "id": news.id,
            "title": news.title,
            "summary": news.summary,
            "content": news.content,
            "source": news.source,
            "source_link": news.source_link,
            "published_at": news.published_at.isoformat(),
            "symbols": news.symbols,
            "urgency": news.urgency,
            "provider": news.provider,
        }
    )