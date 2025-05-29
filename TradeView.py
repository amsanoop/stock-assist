import os
import re
import json
import shutil
import random
import time
import urllib.parse
from datetime import datetime
from typing import List

import requests
from bs4 import BeautifulSoup

class RelatedSymbol:
    """Represents a symbol related to a news item."""

    def __init__(self, symbol: str, currency_logoid: str, base_currency_logoid: str):
        """Initializes a RelatedSymbol object.

        Args:
            symbol (str): The symbol of the related item.
            currency_logoid (str): The logo ID of the currency.
            base_currency_logoid (str): The logo ID of the base currency.
        """
        self.symbol = symbol
        self.currency_logoid = currency_logoid
        self.base_currency_logoid = base_currency_logoid


class Item:
    """Represents a news item."""

    def __init__(self, id: str, title: str, provider: str, sourceLogoId: str, published: str, source: str, urgency: int, link: str, storyPath: str, relatedSymbols: List[RelatedSymbol]):
        """Initializes an Item object.

        Args:
            id (str): The ID of the news item.
            title (str): The title of the news item.
            provider (str): The provider of the news item.
            sourceLogoId (str): The logo ID of the source.
            published (str): The publication date of the news item.
            source (str): The source of the news item.
            urgency (int): The urgency of the news item.
            link (str): The link to the news item.
            storyPath (str): The story path of the news item.
            relatedSymbols (List[RelatedSymbol]): A list of related symbols.
        """
        self.id = id
        self.title = title
        self.provider = provider
        self.sourceLogoId = sourceLogoId
        self.published = published
        self.source = source
        self.urgency = urgency
        self.link = link
        self.storyPath = storyPath
        self.relatedSymbols = relatedSymbols

    def __str__(self) -> str:
        """Returns a string representation of the Item object.

        Returns:
            str: A string representation of the Item object.
        """
        return f"Title: {self.title}\nProvider: {self.provider}\nPublished: {self.published}\nSource: {self.source}\nUrgency: {self.urgency}\nLink: {self.link}\nStory Path: {self.storyPath}\nRelated Symbols: {self.relatedSymbols}"


REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Priority": "u=0, i",
    "Sec-Ch-Ua": '"Not A(Brand";v="8", "Chromium";v="132", "Google Chrome";v="132"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
}


class TradingView:
    """A class to retrieve news from TradingView."""

    def __init__(self):
        """Initializes the TradingView object."""
        self.url = 'https://news-headlines.tradingview.com/v2/view/headlines/symbol?client=web&lang=en&section=&streaming=true&symbol=CRYPTO%3ABTCUSD'
        self.session = requests.Session()
        self.session.headers = REQUEST_HEADERS.copy()

        self.session.cookies = requests.cookies.RequestsCookieJar()

        self.session.cookies.set("_ga", "GA1.2.123456789.1234567890")
        self.session.cookies.set("_gid", "GA1.2.987654321.1234567890")

    def get_news(self, today: bool = False, hours_ago: int = None, latest: bool = False) -> List[Item]:
        """Retrieves news from TradingView.

        Args:
            today (bool): If True, only retrieves news from today.
            hours_ago (int): Retrieves news from the last specified hours.
            latest (bool): If True, only retrieves the latest news.

        Returns:
            List[Item]: A list of news items.
        """
        try:
            response = self.session.get(self.url)
            response.raise_for_status()
            return self.parse_json_to_objects(response.text, today=today, hours_ago=hours_ago, latest=latest)
        except requests.RequestException as e:
            return []

    def parse_json_to_objects(self, json_response: str, today: bool = False, hours_ago: int = None, latest: bool = False) -> List[Item]:
        """Parses a JSON response into a list of Item objects.

        Args:
            json_response (str): The JSON response to parse.
            today (bool): If True, only include news from today.
            hours_ago (int): If specified, only include news from the last specified hours.
            latest (bool): If True, only return the latest news item.

        Returns:
            List[Item]: A list of Item objects.
        """
        try:
            data = json.loads(json_response)
            items = []
            now = datetime.now()
            cutoff_date = (now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() if today else now.timestamp() - 2 * 86400) if hours_ago is None else now.timestamp() - hours_ago * 3600
            for item_data in data.get("items", []):
                if item_data.get("published", 0) >= cutoff_date:
                    related_symbols = [
                        RelatedSymbol(
                            symbol=s.get("symbol", ""),
                            currency_logoid=s.get("currency-logoid", ""),
                            base_currency_logoid=s.get("base-currency-logoid", "")
                        ) for s in item_data.get("relatedSymbols", [])
                    ]
                    item = Item(
                        id=item_data.get("id", ""),
                        title=item_data.get("title", ""),
                        provider=item_data.get("provider", ""),
                        sourceLogoId=item_data.get("sourceLogoId", ""),
                        published=datetime.fromtimestamp(item_data.get("published", 0)).strftime('%Y-%m-%d %H:%M:%S') if item_data.get("published", 0) else "",
                        source=item_data.get("source", ""),
                        urgency=item_data.get("urgency", 0),
                        link=item_data.get("link", ""),
                        storyPath=f"https://www.tradingview.com/{item_data.get('storyPath', '')}",
                        relatedSymbols=related_symbols
                    )
                    items.append(item)
            return [max(items, key=lambda x: x.published)] if latest and items else items
        except json.JSONDecodeError as e:
            return []
        except Exception as e:
            return []

    def get_content(self, link: str) -> str:
        """Retrieves the content from a given link.

        Args:
            link (str): The link to retrieve content from.

        Returns:
            str: The content from the link.
        """
        try:
            time.sleep(random.uniform(2, 5))
            link = self.fix_link(link)
            parsed_url = urllib.parse.urlparse(link)
            domain = parsed_url.netloc

            headers = self.session.headers.copy()
            headers.update({
                "Host": domain,
                "Referer": link,
                "Origin": f"{parsed_url.scheme}://{domain}",
                "Cookie": "; ".join([f"{c.name}={c.value}" for c in self.session.cookies])
            })

            head_response = self.session.head(link, headers=headers, allow_redirects=True)
            head_response.raise_for_status()

            response = self.session.get(link, headers=headers, allow_redirects=True)
            response.raise_for_status()

            if "set-cookie" in response.headers:
                self.session.cookies.update(response.cookies)

            soup = BeautifulSoup(response.text, 'html.parser')

            content_selectors = [
                'div[class*="body-"]',
                'div[class*="content-"]',
                'article',
                '.article-content',
                '.post-content',
                '.entry-content'
            ]

            content = None
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    for unwanted in content_div.select('script, style, iframe, .advertisement'):
                        unwanted.decompose()

                    paragraphs = [p.get_text().strip() for p in content_div.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]
                    if paragraphs:
                        content = " ".join(filter(None, paragraphs))
                        break

            return content if content else None

        except requests.RequestException as e:
            return None
        except Exception as e:
            return None

    def fix_link(self, link: str) -> str:
        """Fixes broken links by removing duplicate slashes in the path.

        Args:
            link (str): The original link.

        Returns:
            str: The fixed link.
        """
        parts = urllib.parse.urlsplit(link)
        cleaned_path = re.sub('/+', '/', parts.path)
        fixed_link = urllib.parse.urlunsplit((parts.scheme, parts.netloc, cleaned_path, parts.query, parts.fragment))
        return fixed_link
