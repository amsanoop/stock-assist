from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from googlesearch import SearchResult

import sys, os, json
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from .ai_service import AIService
from .tools import google_search
from datetime import datetime
from cache import redis_client


@dataclass
class Stock:
    """Data class representing a stock with its essential information."""
    name: str
    company_name: str
    symbol: str
    type: str = "stock"  # can be "stock" or "crypto"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.company_name}) - {self.symbol}"
    
    def __dict__(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "company_name": self.company_name,
            "symbol": self.symbol,
            "type": self.type
        }
    
    def __repr__(self) -> str:
        return f"{self.name} ({self.company_name}) - {self.symbol}"
    

class StockRecommender:
    """A class that recommends stocks and crypto based on current market trends using AI and web search."""
    
    STOCKS_REDIS_KEY = "stock_recommendations"
    CRYPTO_REDIS_KEY = "crypto_recommendations"
    
    def __init__(self, ai_model: Optional[str] = None, language: str = 'en'):
        """
        Initialize the StockRecommender with AI service.
        
        Args:
            ai_model: Optional model name to use for AI service
            language: Language code for responses
        """
        self.service = AIService(model=ai_model, language=language)
        self.chat = self.service.model.start_chat()
        self.stocks_prompt = """You are a financial expert. I need you to provide 5 stock recommendations in a VERY SPECIFIC format.
Follow these rules exactly:
1. Based on the search results, identify 5 promising stocks (not cryptocurrencies)
2. For each stock, provide: stock name, company full name, and stock symbol
3. Format MUST be: <stock_name|company_name|stock_symbol>
4. Separate each stock with a comma
5. Include ALL 3 components for EACH stock
6. Do not include ANY text before or after the formatted list
7. If you don't know an exact value, make your best estimate but NEVER leave it blank
8. FINAL RESPONSE FORMAT EXAMPLE (follow this EXACTLY):
<Apple|Apple Inc.|AAPL>,<Microsoft|Microsoft Corporation|MSFT>,<Amazon|Amazon.com Inc.|AMZN>,<Google|Alphabet Inc.|GOOGL>,<Tesla|Tesla Inc.|TSLA>"""

        self.crypto_prompt = """You are a cryptocurrency expert. I need you to provide 5 cryptocurrency recommendations in a VERY SPECIFIC format.
Follow these rules exactly:
1. Based on the search results, identify 5 promising cryptocurrencies
2. For each crypto, provide: crypto name, project name, and symbol
3. Format MUST be: <crypto_name|project_name|symbol>
4. Separate each crypto with a comma
5. Include ALL 3 components for EACH cryptocurrency
6. Do not include ANY text before or after the formatted list
7. If you don't know an exact value, make your best estimate but NEVER leave it blank
8. FINAL RESPONSE FORMAT EXAMPLE (follow this EXACTLY):
<Bitcoin|Bitcoin|BTC>,<Ethereum|Ethereum|ETH>,<Cardano|Cardano|ADA>,<Solana|Solana|SOL>,<Polkadot|Polkadot|DOT>"""

    def _format_search_results(self, results: List[SearchResult]) -> str:
        """
        Format search results into a prompt-friendly string.
        
        Args:
            results: List of search results
            
        Returns:
            Formatted string with search result details
        """
        search_prompt = "[Websearch Results]:\n"
        
        for result in results:
            search_prompt += f"  Title: {result.title}\n"
            search_prompt += f"  Description: {result.description}\n\n"
            
        return search_prompt

    def _parse_response(self, response: str, asset_type: str = "stock") -> List[Stock]:
        """
        Parse AI response into structured stock data.
        
        Args:
            response: Raw response string from AI
            asset_type: Type of asset ("stock" or "crypto")
            
        Returns:
            List of Stock objects
        """
        result: List[Stock] = []
    
        cleaned_response = response.strip()
        
        start_idx = cleaned_response.find('<')
        end_idx = cleaned_response.rfind('>')
        
        if start_idx != -1 and end_idx != -1:
            cleaned_response = cleaned_response[start_idx:end_idx+1]
        
        stocks = []
        current = ""
        inside_brackets = False
        
        for char in cleaned_response:
            if char == '<':
                inside_brackets = True
                current += char
            elif char == '>':
                inside_brackets = False
                current += char
            elif char == ',' and not inside_brackets:
                stocks.append(current.strip())
                current = ""
            else:
                current += char
                
        if current:
            stocks.append(current.strip())
        
        for stock in stocks:
            match = stock.strip()
            if match.startswith('<') and match.endswith('>'):
                content = match[1:-1]
                parts = content.split('|')
                
                if len(parts) >= 3:
                    stock_name, company_name, symbol = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    
                    if not stock_name:
                        stock_name = symbol
                    if not company_name:
                        company_name = stock_name
                    if not symbol:
                        continue
                        
                    result.append(Stock(
                        name=stock_name,
                        company_name=company_name,
                        symbol=symbol,
                        type=asset_type
                    ))
                elif len(parts) == 2:
                    stock_name, company_name = parts[0].strip(), parts[1].strip()
                    result.append(Stock(
                        name=stock_name,
                        company_name=company_name,
                        symbol=stock_name[:4].upper(),
                        type=asset_type
                    ))
        
        if not result and asset_type == "stock":
            fallback_stocks = [
                Stock("Apple", "Apple Inc.", "AAPL", "stock"),
                Stock("Microsoft", "Microsoft Corporation", "MSFT", "stock"),
                Stock("Amazon", "Amazon.com Inc.", "AMZN", "stock"),
                Stock("Google", "Alphabet Inc.", "GOOGL", "stock"),
                Stock("Tesla", "Tesla Inc.", "TSLA", "stock")
            ]
            return fallback_stocks[:5]
        elif not result and asset_type == "crypto":
            fallback_crypto = [
                Stock("Bitcoin", "Bitcoin", "BTC", "crypto"),
                Stock("Ethereum", "Ethereum", "ETH", "crypto"),
                Stock("Cardano", "Cardano", "ADA", "crypto"),
                Stock("Solana", "Solana", "SOL", "crypto"),
                Stock("Polkadot", "Polkadot", "DOT", "crypto")
            ]
            return fallback_crypto[:5]
            
        return result
    
    def get_recommended_stocks(self) -> List[Stock]:
        """
        Get recommended stocks based on current market data.
        First checks Redis cache, if not found generates new recommendations.
        
        Returns:
            List of Stock objects representing recommended investments
        """
        if redis_client:
            cached_stocks = redis_client.get(self.STOCKS_REDIS_KEY)
            if cached_stocks:
                stocks_data = json.loads(cached_stocks)
                return [Stock(**stock) for stock in stocks_data]
        
        query = f"Top 5 stocks to invest in {datetime.now().strftime('%B %d, %Y')}"
        results = google_search(query=query)
        search_prompt = self._format_search_results(results)
        
        response = self.chat.send_message(content=self.stocks_prompt + search_prompt)
        stocks = self._parse_response(response.text, "stock")
        
        if redis_client and stocks:
            stocks_data = [stock.__dict__() for stock in stocks]
            redis_client.setex(self.STOCKS_REDIS_KEY, 86400, json.dumps(stocks_data))
        
        return stocks

    def get_recommended_crypto(self) -> List[Stock]:
        """
        Get recommended cryptocurrencies based on current market data.
        First checks Redis cache, if not found generates new recommendations.
        
        Returns:
            List of Stock objects representing recommended crypto investments
        """
        if redis_client:
            cached_crypto = redis_client.get(self.CRYPTO_REDIS_KEY)
            if cached_crypto:
                crypto_data = json.loads(cached_crypto)
                return [Stock(**crypto) for crypto in crypto_data]
        
        query = f"Top 5 cryptocurrencies to invest in {datetime.now().strftime('%B %d, %Y')}"
        results = google_search(query=query)
        search_prompt = self._format_search_results(results)
        
        response = self.chat.send_message(content=self.crypto_prompt + search_prompt)
        cryptos = self._parse_response(response.text, "crypto")
        
        if redis_client and cryptos:
            crypto_data = [crypto.__dict__() for crypto in cryptos]
            redis_client.setex(self.CRYPTO_REDIS_KEY, 86400, json.dumps(crypto_data))
        
        return cryptos
    
    def get_all_recommendations(self) -> Tuple[List[Stock], List[Stock]]:
        """
        Get both stock and crypto recommendations.
        Prioritizes cached recommendations and only generates new ones when needed.
        
        Returns:
            Tuple of (stock_recommendations, crypto_recommendations)
        """
        stocks = self.get_cached_recommendations(asset_type="stock") 
        cryptos = self.get_cached_recommendations(asset_type="crypto")
        
        if not stocks:
            stocks = self.get_recommended_stocks()

        if not cryptos:
            cryptos = self.get_recommended_crypto()
            
        return stocks, cryptos
    
    @classmethod
    def get_cached_recommendations(cls, asset_type: str = "stock") -> Optional[List[Stock]]:
        """
        Get only cached recommendations without generating new ones.
        
        Args:
            asset_type: Type of asset to get recommendations for ("stock" or "crypto")
        
        Returns:
            List of Stock objects if cache exists, None otherwise
        """
        if not redis_client:
            return None
            
        redis_key = cls.STOCKS_REDIS_KEY if asset_type == "stock" else cls.CRYPTO_REDIS_KEY
        cached_data = redis_client.get(redis_key)
        
        if cached_data:
            data = json.loads(cached_data)
            return [Stock(**item) for item in data]
        return None