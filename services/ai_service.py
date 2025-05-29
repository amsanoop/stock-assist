import base64
import io
import json
import os
import re
import sys
import tempfile
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models import AIOperation, db
from .tools import (BaseKnowledge, get_system_prompt, google_tools,
                    openrouter_get_system_prompt, parse_arguments,
                    parse_arguments_openrouter, tools, tools_dict)

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "google")

if AI_PROVIDER == "google":
    import google.generativeai as genai
    from google.generativeai.protos import FunctionResponse
    from google.protobuf.struct_pb2 import Struct

    genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))
elif AI_PROVIDER == "openrouter":
    pass


class AIService:
    """StockAssist AI service for financial analysis and stock market insights."""

    def __init__(self, model: str = None, language: str = 'en'):
        """Initializes the StockAssist AI service.

        Args:
            model (str, optional): The name of the language model to use. Defaults to None.
            language (str, optional): The language code for responses. Defaults to 'en'.
        """
        self.language: str = language
        self.base_knowledge: BaseKnowledge = BaseKnowledge()
        self.chat: Any = None

        if AI_PROVIDER == "google":
            self.model_name: str = model or os.getenv("GOOGLE_AI_MODEL", "gemini-2.0-flash-lite")
            self.model_config: Dict[str, Any] = {
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
        elif AI_PROVIDER == "openrouter":
            self.model_name: str = model or os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-opus:beta")
            self.model_config: Dict[str, Any] = {
                "temperature": float(os.getenv("OPENROUTER_TEMPERATURE", 0.7)),
                "top_p": float(os.getenv("OPENROUTER_TOP_P", 0.95)),
                "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", 4096)),
            }
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )
    
    def token_count(
        self,
        text: str,
        images: Optional[List[Dict[str, Any]]] = None
    ) -> int:
        """Count the number of tokens in a text using the OpenAI tokenizer.

        Args:
            text (str): The text to count tokens in.

        Returns:
            int: The number of tokens in the text.
        """
        images_parts: List[Any] = []
        if images:
            for img_data in images:
                if 'data' in img_data:
                    try:
                        mime_type: str = img_data.get('mime_type', 'image/jpeg')
                        file_extension: str = '.jpg'

                        name: str = img_data.get('name', '').lower()
                        if name.endswith('.png'):
                            file_extension = '.png'
                            mime_type = mime_type or 'image/png'
                        elif name.endswith(('.jpg', '.jpeg')):
                            file_extension = '.jpg'
                            mime_type = mime_type or 'image/jpeg'
                        elif name.endswith('.gif'):
                            file_extension = '.gif'
                            mime_type = mime_type or 'image/gif'
                        elif name.endswith('.webp'):
                            file_extension = '.webp'
                            mime_type = mime_type or 'image/webp'

                        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
                            temp_file.write(img_data['data'])
                            temp_file_path: str = temp_file.name

                        try:
                            uploaded_file = genai.upload_file(file=temp_file_path, mime_type=mime_type)
                            images_parts.append(uploaded_file)
                        finally:
                            if os.path.exists(temp_file_path):
                                os.unlink(temp_file_path)
                    except:
                        try:
                            img: Image.Image = Image.open(io.BytesIO(img_data['data']))
                            images_parts.append(img)
                        except:
                            pass
        
        return self.model.count_tokens([text, *images_parts]).total_tokens if images_parts else self.model.count_tokens([text]).total_tokens

    def _append_disclaimer(self, text: str) -> str:
        """Appends a disclaimer to the given text if it doesn't already contain disclaimer-related phrases.

        Args:
            text (str): The text to which the disclaimer may be appended.

        Returns:
            str: The original text with the disclaimer appended, or the original text if it already contains a disclaimer.
        """
        disclaimer = "\n\n---\n**DISCLAIMER**: **This information is provided for research and educational purposes only. It is not financial advice and should not be construed as such. StockAssist is a research tool that aggregates publicly available information. All investment decisions should be made based on your own research and in consultation with a qualified financial advisor.**"

        disclaimer_phrases = [
            "DISCLAIMER",
            "disclaimer",
            "not financial advice",
            "not investment advice",
            "for educational purposes",
            "for informational purposes",
            "consult with a financial advisor",
            "consult a qualified financial advisor"
        ]

        if any(phrase in text for phrase in disclaimer_phrases):
            return text

        return text + disclaimer

    def get_response_with_tracking(
        self,
        operation_id: str,
        message: str,
        images: Optional[List[Dict[str, Any]]] = None,
        symbols: Optional[List[str]] = None,
        chat_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[str] = None,
    ) -> str:
        """Get a response from StockAssist AI with step tracking.

        Args:
            operation_id (str): The ID of the AIOperation to update.
            message (str): The message to process.
            images (Optional[List[Dict[str, Any]]], optional): List of image data dictionaries. Defaults to None.
            symbols (Optional[List[str]], optional): List of stock symbols. Defaults to None.
            chat_history (Optional[List[Dict[str, str]]], optional): Chat history. Defaults to None.
            context (Optional[str], optional): Additional context.

        Returns:
            str: The final response from StockAssist AI.
        """
        operation: AIOperation = AIOperation.query.get(operation_id)
        if not operation:
            raise ValueError("Invalid operation ID")

        try:
            operation.status = 'processing'
            operation.update_step('Initializing analysis')

            if AI_PROVIDER == "google":
                return self._get_google_response(operation, message, images, symbols, chat_history, context)
            elif AI_PROVIDER == "openrouter":
                return self._get_openrouter_response(operation, message, images, symbols, chat_history, context)
            else:
                operation.fail("Configuration error")
                raise ValueError("Invalid configuration")

        except Exception as e:
            error_msg: str = str(e)
            operation.fail(error_msg)
            raise

    def _needs_comprehensive_search(self, message: str) -> tuple[bool, int]:
        """Determines if a query needs comprehensive web search and how many searches to require.

        Args:
            message (str): The query message.

        Returns:
            tuple[bool, int]: A tuple containing a boolean indicating if a comprehensive search is needed, and an integer indicating the minimum number of searches to require.
        """
        message_lower = message.lower()

        stock_keywords = {
            "stock", "market", "company", "earnings", "revenue", "profit",
            "share", "price", "trading", "investor", "investment", "dividend",
            "nasdaq", "nyse", "dow", "s&p", "index", "etf", "fund",
            "bull", "bear", "trend", "analysis", "forecast", "prediction",
            "performance", "growth", "decline", "merger", "acquisition"
        }

        latest_info_keywords = {
            "latest", "recent", "current", "today", "now", "update",
            "news", "announcement", "development", "report", "release",
            "this week", "this month", "this year", "forecast", "outlook",
            "future", "upcoming", "expected", "planned", "scheduled"
        }

        words = set(message_lower.split())

        is_question = any(q in message_lower for q in ["what", "when", "where", "who", "why", "how", "?"])
        has_stock_keywords = any(keyword in message_lower for keyword in stock_keywords)
        needs_latest_info = any(keyword in message_lower for keyword in latest_info_keywords)

        min_searches = 1
        if is_question:
            if has_stock_keywords and needs_latest_info:
                min_searches = 3
            elif has_stock_keywords or needs_latest_info:
                min_searches = 2

        needs_search = True
        return needs_search, min_searches

    def _execute_search_query(self, query: str) -> Dict[str, Any]:
        """Execute a search query and return results in a standardized format.

        Args:
            query (str): The search query to execute.

        Returns:
            Dict[str, Any]: Standardized search results with both raw and formatted data.
        """
        try:
            search_results = tools_dict["google_search"](query=query)

            result_text = "Search Results:\n\n"
            formatted_results = []

            for item in search_results:
                result_dict = {}
                if hasattr(item, '__dict__'):
                    result_dict = item.__dict__
                    for key, value in item.__dict__.items():
                        result_text += f"{key.capitalize()}: {value}\n"
                elif isinstance(item, dict):
                    result_dict = item
                    for key, value in item.items():
                        result_text += f"{key.capitalize()}: {value}\n"
                else:
                    result_dict = {
                        "title": item.title,
                        "description": item.description,
                        "url": item.url
                    }
                    result_text += f"Title: {item.title}\nDescription: {item.description}\nURL: {item.url}\n"

                formatted_results.append(result_dict)
                result_text += "\n"

            return {
                "success": True,
                "raw_results": search_results,
                "formatted_results": formatted_results,
                "text_output": result_text,
                "query": query
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "query": query
            }

    def _parse_search_query(self, text: str) -> Optional[str]:
        """Parse the search query from the response text.

        Args:
            text (str): The response text to parse.

        Returns:
            Optional[str]: The search query if found, None otherwise.
        """
        if not text:
            return None

        pattern = r"<search>(.*?)</search>"
        match = re.search(pattern, text, re.DOTALL)

        if match:
            return match.group(1).strip()
        return None

    def _get_google_response(
        self,
        operation: AIOperation,
        message: str,
        images: Optional[List[Dict[str, Any]]],
        symbols: Optional[List[str]],
        chat_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[str] = None,
    ) -> str:
        """Retrieve a response from the Google AI model.

        Args:
            operation (AIOperation): The AIOperation object for tracking.
            message (str): The user's message.
            images (Optional[List[Dict[str, Any]]]): A list of image data.
            symbols (Optional[List[str]]): A list of stock symbols.
            chat_history (Optional[List[Dict[str, str]]]): The chat history.
            context (Optional[str]): Additional context.

        Returns:
            str: The response from the Google AI model.
        """
        operation.update_step('Preparing request')

        needs_comprehensive_search, min_required_searches = self._needs_comprehensive_search(message)
        needs_comprehensive_search = needs_comprehensive_search and not symbols
        min_web_searches = min_required_searches if needs_comprehensive_search else 0
        web_search_count = 0

        history: List[Dict[str, Any]] = []
        if context:
            operation.update_step('Processing market data')
            history.append({
                "role": "user",
                "parts": [{"text": f"Current market data:\n{context}"}]
            })

        system_prompt: str = get_system_prompt(self.language, image_attached=bool(images))
        history.append({
            "role": "model",
            "parts": [{"text": system_prompt}]
        })

        if chat_history:
            operation.update_step('Processing chat history')
            for msg in chat_history[-5:]:
                if msg.get('role') and msg.get('content'):
                    role: str = 'user' if msg['role'] == 'user' else 'model'
                    history.append({
                        "role": role,
                        "parts": [msg['content']]
                    })

        user_parts: List[Any] = []

        if images:
            operation.update_step('Processing images')
            try:
                for img_data in images:
                    if 'data' in img_data:
                        try:
                            mime_type: str = img_data.get('mime_type', 'image/jpeg')
                            file_extension: str = '.jpg'

                            name: str = img_data.get('name', '').lower()
                            if name.endswith('.png'):
                                file_extension = '.png'
                                mime_type = mime_type or 'image/png'
                            elif name.endswith(('.jpg', '.jpeg')):
                                file_extension = '.jpg'
                                mime_type = mime_type or 'image/jpeg'
                            elif name.endswith('.gif'):
                                file_extension = '.gif'
                                mime_type = mime_type or 'image/gif'
                            elif name.endswith('.webp'):
                                file_extension = '.webp'
                                mime_type = mime_type or 'image/webp'

                            with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
                                temp_file.write(img_data['data'])
                                temp_file_path: str = temp_file.name

                            operation.update_step(f'Uploading image with mime type: {mime_type}')
                            try:
                                uploaded_file = genai.upload_file(file=temp_file_path, mime_type=mime_type)
                                user_parts.append(uploaded_file)
                                operation.update_step('Uploaded image successfully')
                            finally:
                                if os.path.exists(temp_file_path):
                                    os.unlink(temp_file_path)
                        except Exception as e:
                            operation.update_step(f'Uploading image fallback: {str(e)}')
                            try:
                                img: Image.Image = Image.open(io.BytesIO(img_data['data']))
                                user_parts.append(img)
                            except Exception as img_error:
                                operation.update_step(f'Image fallback failed: {str(img_error)}')
            except Exception as e:
                operation.update_step(f'Error processing images: {str(e)}')

        content: str = message
        if symbols:
            content = f"Regarding stocks: {', '.join(symbols)}\n{message}"

        if context:
            operation.update_step('Processing market data')
            content = f"Current market data:\n{context}\n\n{content}"

        if user_parts:
            user_parts.append({"text": content})
            history.append({
                "role": "user",
                "parts": user_parts
            })
        else:
            history.append({
                "role": "user",
                "parts": [{"text": content}]
            })

        operation.update_step('Starting analysis')
        chat = self.model.start_chat(history=history, enable_automatic_function_calling=True)

        operation.update_step('Processing request')
        response = chat.send_message("Please analyze the provided information and respond accordingly.")

        if not response.candidates:
            operation.fail("No response generated")
            return "No response generated"

        response_text: str = ""
        try:
            response_text = response.text
        except (AttributeError, TypeError):
            operation.update_step('Extracting response text')
            try:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
            except Exception as e:
                operation.update_step(f'Error extracting response text: {str(e)}')

        all_tool_results: List[Dict[str, Any]] = []
        round_count: int = 0
        max_rounds: int = 10

        while round_count < max_rounds:
            operation.update_step(f'Checking for tool calls (round {round_count + 1}/{max_rounds})')

            has_function_calls: bool = False
            function_calls: List[Any] = []
            valid_function_calls: List[Any] = []

            try:
                for candidate in response.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            has_function_calls = True
                            function_calls.append(part.function_call)
            except Exception as e:
                operation.update_step(f'Error checking for function calls: {str(e)}')

            if not has_function_calls:
                require_more_tools_tag: Optional[bool] = self._parse_require_more_tools_tag(response_text)

                if needs_comprehensive_search and web_search_count < min_web_searches:
                    operation.update_step(f'Enforcing minimum web searches ({web_search_count}/{min_web_searches})')
                    more_tools_response = chat.send_message(
                        "Respond only with a search query in this exact format: <search>your search query here</search>"
                    )

                    search_query = self._parse_search_query(more_tools_response.text)
                    if search_query:
                        operation.update_step(f'Executing search query: {search_query}')
                        search_result = self._execute_search_query(search_query)

                        if search_result["success"]:
                            operation.update_step('Sending search results to AI')
                            response = chat.send_message(
                                f"Search Results for '{search_query}':\n\n{search_result['text_output']}\n\n"
                                "Please analyze these results and continue with your response."
                            )
                            web_search_count += 1
                        else:
                            operation.update_step(f'Search failed: {search_result["error"]}')
                    else:
                        operation.update_step('No valid search query found in response')

                    try:
                        has_function_calls = False
                        for candidate in response.candidates:
                            for part in candidate.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    has_function_calls = True
                                    break
                    except Exception as e:
                        operation.update_step(f'Error checking for function calls: {str(e)}')

                elif require_more_tools_tag is False or round_count >= max_rounds - 1:
                    operation.update_step('No more tool calls needed or reached round limit')
                    if round_count == 0:
                        operation.update_step('WARNING: No tools were used to process this request')
                    break
                elif require_more_tools_tag is True:
                    operation.update_step('Explicitly requesting more tools')
                    more_tools_response = chat.send_message("Please use additional tools to enhance your analysis. What specific data would be helpful to provide a more comprehensive response?")
                    try:
                        has_function_calls = False
                        function_calls = []
                        for candidate in more_tools_response.candidates:
                            for part in candidate.content.parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    has_function_calls = True
                                    function_calls.append(part.function_call)

                        if not has_function_calls:
                            operation.update_step('No additional tools requested despite tag')
                            break
                    except Exception as e:
                        operation.update_step(f'Error processing more tools request: {str(e)}')
                        break
                else:
                    operation.update_step('No explicit tool request found, proceeding with final response')
                    break

            round_count += 1

            for fn_call in function_calls:
                fn_name: str = fn_call.name
                arguments: Dict[str, Any] = {}

                if hasattr(fn_call, 'args'):
                    arguments = parse_arguments(fn_call.args)

                if fn_name in ["google_search", "bing_news_search"]:
                    web_search_count += 1

                if fn_name in ["get_stock_quote", "get_company_overview", "get_earnings"]:
                    if 'symbol' not in arguments or not arguments['symbol']:
                        if symbols and len(symbols) > 0:
                            arguments['symbol'] = symbols[0]
                            operation.update_step(f'Added missing symbol parameter ({symbols[0]}) to {fn_name}')
                        else:
                            potential_symbols: List[str] = self._extract_potential_symbols(message)
                            if potential_symbols:
                                arguments['symbol'] = potential_symbols[0]
                                operation.update_step(f'Extracted symbol {potential_symbols[0]} from message for {fn_name}')
                            else:
                                operation.update_step(f'Skipping {fn_name} call due to missing symbol parameter')
                                continue

                if fn_name in ["google_search", "bing_news_search"]:
                    if 'query' not in arguments or not arguments.get('query'):
                        if fn_name == "bing_news_search" and symbols and len(symbols) > 0:
                            arguments['query'] = f"{symbols[0]} latest news"
                        else:
                            arguments['query'] = message
                        operation.update_step(f'Added missing query parameter to {fn_name}')

                valid_function_calls.append((fn_call, arguments))

            if not valid_function_calls:
                operation.update_step('No valid tool calls found, skipping this round')
                continue

            operation.update_step(f'Processing {len(valid_function_calls)} valid tool calls in round {round_count}')

            function_responses: List[FunctionResponse] = []

            for fn_call, arguments in valid_function_calls:
                fn_name = fn_call.name
                operation.update_step(f'Using tool: {fn_name}')

                try:
                    if fn_name not in tools_dict:
                        raise ValueError(f"Unknown tool: {fn_name}")

                    operation.update_step(f'Calling {fn_name} with arguments: {json.dumps(arguments)}')
                    result: Any = tools_dict[fn_name](**arguments)

                    tool_response_text: str = ""
                    if fn_name == "google_search":
                        tool_response_text = "Search Results:\n\n"
                        for item in result:
                            if hasattr(item, '__dict__'):
                                for key, value in item.__dict__.items():
                                    tool_response_text += f"{key.capitalize()}: {value}\n"
                            elif isinstance(item, dict):
                                for key, value in item.items():
                                    tool_response_text += f"{key.capitalize()}: {value}\n"
                            else:
                                tool_response_text += f"Title: {item.title}\nDescription: {item.description}\nURL: {item.url}\n"
                            tool_response_text += "\n"
                    elif fn_name == "bing_news_search":
                        if isinstance(result, str) and result.startswith("Error performing Bing news search"):
                            operation.update_step(f'Bing news search failed, using Google search as fallback')
                            try:
                                backup_results: Any = tools_dict["google_search"](query=f"{arguments.get('query', '')} news")
                                tool_response_text = f"News Search Results for {arguments.get('query', 'unknown')}:\n\n"
                                for item in backup_results:
                                    tool_response_text += f"Title: {item.title}\nDescription: {item.description}\nURL: {item.url}\n\n"
                            except Exception as fallback_error:
                                operation.update_step(f'Fallback search failed: {str(fallback_error)}')
                                tool_response_text = result
                        else:
                            tool_response_text = result
                    else:
                        tool_response_text = str(result)

                    all_tool_results.append({
                        "name": fn_name,
                        "arguments": arguments,
                        "result": tool_response_text,
                    })

                    s: Struct = Struct()
                    s.update({"result": tool_response_text})

                    function_response: FunctionResponse = FunctionResponse(
                        name=fn_name,
                        response=s,
                    )
                    function_responses.append(function_response)

                except Exception as e:
                    error_msg: str = f"Error with {fn_name}: {str(e)}"
                    operation.update_step(error_msg)

                    s = Struct()
                    s.update({"error": error_msg})

                    function_response = FunctionResponse(
                        name=fn_name,
                        response=s,
                    )
                    function_responses.append(function_response)

            if function_responses:
                operation.update_step(f'Sending tool results to AI (round {round_count})')
                try:
                    response = chat.send_message(function_responses)

                    try:
                        response_text = response.text
                    except (AttributeError, TypeError):
                        response_text = ""
                        try:
                            for part in response.candidates[0].content.parts:
                                if hasattr(part, 'text') and part.text:
                                    response_text += part.text
                        except Exception as e:
                            operation.update_step(f'Error extracting response text: {str(e)}')
                except Exception as e:
                    operation.update_step(f'Error sending tool results: {str(e)}')
                    break

                if round_count < max_rounds - 1:
                    more_tools_needed: Optional[bool] = self._parse_require_more_tools_tag(response_text)
                    if more_tools_needed is False:
                        operation.update_step(f'Model indicated no more tools needed after round {round_count}')
                        break

                response_text = self._clean_require_more_tools_tag(response_text)

        operation.update_step('Generating final analysis')

        final_text: str = self._clean_require_more_tools_tag(response_text) if response_text else ""

        if not final_text:
            fallback_response: str = "I've analyzed your request and gathered the following information:\n\n"
            for tool_result in all_tool_results:
                fallback_response += f"--- {tool_result['name']} ---\n{tool_result['result']}\n\n"

            if not all_tool_results:
                fallback_response = "I should use tools to provide you with real-time financial data and analysis. Let me try again with specific tool calls to get you accurate information."

            final_text = fallback_response

        operation.update_step('Requesting final comprehensive response')
        try:
            final_message: str = "Based on all the information gathered and analysis done, please provide your complete and comprehensive final response to the user's query. This will be shown directly to the user. Remember to word your response as if it's not financial advice but just the answer to what the user asked."
            final_response = chat.send_message(final_message)

            try:
                complete_response: str = final_response.text
            except (AttributeError, TypeError):
                complete_response = ""
                try:
                    for part in final_response.candidates[0].content.parts:
                        if hasattr(part, 'text') and part.text:
                            complete_response += part.text
                except Exception as e:
                    operation.update_step(f'Error extracting final response text: {str(e)}')
                    complete_response = final_text

            if complete_response and len(complete_response) > 20:
                final_text = self._clean_require_more_tools_tag(complete_response)
            else:
                operation.update_step('Using previous response as final output')
        except Exception as e:
            operation.update_step(f'Error getting final comprehensive response: {str(e)}')

        final_text_with_disclaimer = self._append_disclaimer(final_text)
        operation.complete(final_text_with_disclaimer)
        return final_text_with_disclaimer

    def _parse_require_more_tools_tag(self, text: str) -> Optional[bool]:
        """Parse the require_more_tools tag from the response text.

        Args:
            text (str): The response text to parse.

        Returns:
            Optional[bool]: True if more tools are required, False if not, None if tag not found.
        """
        if not text:
            return None

        pattern: str = r"<require_more_tools>(.*?)</require_more_tools>"
        match: Optional[re.Match[str]] = re.search(pattern, text, re.DOTALL)

        if match:
            value: str = match.group(1).strip().lower()
            if "true" in value:
                return True
            elif "false" in value:
                return False

        text = text.lower()

        return True if "true" in text else False if "false" in text else None

    def _clean_require_more_tools_tag(self, text: str) -> str:
        """Remove the require_more_tools tag from the response text.

        Args:
            text (str): The response text to clean.

        Returns:
            str: The cleaned response text.
        """
        if not text:
            return ""

        pattern: str = r"<require_more_tools>.*?</require_more_tools>"
        cleaned_text: str = re.sub(pattern, "", text, flags=re.DOTALL).strip()

        return cleaned_text

    def _get_openrouter_response(
        self,
        operation: "AIOperation",
        message: str,
        images: Optional[List[Dict[str, Any]]],
        symbols: Optional[List[str]],
        chat_history: Optional[List[Dict[str, str]]] = None,
        context: Optional[str] = None,
    ) -> str:
        """Process request using OpenRouter backend with advanced tool calling.

        Args:
            operation (AIOperation): AIOperation object for tracking progress and status.
            message (str): User's input message to process.
            images (Optional[List[Dict[str, Any]]]): List of image data dictionaries to process.
            symbols (Optional[List[str]]): List of stock symbols relevant to the query.
            chat_history (Optional[List[Dict[str, str]]]): Previous conversation history.
            context (Optional[str]): Additional market data context.

        Returns:
            str: Final response text from the AI.
        """
        operation.update_step("Preparing request")

        needs_comprehensive_search, min_required_searches = self._needs_comprehensive_search(message)
        needs_comprehensive_search = needs_comprehensive_search and not symbols
        min_web_searches = min_required_searches if needs_comprehensive_search else 0
        web_search_count = 0

        messages: List[Dict[str, Any]] = []

        if context:
            operation.update_step("Processing market data")
            messages.append({"role": "system", "content": f"Current market data:\n{context}"})

        system_prompt: str = openrouter_get_system_prompt(self.language)
        messages.append({"role": "system", "content": system_prompt})

        if chat_history:
            operation.update_step("Processing chat history")
            for msg in chat_history[-5:]:
                if msg.get("role") and msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        content_parts: List[Dict[str, Any]] = []

        if images:
            operation.update_step("Processing images")
            for img_data in images:
                if "data" in img_data:
                    img_bytes: bytes = img_data["data"]
                    img_base64: str = base64.b64encode(img_bytes).decode("utf-8")
                    content_parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"},
                        }
                    )

        user_message: str = message
        if symbols:
            user_message = f"Regarding stocks: {', '.join(symbols)}\n{message}"

        content_parts.append({"type": "text", "text": user_message})

        messages.append(
            {"role": "user", "content": content_parts if len(content_parts) > 1 else user_message}
        )

        operation.update_step("Processing request")

        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=self.model_config["temperature"],
                top_p=self.model_config["top_p"],
                max_tokens=self.model_config["max_tokens"],
                tools=tools,
                tool_choice="auto",
            )

            if not completion.choices or len(completion.choices) == 0:
                operation.fail("No response generated from initial request")
                return "I apologize, but I was unable to generate a response. Please try again."

            response_message: Any = completion.choices[0].message
            response_text: str = response_message.content or ""

            if not hasattr(response_message, "tool_calls") or not response_message.tool_calls:
                final_text = self._clean_require_more_tools_tag(response_text)
                operation.complete(final_text)
                return final_text

            tool_call_results: List[Dict[str, Any]] = []
            formatted_tool_results: List[Dict[str, Any]] = []

            for tool_call in response_message.tool_calls:
                try:
                    arguments: Dict[str, Any] = parse_arguments_openrouter(tool_call.function.arguments)

                    if tool_call.function.name in ["google_search", "bing_news_search"]:
                        web_search_count += 1
                        if "query" not in arguments or not arguments.get("query"):
                            arguments["query"] = message
                            operation.update_step(
                                f'Added missing query parameter to {tool_call.function.name}'
                            )

                    if tool_call.function.name in [
                        "get_stock_quote",
                        "get_company_overview",
                        "get_earnings",
                    ]:
                        param_key: str = "symbol"
                        if tool_call.function.name == "get_earnings":
                            param_key = "company_ticker"

                        if param_key not in arguments or not arguments[param_key]:
                            if symbols and len(symbols) > 0:
                                arguments[param_key] = symbols[0]
                                operation.update_step(
                                    f"Added missing {param_key} parameter ({symbols[0]}) to {tool_call.function.name}"
                                )

                    if (
                        tool_call.function.name == "check_market_hours_v2"
                        and ("dummy" not in arguments or not arguments.get("dummy"))
                    ):
                        arguments["dummy"] = "check"

                    if tool_call.function.name not in tools_dict:
                        raise ValueError(f"Unknown tool: {tool_call.function.name}")

                    operation.update_step(
                        f'Calling {tool_call.function.name} with arguments: {json.dumps(arguments)}'
                    )
                    result: Any = tools_dict[tool_call.function.name](**arguments)

                    tool_call_results.append(
                        {
                            "name": tool_call.function.name,
                            "arguments": arguments,
                            "result": str(result),
                            "tool_call_id": tool_call.id,
                        }
                    )

                    formatted_tool_results.append(
                        {"role": "tool", "tool_call_id": tool_call.id, "content": str(result)}
                    )

                except Exception as e:
                    error_msg: str = f"Error with {tool_call.function.name}: {str(e)}"
                    operation.update_step(error_msg)

                    tool_call_results.append(
                        {
                            "name": tool_call.function.name,
                            "arguments": arguments if "arguments" in locals() else {},
                            "error": error_msg,
                            "tool_call_id": tool_call.id,
                        }
                    )

                    formatted_tool_results.append(
                        {"role": "tool", "tool_call_id": tool_call.id, "content": error_msg}
                    )

            if needs_comprehensive_search and web_search_count < min_web_searches:
                operation.update_step(f'Enforcing minimum web searches ({web_search_count}/{min_web_searches})')
                
                additional_messages = formatted_tool_results.copy()
                additional_messages.append({
                    "role": "user",
                    "content": "Respond only with a search query in this exact format: <search>your search query here</search>"
                })

                try:
                    additional_completion = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=additional_messages,
                        temperature=self.model_config["temperature"],
                        top_p=self.model_config["top_p"],
                        max_tokens=self.model_config["max_tokens"],
                        tools=tools,
                        tool_choice="auto",
                    )

                    if additional_completion.choices and len(additional_completion.choices) > 0:
                        additional_message = additional_completion.choices[0].message
                        search_query = self._parse_search_query(additional_message.content)
                        
                        if search_query:
                            operation.update_step(f'Executing search query: {search_query}')
                            result = tools_dict["google_search"](query=search_query)
                            
                            tool_call_results.append({
                                "name": "google_search",
                                "arguments": {"query": search_query},
                                "result": str(result),
                                "tool_call_id": "forced_search",
                            })
                            
                            formatted_tool_results.append({
                                "role": "tool",
                                "tool_call_id": "forced_search",
                                "content": str(result)
                            })
                            
                            web_search_count += 1
                        else:
                            operation.update_step('No valid search query found in response')

                except Exception as e:
                    operation.update_step(f'Error requesting additional web searches: {str(e)}')

            final_messages: List[Dict[str, Any]] = [msg for msg in messages if msg.get("role") in ["system"]]

            final_messages.append(
                {"role": "assistant", "content": None, "tool_calls": response_message.tool_calls}
            )

            final_messages.extend(formatted_tool_results)

            final_messages.append(
                {
                    "role": "user",
                    "content": "Based on all the information gathered and analysis done, please provide your complete and comprehensive final response to my original question. This will be shown directly to me as your final answer.",
                }
            )

            operation.update_step("Sending tool results to AI for final analysis")

            try:
                final_completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=final_messages,
                    temperature=self.model_config["temperature"],
                    top_p=self.model_config["top_p"],
                    max_tokens=self.model_config["max_tokens"],
                )

                if not final_completion.choices or len(final_completion.choices) == 0:
                    operation.update_step("Retrying with simplified message structure")

                    simplified_messages: List[Dict[str, Any]] = [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"{user_message}\n\nTools have gathered the following information:\n\n"
                            + "\n\n".join(
                                [
                                    f"--- {r['name']} ---\n{r.get('result', r.get('error', 'No data'))}"
                                    for r in tool_call_results
                                ]
                            ),
                        },
                        {"role": "assistant", "content": "I've analyzed this data and am ready to respond."},
                        {
                            "role": "user",
                            "content": "Please provide your complete, final answer based on all the information you have gathered. Make sure it's comprehensive and directly addresses my original question.",
                        },
                    ]

                    retry_completion = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=simplified_messages,
                        temperature=self.model_config["temperature"] + 0.1,
                        top_p=self.model_config["top_p"],
                        max_tokens=self.model_config["max_tokens"],
                    )

                    if retry_completion.choices and len(retry_completion.choices) > 0:
                        final_response: str = retry_completion.choices[0].message.content or ""
                        final_text = self._clean_require_more_tools_tag(final_response)
                        final_text_with_disclaimer = self._append_disclaimer(final_text)
                        operation.complete(final_text_with_disclaimer)
                        return final_text_with_disclaimer

                    tool_summary: str = "Based on the data I gathered:\n\n"
                    for r in tool_call_results:
                        result_text: str = r.get("result", r.get("error", "No data"))
                        tool_summary += f"• {r['name']}: {result_text[:300]}...\n\n"

                    final_text_with_disclaimer = self._append_disclaimer(tool_summary)
                    operation.complete(final_text_with_disclaimer)
                    return final_text_with_disclaimer

                final_response = final_completion.choices[0].message.content or ""
                final_text = self._clean_require_more_tools_tag(final_response)

                final_text_with_disclaimer = self._append_disclaimer(final_text)
                operation.complete(final_text_with_disclaimer)
                return final_text_with_disclaimer

            except Exception as final_call_error:
                error_summary: str = f"Error generating final response: {str(final_call_error)}"
                operation.update_step(error_summary)

                tool_summary = "I retrieved the following information for you:\n\n"
                for r in tool_call_results:
                    result_text = r.get("result", r.get("error", "No data available"))
                    if len(result_text) > 300:
                        result_text = result_text[:300] + "..."
                    tool_summary += f"• {r['name']}: {result_text}\n\n"

                final_text_with_disclaimer = self._append_disclaimer(tool_summary)
                operation.complete(final_text_with_disclaimer)
                return final_text_with_disclaimer

        except Exception as e:
            error_message = f"I encountered an error while processing your request: {str(e)}. Please try again or rephrase your question."
            error_with_disclaimer = self._append_disclaimer(error_message)
            operation.fail(error_with_disclaimer)
            return error_with_disclaimer

    def _extract_potential_symbols(self, text: str) -> List[str]:
        """Extract potential stock symbols from text.

        Returns:
            List[str]: List of potential stock symbols.
        """
        symbol_pattern = r"\b[A-Z]{1,5}\b"

        potential_symbols = re.findall(symbol_pattern, text)

        common_words = {
            "I",
            "A",
            "AN",
            "THE",
            "AND",
            "OR",
            "IF",
            "IS",
            "IT",
            "BE",
            "TO",
            "IN",
            "ON",
            "AT",
            "BY",
        }
        filtered_symbols = [s for s in potential_symbols if s not in common_words]

        return filtered_symbols