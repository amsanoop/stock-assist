from datetime import datetime, timedelta
import time
import threading
import re
import os
from urllib.parse import urlparse, urljoin, urlsplit
from dotenv import load_dotenv

from models import News, db
from TradeView import TradingView
from cache import redis_client

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "google")

if AI_PROVIDER == "google":
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))
elif AI_PROVIDER == "openrouter":
    from openai import OpenAI


class SimpleAI:
    """
    A simplified AI client for news summarization that supports both Google Gemini and OpenRouter.
    """
    
    def __init__(self):
        """Initialize the AI client based on the configured provider."""
        self.provider = AI_PROVIDER
        
        if self.provider == "google":
            self.model_name = os.getenv("GOOGLE_AI_MODEL", "gemini-2.0-flash-lite")
            self.model_config = {
                "temperature": float(os.getenv("GOOGLE_AI_TEMPERATURE", 0.7)),
                "top_p": float(os.getenv("GOOGLE_AI_TOP_P", 0.95)),
                "top_k": int(os.getenv("GOOGLE_AI_TOP_K", 40)),
                "max_output_tokens": int(os.getenv("GOOGLE_AI_MAX_OUTPUT_TOKENS", 4096)),
            }
            
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=self.model_config,
                safety_settings=[
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                ],
            )
            
        elif self.provider == "openrouter":
            self.model_name = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-opus:beta")
            self.model_config = {
                "temperature": float(os.getenv("OPENROUTER_TEMPERATURE", 0.7)),
                "top_p": float(os.getenv("OPENROUTER_TOP_P", 0.95)),
                "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", 4096)),
            }
            
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )
    
    def ask(self, question: str, system: str, **kwargs) -> str:
        """
        Ask the AI a question with a system prompt.
        
        Args:
            question (str): The question/content to analyze
            system (str): The system prompt
            **kwargs: Additional arguments (for compatibility)
            
        Returns:
            str: The AI's response
        """
        try:
            if self.provider == "google":
                return self._ask_google(question, system)
            elif self.provider == "openrouter":
                return self._ask_openrouter(question, system)
            else:
                return "AI provider not configured properly"
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def _ask_google(self, question: str, system: str) -> str:
        """Generate response using Google Gemini."""
        try:
            full_prompt = f"{system}\n\nArticle Content:\n{question}"
            
            response = self.model.generate_content(full_prompt)
            
            if response.candidates and len(response.candidates) > 0:
                return response.text
            else:
                return "No response generated"
                
        except Exception as e:
            return f"Error with Google AI: {str(e)}"
    
    def _ask_openrouter(self, question: str, system: str) -> str:
        """Generate response using OpenRouter."""
        try:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": question}
            ]
            
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.model_config["temperature"],
                top_p=self.model_config["top_p"],
                max_tokens=self.model_config["max_tokens"],
            )
            
            if completion.choices and len(completion.choices) > 0:
                return completion.choices[0].message.content or "No response generated"
            else:
                return "No response generated"
                
        except Exception as e:
            return f"Error with OpenRouter: {str(e)}"


class NewsService:
    """
    A service for handling news-related operations such as fetching, summarizing, and updating news articles.
    """

    def __init__(self):
        """
        Initializes the NewsService with AI and TradingView clients.
        """
        self.ai = SimpleAI()
        self.tradingview = TradingView()
        self.redis_prefix = "news_service:"

    def _normalize_url(self, url):
        """Normalize a URL by removing query parameters and fragments.
        
        Args:
            url (str): The URL to normalize
            
        Returns:
            str: Normalized URL
        """
        if not url:
            return url
            
        try:
            parsed = urlsplit(url)
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            return normalized
        except Exception as e:
            return url

    def _add_processed_link(self, link, expire_seconds=3600):
        """Add a source link to Redis to mark it as processed.
        
        Args:
            link (str): The article source link to mark as processed
            expire_seconds (int): Time in seconds before the key expires
        """
        if redis_client:
            normalized_link = self._normalize_url(link)
            key = f"{self.redis_prefix}processed:{normalized_link}"
            redis_client.set(key, "1", ex=expire_seconds)
            
    def _is_link_processed(self, link):
        """Check if a source link has already been processed recently.
        
        Args:
            link (str): The article source link to check
            
        Returns:
            bool: True if the link has been processed, False otherwise
        """
        if redis_client:
            normalized_link = self._normalize_url(link)
            key = f"{self.redis_prefix}processed:{normalized_link}"
            return bool(redis_client.get(key))
        return False

    def _acquire_lock(self, operation, timeout=30):
        """Acquire a Redis lock for an operation.
        
        Args:
            operation (str): The operation name to lock
            timeout (int): Lock timeout in seconds
            
        Returns:
            bool: True if lock was acquired, False otherwise
        """
        if not redis_client:
            return True
            
        lock_key = f"{self.redis_prefix}lock:{operation}"
        return bool(redis_client.set(lock_key, "1", ex=timeout, nx=True))
        
    def _release_lock(self, operation):
        """Release a Redis lock for an operation.
        
        Args:
            operation (str): The operation name to unlock
        """
        if redis_client:
            lock_key = f"{self.redis_prefix}lock:{operation}"
            redis_client.delete(lock_key)

    def _check_exists_in_db(self, link):
        """Check if a news article with this source link already exists in the database.
        
        Args:
            link (str): The article source link to check
            
        Returns:
            News: The existing news article if found, None otherwise
        """
        existing = News.query.filter_by(source_link=link).first()
        if existing:
            return existing
            
        normalized_link = self._normalize_url(link)
        all_articles = News.query.all()
        for article in all_articles:
            if self._normalize_url(article.source_link) == normalized_link:
                return article
                
        return None

    def generate_summary(self, content: str, is_paid: bool = False) -> str:
        """Generates a summary of the given content using OpenAI.

        Args:
            content (str): The content to summarize.
            is_paid (bool): Whether the summary is for a paid user, defaults to False.

        Returns:
            str: A summary of the content.
        """
        if not content:
            return "No content available for summarization."

        try:
            if is_paid:
                prompt = (
                    "You are a expert analyst at Stock Assistant. "
                    "Analyze this news article and provide detailed insights in markdown format: "
                    "\n\n## Key Takeaways\n"
                    "- Main points and market impact\n"
                    "- Potential trading opportunities\n"
                    "\n## Risk Analysis\n"
                    "- Key risk factors\n"
                    "- Market implications\n"
                    "\n## Technical Analysis\n"
                    "- Support/resistance levels if relevant\n"
                    "- Trading patterns mentioned\n"
                    "\nKeep the response professional, concise, and actionable. "
                    "Maximum 2000 characters."
                )
            else:
                prompt = (
                    "You are a expert analyst at Stock Assistant. "
                    "Provide a concise summary of this news article in markdown format:\n\n"
                    "## Summary\n"
                    "- Key points\n"
                    "- Market impact\n\n"
                    "Keep it brief and informative. "
                    "Maximum 500 characters."
                )

            return self.ai.ask(question=content, system=prompt)
        except Exception:
            return "Error generating summary. Please try again later."

    def cleanup_duplicates(self):
        """Remove duplicate news entries keeping the most recent version."""
        if not self._acquire_lock("cleanup_duplicates", timeout=300):
            return
            
        try:
            recent_news = News.query.filter(
                News.published_at >= datetime.utcnow() - timedelta(days=1)
            ).order_by(News.published_at.desc()).all()

            seen_titles = {}
            duplicates_to_remove = set()

            for news in recent_news:
                title_key = news.title.lower().strip()[:50]
                
                if title_key in seen_titles:
                    existing_id = seen_titles[title_key]
                    existing_news = News.query.get(existing_id)
                    
                    if (len(news.content or '') > len(existing_news.content or '') or 
                        news.published_at > existing_news.published_at):
                        duplicates_to_remove.add(existing_id)
                        seen_titles[title_key] = news.id
                    else:
                        duplicates_to_remove.add(news.id)
                else:
                    seen_titles[title_key] = news.id

            if duplicates_to_remove:
                batch_size = 20
                for i in range(0, len(duplicates_to_remove), batch_size):
                    batch = list(duplicates_to_remove)[i:i+batch_size]
                    News.query.filter(News.id.in_(batch)).delete(synchronize_session=False)
                    db.session.commit()
                    

        except Exception as e:
            db.session.rollback()
        finally:
            self._release_lock("cleanup_duplicates")

    def reindex_news(self):
        """Reindex all news by clearing old entries and fetching fresh news.
        This is meant to be run on application startup."""
        if not self._acquire_lock("reindex", timeout=600):
            return
            
        try:
            News.query.delete()
            db.session.commit()

            news_items = self.tradingview.get_news(hours_ago=24)
            if not news_items:
                return

            added_count = 0
            skipped_count = 0
            error_count = 0
            seen_urls = set()

            for item in news_items:
                try:
                    if not item.link:
                        continue
                        
                    normalized_url = self._normalize_url(item.link)

                    if normalized_url in seen_urls:
                        skipped_count += 1
                        continue
                        
                    seen_urls.add(normalized_url)
                        
                    if self._is_link_processed(normalized_url):
                        skipped_count += 1
                        continue
                        
                    self._add_processed_link(normalized_url)

                    content = self.tradingview.get_content(item.link)
                    if not content:
                        continue

                    free_summary = self.generate_summary(content, is_paid=False)
                    time.sleep(1)
                    paid_summary = self.generate_summary(content, is_paid=True)

                    existing = self._check_exists_in_db(item.link)
                    if existing:
                        skipped_count += 1
                        continue

                    news = News(
                        title=item.title,
                        content=content,
                        source=item.source,
                        source_link=item.link,
                        published_at=datetime.strptime(item.published, '%Y-%m-%d %H:%M:%S'),
                        symbols=[s.symbol for s in item.relatedSymbols],
                        summary=free_summary,
                        paid_summary=paid_summary,
                        is_paid_content=False,
                        urgency=item.urgency,
                        provider=item.provider
                    )

                    try:
                        db.session.add(news)
                        db.session.commit()
                        added_count += 1
                    except Exception as e:
                        db.session.rollback()
                        error_count += 1

                except Exception as e:
                    error_count += 1
                    db.session.rollback()
                    continue


        except Exception as e:
            db.session.rollback()
        finally:
            self._release_lock("reindex")

    def update_news(self):
        """Updates the news by fetching new articles from TradingView, summarizing them, and saving them to the database."""
        if not self._acquire_lock("update_news", timeout=600):
            return
            
        try:
            news_items = self.tradingview.get_news(hours_ago=24)
            if not news_items:
                return

            added_count = 0
            skipped_count = 0
            error_count = 0
            seen_urls = set()

            for item in news_items:
                try:
                    if not item.link:
                        continue
                        
                    normalized_url = self._normalize_url(item.link)

                    if normalized_url in seen_urls:
                        skipped_count += 1
                        continue
                        
                    seen_urls.add(normalized_url)

                    if self._is_link_processed(normalized_url):
                        skipped_count += 1
                        continue
                        
                    self._add_processed_link(normalized_url)

                    existing = self._check_exists_in_db(item.link)
                    if existing:
                        if existing.title != item.title:
                            existing.title = item.title
                            db.session.commit()
                        skipped_count += 1
                        continue

                    similar_title_news = News.query.filter(
                        News.published_at >= datetime.utcnow() - timedelta(days=1),
                        News.title.ilike(f"%{item.title[:50]}%")
                    ).first()
                    if similar_title_news:
                        skipped_count += 1
                        continue

                    content = self.tradingview.get_content(item.link)
                    if not content:
                        continue

                    free_summary = self.generate_summary(content, is_paid=False)
                    time.sleep(1)
                    paid_summary = self.generate_summary(content, is_paid=True)

                    if self._check_exists_in_db(item.link):
                        skipped_count += 1
                        continue

                    news = News(
                        title=item.title,
                        content=content,
                        source=item.source,
                        source_link=item.link,
                        published_at=datetime.strptime(item.published, '%Y-%m-%d %H:%M:%S'),
                        symbols=[s.symbol for s in item.relatedSymbols],
                        summary=free_summary,
                        paid_summary=paid_summary,
                        is_paid_content=False,
                        urgency=item.urgency,
                        provider=item.provider
                    )

                    try:
                        db.session.add(news)
                        db.session.commit()
                        added_count += 1
                    except Exception as e:
                        if "Duplicate entry" in str(e):
                            skipped_count += 1
                        else:
                            error_count += 1
                        db.session.rollback()

                except Exception as e:
                    error_count += 1
                    db.session.rollback()
                    continue

            
            if added_count > 0:
                self.cleanup_duplicates()

        except Exception as e:
            db.session.rollback()
        finally:
            self._release_lock("update_news")

    def get_news_by_id(self, news_id: int) -> News:
        """Get a single news article by its ID.

        Args:
            news_id (int): The ID of the news article.

        Returns:
            News: The news article with the given ID.
        """
        return News.query.get(news_id)

    def get_latest_news(self, is_paid: bool = False, limit: int = 20):
        """Retrieves the latest news articles, optionally filtering for paid content and limiting the number of results.

        Args:
            is_paid (bool): Whether to retrieve only paid content, defaults to False.
            limit (int): The maximum number of news articles to retrieve, defaults to 20.

        Returns:
            list[News]: A list of the latest news articles.
        """
        try:
            news_items = News.query.order_by(News.published_at.desc()).limit(limit).all()
            if is_paid:
                for news in news_items:
                    news.summary = news.paid_summary or news.summary
            return news_items
        except Exception:
            return []

    def start(self):
        """Start the news service background thread that periodically updates the news."""
        def update_thread():
            """Background thread to update news periodically."""
            time.sleep(30)
            
            while True:
                try:
                    self.update_news()
                except Exception as e:
                    pass
                
                time.sleep(3600)
        
        thread = threading.Thread(target=update_thread, daemon=True)
        thread.start()