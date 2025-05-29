import hmac
import hashlib
import logging
import os
import dotenv
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, Union, TypedDict
from flask import Flask, current_app
from services.oxapay.OxaPay import SyncOxaPay
from services.oxapay.utils.response_models import OrderStatus, PaymentStatus

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

OXAPAY_MERCHANT_API_KEY = os.getenv('OXAPAY_MERCHANT_API_KEY')
OXAPAY_SANDBOX = os.getenv('OXAPAY_SANDBOX', False)
if type(OXAPAY_SANDBOX) == str:
    OXAPAY_SANDBOX = OXAPAY_SANDBOX.lower() == 'true'
OXAPAY_CALLBACK_URL = os.getenv('OXAPAY_CALLBACK_URL')
OXAPAY_RETURN_URL = os.getenv('OXAPAY_RETURN_URL')
OXAPAY_INVOICE_LIFETIME = os.getenv('OXAPAY_INVOICE_LIFETIME', 30)

class CallbackData(TypedDict):
    track_id: str
    status: str
    valid: bool
    raw_data: Dict[str, Any]

@dataclass
class OxaPayResponse:
    success: bool
    message: str
    data: Dict[str, Any]

    def get_track_id(self) -> Optional[str]:
        """Get the track ID from the response data."""
        if not self.data:
            return None
        return str(self.data.get('trackId', '')) or str(self.data.get('id', ''))

    def get_payment_link(self) -> Optional[str]:
        """Get the payment link from the response data."""
        if not self.data:
            return None
        return str(self.data.get('payLink', '')) or str(self.data.get('link', ''))

    def is_payment_confirmed(self) -> bool:
        """Check if the payment is confirmed based on status."""
        if not self.data:
            return False
        status = str(self.data.get('status', '')).lower()
        return status in ['paid', 'completed', 'confirmed']

class OxaPayStatus:
    NEW         = "new"
    PENDING     = "pending"
    PAID        = "paid"
    COMPLETED   = "completed"
    EXPIRED     = "expired"
    CANCELLED   = "cancelled"
    ERROR       = "error"

class OxaPayAPI:
    def __init__(self, app: Optional[Flask] = None) -> None:
        """Initialize OxaPay API client."""
        self.app = app
        self._client: Optional[SyncOxaPay] = None

    @property
    def client(self) -> SyncOxaPay:
        """Lazy initialization of the OxaPay client."""
        if self._client is None:
            if self.app:
                self.app.config['OXAPAY_MERCHANT_API_KEY'] = OXAPAY_MERCHANT_API_KEY
                self.app.config['OXAPAY_SANDBOX'] = OXAPAY_SANDBOX
                self.app.config['OXAPAY_CALLBACK_URL'] = OXAPAY_CALLBACK_URL
                self.app.config['OXAPAY_RETURN_URL'] = OXAPAY_RETURN_URL
                self.app.config['OXAPAY_INVOICE_LIFETIME'] = OXAPAY_INVOICE_LIFETIME
                api_key = self.app.config.get('OXAPAY_MERCHANT_API_KEY')
                sandbox = self.app.config.get('OXAPAY_SANDBOX', True)
            else:
                current_app.config['OXAPAY_MERCHANT_API_KEY'] = OXAPAY_MERCHANT_API_KEY
                current_app.config['OXAPAY_SANDBOX'] = OXAPAY_SANDBOX
                current_app.config['OXAPAY_CALLBACK_URL'] = OXAPAY_CALLBACK_URL
                current_app.config['OXAPAY_RETURN_URL'] = OXAPAY_RETURN_URL
                current_app.config['OXAPAY_INVOICE_LIFETIME'] = OXAPAY_INVOICE_LIFETIME
                api_key = current_app.config.get('OXAPAY_MERCHANT_API_KEY')
                sandbox = current_app.config.get('OXAPAY_SANDBOX', True)
            
            if not api_key:
                raise RuntimeError("OXAPAY_MERCHANT_API_KEY not configured")
                
            self._client = SyncOxaPay(api_key, sandbox)
        return self._client

    def init_app(self, app: Flask) -> None:
        """Initialize the API with a Flask app."""
        self.app = app

    def create_payment(
        self,
        amount: float,
        currency: str = "BTC",
        callback_url: Optional[str] = None,
        email: Optional[str] = None,
        order_id: Optional[str] = None,
        description: Optional[str] = None,
        return_url: Optional[str] = None,
        life_time: int = 30
    ) -> OxaPayResponse:
        """Create a new payment invoice."""
        try:
            logger.error(f"Creating payment: amount={amount}, currency={currency}, order_id={order_id}")
            result = self.client.create_invoice(
                amount=amount,
                currency=currency,
                callbackUrl=callback_url,
                email=email,
                orderId=order_id,
                description=description,
                returnUrl=return_url,
                lifeTime=life_time,
                raw_response=True
            )
            
            logger.error(f"Raw OxaPay response: {result}")
            
            if isinstance(result, str):
                try:
                    import json
                    result = json.loads(result)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    return OxaPayResponse(success=False, message="Invalid JSON response", data={})
            
            if isinstance(result, dict):
                success = result.get('result') == 100
                message = result.get('message', 'Unknown error' if not success else 'Success')
                result['amount'] = amount
                logger.error(f"Payment creation result: success={success}, message={message}")
                return OxaPayResponse(success=success, message=message, data=result)
            elif isinstance(result, OrderStatus):
                success = result.result == 100
                message = result.message or ('Success' if success else 'Unknown error')
                data = {
                    'result': result.result,
                    'message': result.message,
                    'trackId': result.trackId,
                    'expiredAt': result.expiredAt,
                    'payLink': result.payLink,
                    'status': 'new',
                    'amount': amount
                }
                logger.error(f"Payment creation result: success={success}, message={message}")
                return OxaPayResponse(success=success, message=message, data=data)
            else:
                error_msg = f"Unexpected response type from OxaPay: {type(result)}"
                logger.error(error_msg)
                return OxaPayResponse(success=False, message=error_msg, data={})
            
        except Exception as e:
            error_msg = f"Error creating payment: {str(e)}"
            logger.error(error_msg)
            return OxaPayResponse(success=False, message=error_msg, data={})

    def check_payment_status(self, track_id: str) -> OxaPayResponse:
        """Check the status of a payment."""
        try:
            logger.error(f"Checking payment status for track_id: {track_id}")
            result = self.client.get_payment_information(track_id, raw_response=True)
            
            logger.error(f"Raw OxaPay status response: {result}")
            
            if isinstance(result, str):
                try:
                    import json
                    result = json.loads(result)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    return OxaPayResponse(success=False, message="Invalid JSON response", data={})
            
            if isinstance(result, dict):
                success = result.get('result') == 100
                message = result.get('message', 'Unknown error' if not success else 'Success')
                logger.error(f"Payment status result: success={success}, status={result.get('status')}")
                return OxaPayResponse(success=success, message=message, data=result)
            elif isinstance(result, PaymentStatus):
                success = result.result == 100
                message = result.message or ('Success' if success else 'Unknown error')
                data = {
                    'result': result.result,
                    'message': result.message,
                    'trackId': result.trackId,
                    'status': result.status,
                    'amount': result.amount,
                    'currency': result.currency,
                    'payAmount': result.payAmount,
                    'payCurrency': result.payCurrency,
                    'receivedAmount': result.receivedAmount,
                    'rate': result.rate,
                    'fee': result.feePaidByPayer,
                    'address': result.address,
                    'txID': result.txID,
                    'createdAt': result.createdAt,
                    'expiredAt': result.expiredAt,
                    'payDate': result.payDate
                }
                logger.error(f"Payment status result: success={success}, status={result.status}")
                return OxaPayResponse(success=success, message=message, data=data)
            else:
                error_msg = f"Unexpected response type from OxaPay: {type(result)}"
                logger.error(error_msg)
                return OxaPayResponse(success=False, message=error_msg, data={})
            
        except Exception as e:
            error_msg = f"Error checking payment status: {str(e)}"
            logger.error(error_msg)
            return OxaPayResponse(success=False, message=error_msg, data={})

class OxaPayFlaskIntegration:
    def __init__(self) -> None:
        """Initialize OxaPay Flask integration."""
        self.app: Optional[Flask] = None
        self.api: Optional[OxaPayAPI] = None

    def init_app(self, app: Flask) -> None:
        """Initialize the integration with a Flask app."""
        self.app = app
        self.api = OxaPayAPI(app)
        
        self.app.config['OXAPAY_MERCHANT_API_KEY']  = OXAPAY_MERCHANT_API_KEY
        self.app.config['OXAPAY_SANDBOX']           = OXAPAY_SANDBOX
        self.app.config['OXAPAY_CALLBACK_URL']      = OXAPAY_CALLBACK_URL
        self.app.config['OXAPAY_RETURN_URL']        = OXAPAY_RETURN_URL
        self.app.config['OXAPAY_INVOICE_LIFETIME']  = OXAPAY_INVOICE_LIFETIME

        if not app.config.get('OXAPAY_MERCHANT_API_KEY'):
            logger.warning("OXAPAY_MERCHANT_API_KEY not set in Flask config")

        if not app.config.get('OXAPAY_CALLBACK_URL'):
            logger.warning("OXAPAY_CALLBACK_URL not set in Flask config")

    def create_payment(
        self,
        amount: float,
        currency: str = "BTC",
        order_id: Optional[str] = None,
        description: Optional[str] = None,
        email: Optional[str] = None,
        return_url: Optional[str] = None,
        callback_url: Optional[str] = None
    ) -> OxaPayResponse:
        """Create a new payment invoice using configured settings."""
        if not self.api:
            raise RuntimeError("OxaPay integration not initialized. Call init_app first.")

        self.app.config['OXAPAY_MERCHANT_API_KEY'] = OXAPAY_MERCHANT_API_KEY
        self.app.config['OXAPAY_SANDBOX'] = OXAPAY_SANDBOX
        self.app.config['OXAPAY_CALLBACK_URL'] = OXAPAY_CALLBACK_URL
        self.app.config['OXAPAY_RETURN_URL'] = OXAPAY_RETURN_URL
        life_time = self.app.config.get('OXAPAY_INVOICE_LIFETIME', 30)
        
        return self.api.create_payment(
            amount=amount,
            currency=currency,
            callback_url=callback_url or self.app.config.get('OXAPAY_CALLBACK_URL'),
            email=email,
            order_id=order_id,
            description=description,
            return_url=return_url or self.app.config.get('OXAPAY_RETURN_URL'),
            life_time=life_time
        )

    def check_payment_status(self, track_id: str) -> OxaPayResponse:
        """Check the status of a payment."""
        if not self.api:
            raise RuntimeError("OxaPay integration not initialized. Call init_app first.")
            
        return self.api.check_payment_status(track_id)

    def verify_callback_signature(self, data: Dict[str, Any], signature: str) -> bool:
        """Verify the callback signature from OxaPay."""
        if not self.app:
            raise RuntimeError("OxaPay integration not initialized. Call init_app first.")
        
        self.app.config['OXAPAY_MERCHANT_API_KEY'] = OXAPAY_MERCHANT_API_KEY
        self.app.config['OXAPAY_SANDBOX'] = OXAPAY_SANDBOX
        self.app.config['OXAPAY_CALLBACK_URL'] = OXAPAY_CALLBACK_URL
        self.app.config['OXAPAY_RETURN_URL'] = OXAPAY_RETURN_URL
        api_key = self.app.config.get('OXAPAY_MERCHANT_API_KEY')
        if not api_key:
            logger.error("OXAPAY_MERCHANT_API_KEY not configured")
            return False

        try:
            sorted_data = dict(sorted(data.items()))
            payload = ''.join(str(v) for v in sorted_data.values())
            
            computed_signature = hmac.new(
                api_key.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(computed_signature, signature)
            
        except Exception as e:
            logger.error(f"Error verifying callback signature: {str(e)}")
            return False

    def handle_callback(self, data: Dict[str, Any]) -> tuple[bool, CallbackData]:
        """Handle callback notification from OxaPay."""
        if not data:
            logger.error("Empty callback data received")
            return False, CallbackData(track_id="", status="error", valid=False, raw_data={})

        track_id = str(data.get('trackId', ''))
        status = str(data.get('status', '')).lower()
        signature = str(data.get('sign', ''))

        if not track_id or not status or not signature:
            logger.error("Missing required callback fields")
            return False, CallbackData(track_id=track_id, status=status, valid=False, raw_data=data)

        is_valid = self.verify_callback_signature(data, signature)
        if not is_valid:
            logger.warning(f"Invalid callback signature for track_id: {track_id}")
            return False, CallbackData(track_id=track_id, status=status, valid=False, raw_data=data)

        is_confirmed = status in ['paid', 'completed', 'confirmed']
        logger.error(f"Valid callback received: track_id={track_id}, status={status}, confirmed={is_confirmed}")
        
        return is_confirmed, CallbackData(track_id=track_id, status=status, valid=True, raw_data=data)
