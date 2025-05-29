import os
import dotenv

from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect

from utils.ip import get_ip
from utils.utils import SQLiteConnectionPool

dotenv.load_dotenv()

limiter             : Limiter               | None = None
csrf                : CSRFProtect           | None = None
symbols_db_pool     : SQLiteConnectionPool  | None = None

COMPRESS_ENABLED    : bool = True
COMPRESS_LEVEL      : int  = 6
COMPRESS_MIN_SIZE   : int  = 500

def init_protections(app) -> Limiter:
    """Initializes CSRF protection and rate limiter for the Flask app.

    Args:
        app: Flask application instance.

    Returns:
        Limiter: The configured Limiter instance.
    """
    global limiter, csrf
    csrf = CSRFProtect(app)
    csrf.init_app(app)
    limiter = Limiter(
        app=app,
        key_func=get_ip,
        default_limits=["300 per hour"],
        storage_uri=f"redis://{app.config['REDIS_HOST']}:{app.config['REDIS_PORT']}/{app.config['REDIS_DB']}",
    )
    return limiter


symbols_db_pool = SQLiteConnectionPool("symbols_db/tradingview.db", max_connections=20)

ALPHA_VANTAGE_API_KEY: str | None = os.getenv("ALPHA_VANTAGE_API_KEY")
BASE_URL: str = "https://www.alphavantage.co/query"

COMMON_STOCKS: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "META": "Meta Platforms Inc.",
    "NVDA": "NVIDIA Corporation",
    "TSLA": "Tesla Inc.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "WMT": "Walmart Inc.",
    "KO": "The Coca-Cola Company",
    "DIS": "The Walt Disney Company",
    "NFLX": "Netflix Inc.",
    "INTC": "Intel Corporation",
    "AMD": "Advanced Micro Devices Inc.",
    "IBM": "International Business Machines",
    "CSCO": "Cisco Systems Inc.",
    "ORCL": "Oracle Corporation",
    "CRM": "Salesforce Inc.",
}

CRYPTO_SYMBOLS: dict[str, str] = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "XRP": "Ripple",
    "LTC": "Litecoin",
    "BCH": "Bitcoin Cash",
    "ADA": "Cardano",
    "DOT": "Polkadot",
    "LINK": "Chainlink",
    "XLM": "Stellar",
    "DOGE": "Dogecoin",
    "UNI": "Uniswap",
    "SOL": "Solana",
    "AVAX": "Avalanche",
    "MATIC": "Polygon",
    "LUNA": "Terra Luna",
    "SHIB": "Shiba Inu",
    "ATOM": "Cosmos",
    "ALGO": "Algorand",
    "XTZ": "Tezos",
    "FIL": "Filecoin",
    "VET": "VeChain",
    "EOS": "EOS",
    "AAVE": "Aave",
    "MKR": "Maker",
    "COMP": "Compound",
}