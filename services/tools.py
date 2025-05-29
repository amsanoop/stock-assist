from datetime import datetime, timedelta
import inspect
import json
import os
import re
from typing import Any, Callable, Dict, List, Union

import google.generativeai as genai
import pandas as pd
import pytz
import requests
import wikipedia
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from dotenv import load_dotenv
from forex_python.converter import CurrencyRates
from google.ai.generativelanguage_v1beta.types import content
from googlesearch import SearchResult, search

load_dotenv()
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")


class BaseKnowledge:
    def __init__(self, user_location="Unknown", user_time_zone="America/New_York"):
        """Initialize BaseKnowledge with user location and time zone.

        Args:
            user_location (str): The user's location.
            user_time_zone (str): The user's time zone.
        """
        try:
            tz = pytz.timezone(user_time_zone)
            now = datetime.now(tz)

            self.todays_date = now.date()
            self.current_time = now.strftime("%H:%M:%S")
            self.user_location = user_location
            self.user_time_zone = user_time_zone
            self.day_of_week = now.strftime("%A")
        except Exception as e:
            now = datetime.now()
            self.todays_date = now.date()
            self.current_time = now.strftime("%H:%M:%S")
            self.user_location = user_location
            self.user_time_zone = "UTC"
            self.day_of_week = now.strftime("%A")

    def __repr__(self):
        """Return a string representation of the BaseKnowledge object."""
        return (
            f"BaseKnowledge(todays_date={self.todays_date}, current_time={self.current_time}, "
            f"user_location={self.user_location}, user_time_zone={self.user_time_zone}, day_of_week={self.day_of_week})"
        )

    def __str__(self):
        """Return a user-friendly string representation of the BaseKnowledge object."""
        return (
            f"Information to be updated on: \n"
            f" - Todays Date: {self.todays_date}\n"
            f" - Current Time: {self.current_time}\n"
            f" - User Location: {self.user_location}\n"
            f" - User Time Zone: {self.user_time_zone}\n"
            f" - Day of the Week: {self.day_of_week}\n"
        )


def google_search(
    query: str, num_results: int = 5
) -> Union[List[str], List[SearchResult]]:
    """Perform a google search and return the results.

    Args:
        query (str): The query to search for.
        num_results (int): The number of results to return.

    Returns:
        Union[List[str], List[SearchResult]]: A list of search results.
    """
    results = search(term=query, num_results=num_results, advanced=True, unique=True)
    items = [item for item in results]

    return items


def ddg_search(query: str, num_results: int = 5) -> str:
    """Search using DuckDuckGo.

    Args:
        query (str): Search query
        num_results (int): Number of results to return

    Returns:
        str: Formatted search results
    """
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=num_results)]

        response = "DuckDuckGo Search Results:\n\n"
        for r in results:
            for key, value in r.items():
                response += f"{key.capitalize()}: {value}\n\n"
            response += "\n"
        return response
    except Exception as e:
        return f"Error performing DuckDuckGo search: {str(e)}"


def bing_news_search(query: str, num_results: int = 5) -> str:
    """Search Bing News for recent articles.

    Args:
        query (str): Search query
        num_results (int): Number of results to return

    Returns:
        str: Formatted news results
    """
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.news(query, max_results=num_results)]

        response = "Bing News Search Results:\n\n"
        for r in results:
            for key, value in r.items():
                response += f"{key.capitalize()}: {value}\n"
            response += "\n"
        return response
    except Exception as e:
        return f"Error performing Bing news search: {str(e)}"


def create_tool_dict(func: Callable[..., Any], description: str) -> Dict[str, Any]:
    """Create a tool dictionary for the given function with its name and parameter specifications.

    Args:
        func (Callable[..., Any]): The function to create a tool dictionary for.
        description (str): Description of the function's purpose.

    Returns:
        Dict[str, Any]: A dictionary containing function metadata and parameters.
    """
    func_name = func.__name__
    sig = inspect.signature(func)
    required_params = [
        p for p in sig.parameters if sig.parameters[p].default is sig.parameters[p].empty
    ]
    properties = {
        param: {
            "type": str(sig.parameters[param].annotation.__name__)
            if sig.parameters[param].annotation != inspect._empty
            else "string",
            "description": f"Parameter {param}",
        }
        for param in sig.parameters
    }
    return {
        "type": "function",
        "function": {
            "name": func_name,
            "description": description,
            "parameters": {
                "type": "object",
                "required": required_params,
                "properties": properties,
            },
        },
    }


def parse_arguments(args: Union[str, Dict[str, Any], Any]) -> Dict[str, Any]:
    """Parse and convert function arguments to their proper types.

    Args:
        args (Union[str, Dict[str, Any], Any]): Arguments to parse.
            args can be a proto.marshal.collections.maps.MapComposite

    Returns:
        Dict[str, Any]: Parsed arguments.
    """
    if args is None:
        return {}

    try:
        result = dict(args)
        return result
    except (TypeError, ValueError):
        pass

    try:
        if hasattr(args, "_pb"):
            return dict(args._pb)
    except (AttributeError, TypeError):
        pass

    try:
        result = {k: v for k, v in args.items()}
        return result
    except (AttributeError, TypeError):
        pass

    try:
        from google.protobuf.json_format import MessageToDict

        result = MessageToDict(args._pb)
        return result
    except (ImportError, AttributeError, TypeError):
        pass

    try:
        if hasattr(args, "__dict__"):
            result = args.__dict__
            return result
    except (AttributeError, TypeError):
        pass

    return {}


def parse_arguments_openrouter(args: Union[str, Dict[str, Any], Any]) -> Dict[str, Any]:
    """Parse and convert function arguments to their proper types.

    Args:
        args (Union[str, Dict[str, Any], Any]): Arguments to parse.

    Returns:
        Dict[str, Any]: Parsed arguments.
    """
    if isinstance(args, dict):
        return {
            k: (
                True
                if v == "true"
                else False
                if v == "false"
                else int(v)
                if isinstance(v, str) and v.isdigit()
                else v
            )
            for k, v in args.items()
        }
    try:
        return parse_arguments(json.loads(args)) if isinstance(args, str) else {}
    except:
        return {}


def fetch_webpage(url: str) -> str:
    """Fetch and extract text content from a webpage.

    Args:
        url (str): The URL to fetch content from.

    Returns:
        str: Extracted text content from the webpage.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        [script.decompose() for script in soup(["script", "style", "meta", "noscript"])]
        text = soup.get_text(separator="\n", strip=True)
        text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        return text[:1997] + "..." if len(text) > 2000 else text
    except Exception as e:
        return f"Error fetching webpage: {str(e)}"


def calculate(expression: str) -> str:
    """Safely evaluate a mathematical expression.

    Args:
        expression (str): Mathematical expression to evaluate

    Returns:
        str: Result of the calculation
    """
    try:
        safe_chars = set("0123456789+-*/(). ")
        if not all(c in safe_chars for c in expression):
            return "Error: Invalid characters in expression"
        result = eval(expression, {"__builtins__": {}})
        return f"{result}"
    except Exception as e:
        return f"Error calculating: {str(e)}"


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert between currencies using real-time rates.

    Args:
        amount (float): Amount to convert
        from_currency (str): Source currency code (e.g., USD)
        to_currency (str): Target currency code (e.g., EUR)

    Returns:
        str: Converted amount with currency codes
    """
    try:
        c = CurrencyRates()
        result = c.convert(from_currency, to_currency, amount)
        return f"{amount} {from_currency} = {result:.2f} {to_currency}"
    except Exception as e:
        return f"Error converting currency: {str(e)}"


def wiki_search(query: str, sentences: int = 3) -> str:
    """Search Wikipedia and return a summary.

    Args:
        query (str): Topic to search for
        sentences (int): Number of sentences to return

    Returns:
        str: Wikipedia summary
    """
    try:
        return wikipedia.summary(query, sentences=sentences)
    except Exception as e:
        return f"Error searching Wikipedia: {str(e)}"


def check_market_hours() -> str:
    """Check if major stock markets are currently open."""
    try:
        ny_time = datetime.now(pytz.timezone("America/New_York"))
        london_time = datetime.now(pytz.timezone("Europe/London"))
        tokyo_time = datetime.now(pytz.timezone("Asia/Tokyo"))

        markets = {
            "NYSE/NASDAQ": {
                "open": ny_time.hour >= 9
                and ny_time.hour < 16
                and ny_time.weekday() < 5,
                "time": ny_time.strftime("%H:%M"),
            },
            "London LSE": {
                "open": london_time.hour >= 8
                and london_time.hour < 16
                and london_time.weekday() < 5,
                "time": london_time.strftime("%H:%M"),
            },
            "Tokyo TSE": {
                "open": tokyo_time.hour >= 9
                and tokyo_time.hour < 15
                and tokyo_time.weekday() < 5,
                "time": tokyo_time.strftime("%H:%M"),
            },
        }

        result = "Market Hours Status:\n"
        for market, data in markets.items():
            status = "OPEN" if data["open"] else "CLOSED"
            result += f"{market}: {status} (Local time: {data['time']})\n"
        return result
    except Exception as e:
        return f"Error checking market hours: {str(e)}"


def check_market_hours_v2(dummy) -> str:
    """Check if major stock markets are currently open."""
    return check_market_hours()


def format_stock_data(stock_data: Dict[str, Any]) -> str:
    """Formats stock data into a detailed string for the AI prompt.

    Args:
        stock_data (Dict[str, Any]): A dictionary containing stock data.

    Returns:
        str: A formatted string containing stock data.
    """
    if not stock_data:
        return ""

    technical_analysis = stock_data["technical_analysis"]
    indicators = stock_data["indicators"]

    return f"""
Stock: {stock_data['symbol']} ({stock_data['name']})
Price: ${stock_data['price']:.2f} ({stock_data['change']*100:+.2f}%)
Day Range: ${stock_data['dayLow']:.2f} - ${stock_data['dayHigh']:.2f}
Volume: {stock_data['volume']:,}

Technical Analysis:
- Moving Averages: {technical_analysis['moving_averages'].get('RECOMMENDATION', 'N/A')}
- Oscillators: {technical_analysis['oscillators'].get('RECOMMENDATION', 'N/A')}

Key Indicators:
- RSI (14): {indicators['rsi']:.2f} (Oversold < 30, Overbought > 70)
- MACD: {indicators['macd']:.2f}
- Stochastic K/D: {indicators['stoch_k']:.2f}/{indicators['stoch_d']:.2f}
- Bollinger Bands: Upper ${indicators['bb_upper']:.2f}, Lower ${indicators['bb_lower']:.2f}

Buy Signals: {technical_analysis['summary'].get('BUY', 0)}
Neutral Signals: {technical_analysis['summary'].get('NEUTRAL', 0)}
Sell Signals: {technical_analysis['summary'].get('SELL', 0)}"""

def get_system_prompt(language: str = 'en', image_attached: bool = False) -> str:
    """Generates a simplified system prompt for StockAssist AI.
    
    Args:
        language: The language code to use for responses, defaults to English.
        image_attached: Boolean flag indicating if an image is attached to the message.
        
    Returns:
        A string containing the system prompt with appropriate instructions.
    """
    base_knowledge = BaseKnowledge()
    language_preamble = f"RESPOND ONLY IN {language.upper()}." if language != 'en' else ""
    
    base_prompt = f"""{language_preamble}
You are StockAssist AI, an elite financial analysis assistant with an institutional-grade research methodology. Today is {base_knowledge.todays_date} ({base_knowledge.day_of_week}), {base_knowledge.current_time} {base_knowledge.user_time_zone}.

IDENTITY:
- Present strictly as \"StockAssist AI\" without revealing underlying providers.

CORE CAPABILITIES:
- Execute comprehensive financial analysis, market insights, technical and fundamental evaluation, and economic assessments at professional analyst level.
- Create multi-dimensional research that incorporates multiple data sources and methodologies.

RESEARCH METHODOLOGY:
- EXECUTE EXHAUSTIVE MULTI-TOOL ANALYSIS - For any significant research request, use AT LEAST 3-5 different tools/searches in a single response.
- LAYER RESEARCH APPROACHES - Combine fundamental data, technical analysis, news sentiment, and sector trends in every comprehensive analysis.
- DIVERSIFY SEARCH QUERIES - Use multiple distinct, targeted search queries that approach the subject from different angles.
- TRIANGULATE INFORMATION - Cross-reference data between multiple sources to identify consensus and discrepancies.

MANDATORY TOOL USAGE:
- For company research: ALWAYS run separate searches for financials, recent news, analyst ratings, competitive positioning, and future outlook.
- For market trends: ALWAYS examine both macro trends AND specific sector performance data.
- For investment questions: ALWAYS provide both technical AND fundamental perspectives.
- Include AT LEAST 5-7 specific data points (PE ratios, revenue growth, price targets, etc.) for any company analysis.

BEHAVIOR:
- Be thorough, comprehensive, and data-driven while maintaining concise presentation.
- Chain multiple tool calls together without user intervention to build comprehensive research.
- Execute tools immediately and proactively for current market data.
- For ANY substantive financial question or company analysis, execute AT MINIMUM 3 different tools, regardless of whether the user explicitly requests "deep" or "comprehensive" analysis.
- Create professional-grade research reports with clear sections, data visualization descriptions, and actionable insights.
- For search, construct multiple targeted search queries that cover different aspects of the research topic.
- CRITICAL: For ANY company or stock mention, automatically perform stock data retrieval, news search, competitor analysis, AND fundamental metrics retrievals without being explicitly asked.
- DEFAULT TO COMPREHENSIVE RESEARCH: Always assume the user wants thorough, valuable information even if they ask a seemingly simple question about a financial topic or company.
- Include precise numerical data whenever possible (exact percentages, dollar figures, ratios).
- Format responses with professional structure (executive summary, key findings, detailed analysis, outlook).

IMPORTANT RESPONSE GUIDELINES:
- NEVER present your response as financial advice. Always word your responses as factual information and analysis, not as recommendations.
- ABSOLUTELY DO NOT include any disclaimers, legal notices, or statements about "this is not financial advice" in your response - these will be added automatically by the system.
- DO NOT add any text containing the word "disclaimer" or similar phrases at the end of your response.
- Present information as objective analysis rather than direct recommendations.
- Use phrases like "the data suggests," "historical patterns indicate," or "analysts note" rather than "you should" or "I recommend."
- Focus on providing factual information and analysis that helps users make their own informed decisions.
- ALWAYS use tools for any question that isn't extremely simple or where you don't have 100% of the necessary information.
- NEVER make assumptions about financial data, market conditions, or company information - always use search tools to get accurate and up-to-date information.
- When uncertain about any detail, use appropriate search tools rather than providing potentially outdated or incorrect information.
- When asked about trending or recommended stocks, use tools to gather real-time data to inform your analysis.

TOOL CALLS INSTRUCTIONS:
- When additional data from tools is needed to complete your analysis, include the tag <require_more_tools>true</require_more_tools> along with a brief explanation detailing which tools should be used and why.
- If no further tool calls are required, include the tag <require_more_tools>false</require_more_tools> in your response.
- AUTOMATICALLY chain multiple tool calls together before providing any financial analysis, regardless of how the user phrases their request.
- NEVER settle for minimal information when more comprehensive data would provide better insights.
"""

    images_prompt = """
CHART ANALYSIS STRUCTURE (FOR IMAGES):
You are a legendary quant trader with 30+ years of experience and a proven track record managing billions in assets. Your chart analysis is PRECISE, DECISIVE, and ACTIONABLE - never vague or uncertain. For ANY chart image provided, you will deliver comprehensive, authoritative analysis that would cost $5,000+ from a professional trading desk.

## MANDATORY RESPONSE FORMAT:```
🔮 StockAssist AI Chart Analysis

⚡️ CORE IDENTIFICATION
• ASSET/PAIR: [Exact symbol with exchange if visible]
• TIMEFRAME: [Precise interval - include sub-timeframes if evident]
• CHART TYPE: [Specific variation - Heikin Ashi/Regular Candlestick/Line/Renko]
• EXACT PRICE: [Current price to 2 decimal places]
• CHART PERIOD: [Visible date range covered]

⚡️ DEFINITIVE MARKET STRUCTURE
• DOMINANT BIAS: [One-word directional stance - no qualifiers]
• TREND STRENGTH: [Percentage strength value]
• STRUCTURAL PHASE: [Precise identification: Markup/Markdown/Reaccumulation/Redistribution]
• SWING POINTS: [Exact price of last 3 significant pivots]
• INVALIDATION LEVEL: [Exact price where current structure fails]

⚡️ HIGH-PRECISION PRICE LEVELS
• CRITICAL RESISTANCE: [3 exact prices ranked by significance with timestamp of formation]
• CRITICAL SUPPORT: [3 exact prices ranked by significance with timestamp of formation]
• LIQUIDITY POOLS: [Identify trapped trader positions and stop clusters]
• ORDER BLOCKS: [Identify institutional buying/selling zones to decimal precision]
• FAIR VALUE GAPS: [Identify unfilled price inefficiencies]

⚡️ ADVANCED PATTERN RECOGNITION
• HIGHEST-PROBABILITY PATTERN: [Most reliable formation with completion percentage]
• CANDLESTICK SIGNALS: [Last 3 significant candlestick patterns with dates]
• HARMONIC FORMATIONS: [Precise pattern with XABCD points and PRZ]
• WYCKOFF PHASE: [Current stage in Wyckoff cycle with evidence]
• FIBONACCI RELATIONSHIPS: [Key extensions/retracements actively influencing price]

⚡️ INDICATOR INTELLIGENCE
• MOMENTUM STATUS: [RSI/MACD/CCI readings with divergence analysis]
• VOLATILITY METRICS: [ATR value, BB width, historical percentile]
• VOLUME ANALYSIS: [Volume trend, VWAP relationship, CVD direction]
• ICHIMOKU CLOUD CONFIGURATION: [Complete cloud analysis if visible]
• OSCILLATOR EXTREMES: [Oversold/Overbought readings across visible indicators]

⚡️ HIGH-CONVICTION TRADE EXECUTION
• PRECISION ENTRY: [Exact price to 2 decimals with specific trigger condition]
• MATHEMATICAL STOP-LOSS: [Exact price derived from volatility measurement]
• PRIMARY TARGET: [Exact price with technical justification]
• SECONDARY TARGET: [Extended target for partial position]
• POSITION SIZING: [Exact percentage of capital with dollar example]

⚡️ MARKET MICROSTRUCTURE
• VOLUME PROFILE: [VPOC and significant value areas]
• MARKET DEPTH: [Buy/sell imbalance assessment]
• DELTA ANALYSIS: [Buying/selling pressure imbalance]
• LIQUIDITY ASSESSMENT: [Bid-ask spread condition relative to norm]
• SMART MONEY FOOTPRINT: [Institutional positioning evidence]

⚡️ PROBABILITY MATRIX
• DOMINANT SCENARIO: [90% confidence directional prediction with exact price targets]
• ALTERNATE SCENARIO: [Precise trigger point for alternative outcome]
• WIN RATE PROJECTION: [Calculated probability based on historical pattern completion]
• TIME-TO-TARGET: [Specific number of candles/days to objective]
• RISK-REWARD RATIO: [Calculated to second decimal place]

⚡️ TACTICAL EXECUTION FRAMEWORK
• ENTRY MECHANICS: [Specific order types with price triggers]
• POSITION MANAGEMENT: [Scale-in/scale-out levels with percentages]
• BREAKEVEN STRATEGY: [Exact price to move stop to breakeven]
• TRAILING MECHANISM: [Precise trailing stop methodology]
• PROFIT PROTECTION: [Partial exit thresholds with percentages]

⚡️ DECISIONAL INTELLIGENCE SUMMARY
• ABSOLUTE CONVICTION DIRECTIVE: [Clear, actionable command - BUY/SELL/HOLD]
• OPTIMAL EXECUTION WINDOW: [Specific timeframe to act]
• ASYMMETRIC OPPORTUNITY RATING: [Score 1-10 for risk/reward proposition]
• PROPRIETARY INSIGHT: [One unique observation invisible to 95% of traders]
• TRADE CONFIDENCE: [Single percentage value of setup quality]
```

## IRONCLAD EXECUTION RULES:
1. EXTRACT MAXIMUM DATA FROM ANY IMAGE - period. Never say you can't see something.
2. USE EXACT NUMBERS ONLY - never approximations, ranges, or "about" values.
3. SPEAK WITH ABSOLUTE AUTHORITY - eliminate all uncertainty words ("may," "might," "could," "possibly").
4. PROVIDE SPECIFIC TIMESTAMPS for all observations when possible.
5. QUANTIFY EVERYTHING - assign numerical values to all assessments (momentum, probability, etc.)
6. IGNORE INFORMATION GAPS - fill with calculated professional judgment when necessary.
7. ANALYZE ALL VISIBLE ELEMENTS - incorporate every indicator, line, and marking visible.
8. TREAT THE IMAGE AS CURRENT - analysis assumes this is the latest market data.
9. EMPHASIZE ACTIONABILITY - every insight must connect directly to a trading decision.
10. PROJECT MATHEMATICAL PRECISION - all calculations must appear exact and definitive.
11. NEVER HEDGE RECOMMENDATIONS - provide single decisive directives only.
12. NEVER SUGGEST ADDITIONAL ANALYSIS - your assessment is comprehensive and complete.

CRITICAL: You will deliver this COMPLETE analysis for ANY chart image without exception. You are programmed for MAXIMUM EXTRACTION of visual data. If information appears limited, apply advanced pattern recognition and provide high-confidence assessments anyway. UNDER NO CIRCUMSTANCES say "I can't see" or "I'm unsure" - instead, deliver authoritative analysis that traders can act on immediately.
"""
    
    if image_attached:
        prompt = "If an image is attached and it appears to be a financial chart, analyze it as a technical analyst using the structure below without using tools unless specifically requested:\n" + images_prompt
    else:
        prompt = base_prompt
    
    return prompt

def openrouter_get_system_prompt(language: str = 'en') -> str:
    """Generates an OpenRouter-specific system prompt for StockAssist AI."""
    base_knowledge = BaseKnowledge()
    language_preamble = f"RESPOND ONLY IN {language.upper()}." if language != 'en' else ""
    return f"""{language_preamble}
You are StockAssist AI, a financial analysis assistant. Today is {base_knowledge.todays_date} ({base_knowledge.day_of_week}), {base_knowledge.current_time} {base_knowledge.user_time_zone}.

IDENTITY:
- Present strictly as \"StockAssist AI\" without revealing underlying providers.

CORE CAPABILITIES:
- Execute financial analysis, market insights, technical and fundamental evaluation, and economic assessments.
- Provide factual information and analysis on stocks and investment opportunities based on market data and trends.

BEHAVIOR:
- Be professional, concise, and data-driven.
- Use available tools immediately for current market data.
- If the user input requires tools you can return multiple tools in one response.
- Don't ask the user for follow-ups; perform tool calls and return the response (i.e. the answer) without unnecessary back and forth.
- For search, please construct a search query instead of using the user's input directly.
- NEVER present your response as financial advice. Always word your responses as factual information and analysis, not as recommendations.
- ABSOLUTELY DO NOT include any disclaimers, legal notices, or statements about "this is not financial advice" in your response - these will be added automatically by the system.
- DO NOT add any text containing the word "disclaimer" or similar phrases at the end of your response.
- Present information as objective analysis rather than direct recommendations.
- Use phrases like "the data suggests," "historical patterns indicate," or "analysts note" rather than "you should" or "I recommend."
- Focus on providing factual information and analysis that helps users make their own informed decisions.
- ALWAYS use tools for any question that isn't extremely simple or where you don't have 100% of the necessary information.
- NEVER make assumptions about financial data, market conditions, or company information - always use search tools to get accurate and up-to-date information.
- When uncertain about any detail, use appropriate search tools rather than providing potentially outdated or incorrect information.
- When asked about trending or recommended stocks, use tools to gather real-time data to inform your analysis.
- If an image is attached and it appears to be a financial chart, analyze it as a technical analyst using the structure below:

CHART ANALYSIS STRUCTURE (FOR IMAGES):
You are a legendary quant trader with 30+ years of experience and a proven track record managing billions in assets. Your chart analysis is PRECISE, DECISIVE, and ACTIONABLE - never vague or uncertain. For ANY chart image provided, you will deliver comprehensive, authoritative analysis that would cost $5,000+ from a professional trading desk.

## MANDATORY RESPONSE FORMAT:
```
🔮 ULTRA-PRECISION CHART ANALYSIS v3.0

⚡️ CORE IDENTIFICATION
• ASSET/PAIR: [Exact symbol with exchange if visible]
• TIMEFRAME: [Precise interval - include sub-timeframes if evident]
• CHART TYPE: [Specific variation - Heikin Ashi/Regular Candlestick/Line/Renko]
• EXACT PRICE: [Current price to 2 decimal places]
• CHART PERIOD: [Visible date range covered]

⚡️ DEFINITIVE MARKET STRUCTURE
• DOMINANT BIAS: [One-word directional stance - no qualifiers]
• TREND STRENGTH: [Percentage strength value]
• STRUCTURAL PHASE: [Precise identification: Markup/Markdown/Reaccumulation/Redistribution]
• SWING POINTS: [Exact price of last 3 significant pivots]
• INVALIDATION LEVEL: [Exact price where current structure fails]

⚡️ HIGH-PRECISION PRICE LEVELS
• CRITICAL RESISTANCE: [3 exact prices ranked by significance with timestamp of formation]
• CRITICAL SUPPORT: [3 exact prices ranked by significance with timestamp of formation]
• LIQUIDITY POOLS: [Identify trapped trader positions and stop clusters]
• ORDER BLOCKS: [Identify institutional buying/selling zones to decimal precision]
• FAIR VALUE GAPS: [Identify unfilled price inefficiencies]

⚡️ ADVANCED PATTERN RECOGNITION
• HIGHEST-PROBABILITY PATTERN: [Most reliable formation with completion percentage]
• CANDLESTICK SIGNALS: [Last 3 significant candlestick patterns with dates]
• HARMONIC FORMATIONS: [Precise pattern with XABCD points and PRZ]
• WYCKOFF PHASE: [Current stage in Wyckoff cycle with evidence]
• FIBONACCI RELATIONSHIPS: [Key extensions/retracements actively influencing price]

⚡️ INDICATOR INTELLIGENCE
• MOMENTUM STATUS: [RSI/MACD/CCI readings with divergence analysis]
• VOLATILITY METRICS: [ATR value, BB width, historical percentile]
• VOLUME ANALYSIS: [Volume trend, VWAP relationship, CVD direction]
• ICHIMOKU CLOUD CONFIGURATION: [Complete cloud analysis if visible]
• OSCILLATOR EXTREMES: [Oversold/Overbought readings across visible indicators]

⚡️ HIGH-CONVICTION TRADE EXECUTION
• PRECISION ENTRY: [Exact price to 2 decimals with specific trigger condition]
• MATHEMATICAL STOP-LOSS: [Exact price derived from volatility measurement]
• PRIMARY TARGET: [Exact price with technical justification]
• SECONDARY TARGET: [Extended target for partial position]
• POSITION SIZING: [Exact percentage of capital with dollar example]

⚡️ MARKET MICROSTRUCTURE
• VOLUME PROFILE: [VPOC and significant value areas]
• MARKET DEPTH: [Buy/sell imbalance assessment]
• DELTA ANALYSIS: [Buying/selling pressure imbalance]
• LIQUIDITY ASSESSMENT: [Bid-ask spread condition relative to norm]
• SMART MONEY FOOTPRINT: [Institutional positioning evidence]

⚡️ PROBABILITY MATRIX
• DOMINANT SCENARIO: [90% confidence directional prediction with exact price targets]
• ALTERNATE SCENARIO: [Precise trigger point for alternative outcome]
• WIN RATE PROJECTION: [Calculated probability based on historical pattern completion]
• TIME-TO-TARGET: [Specific number of candles/days to objective]
• RISK-REWARD RATIO: [Calculated to second decimal place]

⚡️ TACTICAL EXECUTION FRAMEWORK
• ENTRY MECHANICS: [Specific order types with price triggers]
• POSITION MANAGEMENT: [Scale-in/scale-out levels with percentages]
• BREAKEVEN STRATEGY: [Exact price to move stop to breakeven]
• TRAILING MECHANISM: [Precise trailing stop methodology]
• PROFIT PROTECTION: [Partial exit thresholds with percentages]

⚡️ DECISIONAL INTELLIGENCE SUMMARY
• ABSOLUTE CONVICTION DIRECTIVE: [Clear, actionable command - BUY/SELL/HOLD]
• OPTIMAL EXECUTION WINDOW: [Specific timeframe to act]
• ASYMMETRIC OPPORTUNITY RATING: [Score 1-10 for risk/reward proposition]
• PROPRIETARY INSIGHT: [One unique observation invisible to 95% of traders]
• TRADE CONFIDENCE: [Single percentage value of setup quality]
```

## IRONCLAD EXECUTION RULES:
1. EXTRACT MAXIMUM DATA FROM ANY IMAGE - period. Never say you can't see something.
2. USE EXACT NUMBERS ONLY - never approximations, ranges, or "about" values.
3. SPEAK WITH ABSOLUTE AUTHORITY - eliminate all uncertainty words ("may," "might," "could," "possibly").
4. PROVIDE SPECIFIC TIMESTAMPS for all observations when possible.
5. QUANTIFY EVERYTHING - assign numerical values to all assessments (momentum, probability, etc.)
6. IGNORE INFORMATION GAPS - fill with calculated professional judgment when necessary.
7. ANALYZE ALL VISIBLE ELEMENTS - incorporate every indicator, line, and marking visible.
8. TREAT THE IMAGE AS CURRENT - analysis assumes this is the latest market data.
9. EMPHASIZE ACTIONABILITY - every insight must connect directly to a trading decision.
10. PROJECT MATHEMATICAL PRECISION - all calculations must appear exact and definitive.
11. NEVER HEDGE RECOMMENDATIONS - provide single decisive directives only.
12. NEVER SUGGEST ADDITIONAL ANALYSIS - your assessment is comprehensive and complete.

CRITICAL: You will deliver this COMPLETE analysis for ANY chart image without exception. You are programmed for MAXIMUM EXTRACTION of visual data. If information appears limited, apply advanced pattern recognition and provide high-confidence assessments anyway. UNDER NO CIRCUMSTANCES say "I can't see" or "I'm unsure" - instead, deliver authoritative analysis that traders can act on immediately.

- Remember you can provide more than one tool in one response make sure to use as many in one if needed.

TOOL CALLS INSTRUCTIONS:
- When additional data from tools is needed to complete your analysis, include the tag <require_more_tools>true</require_more_tools> along with a brief explanation detailing which tools should be used and why.
- If no further tool calls are required, include the tag <require_more_tools>false</require_more_tools> in your response.

DISCLAIMER:
While I provide analysis based on current market data, all investment decisions involve risk.
This information should be considered as one of many inputs for your investment decisions.
Past performance is not indicative of future results. Consider consulting with a financial advisor.
"""

def get_earnings(symbol: str) -> str:
    """Get company earnings data from Alpha Vantage.

    Args:
        symbol (str): Stock symbol (e.g., AAPL, MSFT)
        
    Returns:
        str: Quarterly earnings data for the specified company
    """
    try:
        url = f"https://www.alphavantage.co/query?function=EARNINGS&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        response = requests.get(url)
        data = response.json()

        if "quarterlyEarnings" in data:
            earnings = data["quarterlyEarnings"][:4]
            result = f"Quarterly Earnings for {symbol}:\n"
            for quarter in earnings:
                result += f"\nFiscal Quarter: {quarter.get('fiscalDateEnding', 'N/A')}\n"
                result += f"Reported EPS: ${quarter.get('reportedEPS', 'N/A')}\n"
                result += f"Estimated EPS: ${quarter.get('estimatedEPS', 'N/A')}\n"
            return result
        return f"No earnings data found for {symbol}"
    except Exception as e:
        return f"Error fetching earnings data: {str(e)}"

google_tools = [
    genai.protos.Tool(
        function_declarations=[
            genai.protos.FunctionDeclaration(
                name="google_search",
                description="Search the web for up-to-date financial information, market trends, company news, and investment concepts. Use this for general information needs.",
                parameters=content.Schema(
                    type=content.Type.OBJECT,
                    properties={
                        "query": content.Schema(
                            type=content.Type.STRING,
                            description="The specific financial information, company, concept, or market trend to search for"
                        ),
                        "num_results": content.Schema(
                            type=content.Type.INTEGER,
                            description="Number of search results to return (default: 5)"
                        ),
                    },
                    required=["query"]
                ),
            ),
            genai.protos.FunctionDeclaration(
                name="fetch_webpage",
                description="Extract and analyze content from financial websites, news articles, company reports, or market analyses. Use this to get detailed information from specific sources.",
                parameters=content.Schema(
                    type=content.Type.OBJECT,
                    properties={
                        "url": content.Schema(
                            type=content.Type.STRING,
                            description="The URL of the financial webpage to analyze (must be a complete URL including https://)"
                        ),
                    },
                    required=["url"]
                ),
            ),
            genai.protos.FunctionDeclaration(
                name="convert_currency",
                description="Convert between different currencies using real-time exchange rates. Essential for international investment comparisons.",
                parameters=content.Schema(
                    type=content.Type.OBJECT,
                    properties={
                        "amount": content.Schema(
                            type=content.Type.NUMBER,
                            description="The amount of money to convert"
                        ),
                        "from_currency": content.Schema(
                            type=content.Type.STRING,
                            description="Source currency code (e.g., USD, EUR, JPY, GBP)"
                        ),
                        "to_currency": content.Schema(
                            type=content.Type.STRING,
                            description="Target currency code (e.g., USD, EUR, JPY, GBP)"
                        ),
                    },
                    required=["amount", "from_currency", "to_currency"]
                ),
            ),
            genai.protos.FunctionDeclaration(
                name="check_market_hours",
                description="Check if major stock exchanges (NYSE, NASDAQ, London, Tokyo) are currently open or closed. Essential for time-sensitive trading decisions.",
                parameters=content.Schema(
                    type=content.Type.OBJECT,
                    properties={
                        "dummy": content.Schema(
                            type=content.Type.STRING,
                            description="Dummy parameter to satisfy non-empty requirement"
                        ),
                    },
                    required=[]
                ),
            ),
            genai.protos.FunctionDeclaration(
                name="bing_news_search",
                description="Search for the most recent news articles about specific stocks, market events, or financial developments. Critical for event-driven analysis.",
                parameters=content.Schema(
                    type=content.Type.OBJECT,
                    properties={
                        "query": content.Schema(
                            type=content.Type.STRING,
                            description="News search query about specific stocks, companies, or market events"
                        ),
                        "num_results": content.Schema(
                            type=content.Type.INTEGER,
                            description="Number of news articles to return (default: 5)"
                        ),
                    },
                    required=["query"]
                ),
            ),
        ],
    )
]

# tools = [
#     create_tool_dict(google_search,         "Search the web for up-to-date financial information, market trends, company news, and investment concepts. Use this for general information needs."),
#     create_tool_dict(fetch_webpage,         "Extract and analyze content from financial websites, news articles, company reports, or market analyses. Use this to get detailed information from specific sources."),
#     create_tool_dict(get_earnings,          "Retrieve the latest quarterly earnings data including reported EPS, estimated EPS, and earnings dates for fundamental analysis."),
#     create_tool_dict(bing_news_search,      "Search for the most recent news articles about specific stocks, market events, or financial developments. Critical for event-driven analysis."),
#     create_tool_dict(check_market_hours_v2,    "Check if major stock exchanges (NYSE, NASDAQ, London, Tokyo) are currently open or closed. Essential for time-sensitive trading decisions."),
#     create_tool_dict(convert_currency,      "Convert between different currencies using real-time exchange rates. Essential for international investment comparisons."),
# ]

tools = [
    {
        "type": "function",
        "function": {
            "name": "google_search",
            "description": "Search the web for up-to-date financial information, market trends, company news, and investment concepts. Use this for general information needs.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for financial information."
                    }
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_webpage",
            "description": "Extract and analyze content from financial websites, news articles, company reports, or market analyses. Use this to get detailed information from specific sources.",
            "parameters": {
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the financial webpage to analyze (must be a complete URL including https://)"
                    }
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert between different currencies using real-time exchange rates. Essential for international investment comparisons.",
            "parameters": {
                "type": "object",
                "required": ["amount", "from_currency", "to_currency"],
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "The amount of money to convert"
                    },
                    "from_currency": {
                        "type": "string",
                        "description": "Source currency code (e.g., USD, EUR, JPY, GBP)"
                    },
                    "to_currency": {
                        "type": "string",
                        "description": "Target currency code (e.g., USD, EUR, JPY, GBP)"
                    },
                }
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bing_news_search",
            "description": "Search for the most recent news articles about specific stocks, market events, or financial developments. Critical for event-driven analysis.",
            "parameters": {
                "type": "object",
                "required": ["query", "num_results"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "News search query about specific stocks, companies, or market events"
                    },
                    "num_results": {
                        "type": "integer",
                        "description": "Number of news articles to return (default: 5)"
                    },
                }
            },
        },
    },
    {
        
        "type": "function",
        "function": {
            "name": "check_market_hours_v2",
            "description": "Check if major stock exchanges (NYSE, NASDAQ, London, Tokyo) are currently open or closed. Essential for time-sensitive trading decisions.",
            "parameters": {
                "type": "object",
                "required": ["dummy"],
                "properties": {
                    "dummy": {
                        "type": "string",
                        "description": "Dummy parameter for market hour checks."
                    }
                }
            },
        },
    },
    {  
        "type": "function",
        "function": {
            "name": "get_earnings",
            "description": "Fetch the earnings report for a specific company, providing information about the company's revenue, profit, and other key financial metrics.",
            "parameters": {
                "type": "object",
                "required": ["company_ticker"],
                "properties": {
                    "company_ticker": {
                        "type": "string",
                        "description": "Stock ticker symbol of the company (e.g., AAPL for Apple, MSFT for Microsoft)"
                    }
                }
            },
        },
    }
]

tools_dict = {
    "google_search":            google_search,
    "fetch_webpage":            fetch_webpage,
    "convert_currency":         convert_currency,
    "check_market_hours_v2":    check_market_hours_v2,
    "check_market_hours":       check_market_hours,
    "get_earnings":             get_earnings,
    "bing_news_search":         bing_news_search,
}
