import hashlib
import hmac
import json
import logging
import os
import secrets
import stripe
import traceback
import uuid
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Optional, Tuple, Union

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from config import csrf, limiter
from extensions import db
from models import OxaPayTransaction, StripeTransaction, Subscription, User
from services.oxapay_service import OxaPayAPI, OxaPayFlaskIntegration, OxaPayStatus
from utils.ip import get_ip
from utils.eConfig import econfig

logger = logging.getLogger(__name__)

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")

oxapay = OxaPayFlaskIntegration()

processed_transactions: Dict[str, Tuple[datetime, Any]] = {}

stripe_mode = os.getenv("STRIPE_MODE", "live").lower()
if stripe_mode == "test":
    stripe.api_key = os.getenv("STRIPE_TEST_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_TEST_WEBHOOK_SECRET")
else:
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

STRIPE_LINKS = {
    "live": {
        "pro": os.getenv("STRIPE_PRO_LINK", "NONE"),
        "starter": os.getenv("STRIPE_STARTER_LINK", "NONE"),
        "portal": os.getenv("STRIPE_PORTAL_LINK", "NONE"),
    },
    "test": {
        "pro": os.getenv("STRIPE_TEST_PRO_LINK", "NONE"),
        "starter": os.getenv("STRIPE_TEST_STARTER_LINK", "NONE"),
        "portal": os.getenv("STRIPE_TEST_PORTAL_LINK", "NONE"),
    },
}

def _init_stripe_products():
    """Initialize STRIPE_PRODUCTS from eConfig configuration."""
    products = {
        "live": {},
        "test": {}
    }

    for mode in ["live", "test"]:
        plans = econfig.get_all_stripe_plans(mode)
        for plan_name, plan_config in plans.items():
            product_id = plan_config.get("product-id")
            if product_id:
                products[mode][plan_name] = product_id

    return products

STRIPE_PRODUCTS = _init_stripe_products()


def get_stripe_link(plan_type: str) -> str:
    """Get the appropriate Stripe payment link based on mode and plan type.

    Args:
        plan_type (str): The type of plan ('pro' or 'starter').

    Returns:
        str: The Stripe payment link.
    """
    return STRIPE_LINKS[stripe_mode][plan_type]


def get_stripe_product_id(plan_type: str) -> str:
    """Get the appropriate Stripe product ID based on mode and plan type.

    Args:
        plan_type (str): The type of plan ('pro' or 'starter').

    Returns:
        str: The Stripe product ID.
    """
    return STRIPE_PRODUCTS.get(stripe_mode, {}).get(plan_type, "N/A")


@payments_bp.app_template_filter("format_datetime")
def format_datetime(value: Optional[datetime]) -> str:
    """Format datetime object to a readable string.

    Args:
        value (Optional[datetime]): The datetime to format.

    Returns:
        str: Formatted datetime string.
    """
    if value is None:
        return ""
    return value.strftime("%b %d, %Y %H:%M")


@payments_bp.app_template_filter("transaction_type")
def transaction_type(transaction: Any) -> str:
    """Determine the type of transaction.

    Args:
        transaction (Any): The transaction object.

    Returns:
        str: Either 'oxapay' or 'stripe'.
    """
    if transaction.__class__.__name__ == "OxaPayTransaction":
        return "oxapay"
    elif transaction.__class__.__name__ == "StripeTransaction":
        return "stripe"
    return "unknown"


def validate_subscription(subscription_id: Union[str, int]) -> Optional[Subscription]:
    """Validate that a subscription ID exists and is eligible for purchase.

    Args:
        subscription_id (Union[str, int]): The ID to validate.

    Returns:
        Optional[Subscription]: Subscription object if valid, None otherwise.
    """
    try:
        subscription_id = int(subscription_id)
        subscription = Subscription.query.get(subscription_id)

        if not subscription:
            return None

        if subscription.price <= 0:
            return None

        return subscription
    except (ValueError, TypeError):
        return None


def validate_track_id(track_id: Optional[str]) -> bool:
    """Validate that a track ID is properly formatted.

    Args:
        track_id (Optional[str]): The track ID to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    if not track_id or not isinstance(track_id, str):
        return False

    if len(track_id) < 8 or len(track_id) > 64:
        return False

    return True


def verify_idempotent_request(f: callable) -> callable:
    """Decorator to ensure payment requests are not processed multiple times.

    Args:
        f (callable): The function to decorate.

    Returns:
        callable: The decorated function.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        request_hash = None

        if request.method in ["POST", "PUT", "PATCH"]:
            data = request.get_data()
            request_hash = hashlib.sha256(data).hexdigest()

            if request_hash in processed_transactions:
                timestamp, response = processed_transactions[request_hash]

                if datetime.utcnow() - timestamp < timedelta(minutes=10):
                    logger.warning(f"Duplicate payment request detected: {request_hash}")
                    return response

        response = f(*args, **kwargs)

        if request_hash:
            processed_transactions[request_hash] = (datetime.utcnow(), response)

            for hash_key in list(processed_transactions.keys()):
                if datetime.utcnow() - processed_transactions[hash_key][0] > timedelta(hours=1):
                    del processed_transactions[hash_key]

        return response

    return decorated_function


@payments_bp.record
def record_params(setup_state: Any) -> None:
    """Initialize the OxaPay integration with the Flask app.

    Args:
        setup_state (Any): Flask setup state.
    """
    app = setup_state.app

    # IMPORTANT: Set these in .env file for your domain
    # app.config.setdefault("SERVER_NAME", "yourdomain.com")
    app.config.setdefault("PREFERRED_URL_SCHEME", "https")

    app.config["OXAPAY_DEFAULT_CURRENCY"] = "BTC"
    app.config["OXAPAY_INVOICE_LIFETIME"] = 30

    # CRITICAL: Set these URLs in .env file with your actual domain
    app.config["OXAPAY_RETURN_URL"] = os.getenv("OXAPAY_RETURN_URL")
    app.config["OXAPAY_CALLBACK_URL"] = os.getenv("OXAPAY_CALLBACK_URL")

    if not app.config["OXAPAY_RETURN_URL"] or not app.config["OXAPAY_CALLBACK_URL"]:
        raise ValueError("OXAPAY_RETURN_URL and OXAPAY_CALLBACK_URL must be set in environment variables")

    oxapay.init_app(app)


@payments_bp.route("/checkout/<int:subscription_id>")
def checkout(subscription_id: int) -> Any:
    """Render checkout page for the specified subscription.

    Args:
        subscription_id (int): The ID of the subscription.

    Returns:
        Any: Rendered template or redirect.
    """
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to access this page.", "error")
        return redirect(url_for("auth.login"))

    user = db.session.query(User).filter_by(id=user_id).first()
    if not user:
        flash("User not found. Please log in again.", "error")
        return redirect(url_for("auth.login"))

    subscription = db.session.query(Subscription).filter_by(id=subscription_id).first()

    if not subscription:
        flash("Invalid subscription selected.", "error")
        return redirect(url_for("pricing"))

    is_admin = False
    if user.subscription_id:
        user_subscription = db.session.query(Subscription).filter_by(id=user.subscription_id).first()
        if user_subscription and user_subscription.name == "Admin":
            is_admin = True
            flash("You are already an admin. Please contact support to upgrade your subscription.", "info")
            return redirect(url_for("pricing"))

    if not is_admin and user.subscription_id:
        current_subscription = db.session.query(Subscription).filter_by(id=user.subscription_id).first()

        if current_subscription:
            if current_subscription.id == subscription.id:
                flash(f"You already have an active {current_subscription.name} subscription valid until {user.subscription_end_date.strftime('%Y-%m-%d')}.", "info")
                return redirect(url_for("pricing"))

            if current_subscription.price > subscription.price:
                flash(f"You already have the {current_subscription.name} plan which includes more features. Your subscription is valid until {user.subscription_end_date.strftime('%Y-%m-%d')}.", "info")
                return redirect(url_for("pricing"))

    stripe_link = None
    if subscription.name.lower() == "pro":
        stripe_link = get_stripe_link("pro")
    elif subscription.name.lower() == "starter":
        stripe_link = get_stripe_link("starter")

    return render_template(
        "payments/checkout.html", subscription=subscription, stripe_link=stripe_link
    )


@payments_bp.route("/checkout/success")
def checkout_success() -> Any:
    """Handle successful checkout session.

    Returns:
        Any: Rendered template or redirect.
    """
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect(url_for("pricing"))

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)

        user_id = session.get("user_id")
        if not user_id:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))

        user = db.session.query(User).filter_by(id=user_id).first()
        if not user:
            flash("User not found. Please log in again.", "error")
            return redirect(url_for("auth.login"))

        line_items = stripe.checkout.Session.list_line_items(session_id)
        product_id = None

        if line_items and line_items.data:
            price_id = line_items.data[0].price.id if line_items.data[0].price else None
            if price_id:
                price = stripe.Price.retrieve(price_id)
                product_id = price.product

        if not product_id:
            product_id = checkout_session.get("metadata", {}).get("product_id")

        subscription_type = None
        subscription = None

        stripe_mode = os.getenv("STRIPE_MODE", "live").lower()
        if product_id:
            if stripe_mode == "test":
                if product_id == get_stripe_product_id("pro"):
                    subscription_type = "pro"
                elif product_id == get_stripe_product_id("starter"):
                    subscription_type = "starter"
            else:
                if product_id == get_stripe_product_id("pro"):
                    subscription_type = "pro"
                elif product_id == get_stripe_product_id("starter"):
                    subscription_type = "starter"

        if subscription_type:
            subscription = (
                db.session.query(Subscription)
                .filter_by(name=subscription_type.capitalize())
                .first()
            )

        transaction = (
            db.session.query(StripeTransaction)
            .filter_by(transaction_id=session_id)
            .first()
        )

        customer_id = checkout_session.customer
        customer_email = (
            checkout_session.customer_details.email
            if checkout_session.customer_details
            else None
        )

        if customer_id and not user.stripe_customer_id:
            user.stripe_customer_id = customer_id
            db.session.commit()
            logger.info(f"Updated user {user.id} with Stripe customer ID: {customer_id}")

        if not transaction:
            transaction = StripeTransaction(
                user_id=user_id,
                transaction_id=session_id,
                amount=checkout_session.amount_total / 100,
                currency=checkout_session.currency,
                status=checkout_session.payment_status,
                customer_email=customer_email,
                customer_id=customer_id,
                stripe_subscription_id=checkout_session.subscription,
                product_id=product_id,
                subscription_id=subscription.id if subscription else None,
            )
            db.session.add(transaction)
            db.session.commit()
            logger.info(f"Created transaction record for session {session_id}")

        if checkout_session.payment_status == "paid":
            if subscription:
                duration_days = 30
                if hasattr(subscription, "duration") and subscription.duration:
                    duration_days = subscription.duration

                user.update_subscription(
                    subscription_id=subscription.id,
                    duration_days=duration_days,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=checkout_session.subscription,
                )
                db.session.commit()
                logger.info(f"Updated user {user.id} subscription to {subscription.name}")
                flash(f"Your {subscription.name} subscription has been activated!", "success")
            else:
                logger.error(f"Could not determine subscription for product_id {product_id}")
                flash(
                    "Payment successful, but we could not determine your subscription. Please contact support.",
                    "warning",
                )

        return render_template("payments/success.html", transaction=transaction)
    except Exception as e:
        logger.error(f"Error processing checkout: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f"Error processing checkout: {str(e)}", "error")
        return redirect(url_for("pricing"))


@payments_bp.route("/create-invoice", methods=["POST"])
@login_required
@limiter.limit("5/minute")
@verify_idempotent_request
def create_invoice() -> Any:
    """Create a payment invoice for a subscription using OxaPay.

    Returns:
        Any: JSON response with payment URL and tracking information.
    """
    subscription_id = request.form.get("subscription_id")

    if not subscription_id:
        return jsonify({"success": False, "message": "Subscription ID is required"}), 400

    subscription = validate_subscription(subscription_id)

    if not subscription:
        return jsonify({"success": False, "message": "Invalid subscription"}), 400

    is_admin = False
    if current_user.subscription_id:
        user_subscription = Subscription.query.get(current_user.subscription_id)
        if user_subscription and user_subscription.name == "Admin":
            is_admin = True

    if not is_admin and (
        current_user.subscription_id
        and current_user.subscription_end_date
        and current_user.subscription_end_date > datetime.utcnow()
    ):
        current_subscription = Subscription.query.get(current_user.subscription_id)
        if current_subscription and current_subscription.price >= subscription.price:
            return jsonify(
                {
                    "success": False,
                    "message": f"You already have an active {current_subscription.name} subscription valid until {current_user.subscription_end_date.strftime('%Y-%m-%d')}.",
                }
            ), 403

    if subscription.price <= 0:
        return jsonify({"success": False, "message": "Invalid subscription price"}), 400

    random_part = uuid.uuid4().hex[:12]
    timestamp = hex(int(datetime.utcnow().timestamp()))[2:]
    order_id = f"ORDER-{timestamp}-{random_part}-{current_user.id}"

    description = f"StockAssist {subscription.name} Subscription"

    try:
        existing_pending = OxaPayTransaction.query.filter(
            OxaPayTransaction.user_id == current_user.id,
            OxaPayTransaction.status == "pending",
            OxaPayTransaction.created_at > datetime.utcnow() - timedelta(minutes=30),
        ).first()

        if existing_pending:
            logger.info(
                f"User {current_user.id} has existing pending transaction {existing_pending.track_id}, reusing"
            )
            return jsonify(
                {
                    "success": True,
                    "payment_url": existing_pending.pay_link,
                    "track_id": existing_pending.track_id,
                    "message": "Redirecting to existing payment",
                }
            )

        result = oxapay.create_payment(
            amount=subscription.price,
            currency="USD",
            order_id=order_id,
            description=description,
            email=current_user.email,
            return_url=url_for("payments.payment_success", _external=True),
            callback_url=url_for("payments.payment_callback", _external=True),
        )

        logger.info(
            f"OxaPay API response: success={result.success}, trackId={result.get_track_id()}, payLink={result.get_payment_link() != None}"
        )

        track_id = result.get_track_id()
        payment_link = result.get_payment_link()

        if not track_id or not payment_link:
            logger.error(
                f"OxaPay response missing required fields: trackId={track_id}, payLink={payment_link}"
            )
            return (
                jsonify({"success": False, "message": "Invalid payment gateway response"}),
                500,
            )

        transaction = OxaPayTransaction.from_oxapay_response(
            result=result,
            user_id=current_user.id,
            order_id=order_id,
            description=description,
        )

        if not transaction:
            logger.error("Failed to create transaction record from response")
            return (
                jsonify({"success": False, "message": "Failed to create transaction record"}),
                500,
            )

        transaction.payment_data = transaction.payment_data or {}
        transaction.payment_data["subscription_id"] = subscription.id

        db.session.add(transaction)
        db.session.commit()

        logger.info(
            f"Created payment {transaction.track_id} for user {current_user.id}, subscription {subscription.id}"
        )
        return jsonify({"success": True, "payment_url": payment_link, "track_id": track_id})

    except Exception as e:
        logger.error(f"Error creating payment: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "message": "An unexpected error occurred"}), 500


@payments_bp.route("/success", methods=["GET"])
@limiter.limit("20/minute")
def payment_success() -> Any:
    """Handle successful payment redirect from OxaPay.

    Returns:
        Any: Rendered success template with payment status.
    """
    track_id = request.args.get("trackId")

    if not validate_track_id(track_id):
        flash("Invalid payment information", "error")
        return redirect(url_for("index"))

    transaction = OxaPayTransaction.query.filter_by(track_id=track_id).first()

    if not transaction:
        flash("Invalid payment information", "error")
        return redirect(url_for("index"))

    if current_user.is_authenticated and transaction.user_id and transaction.user_id != current_user.id:
        logger.warning(
            f"User {current_user.id} attempted to access payment {track_id} belonging to user {transaction.user_id}"
        )
        flash("You do not have permission to view this payment", "error")
        return redirect(url_for("index"))

    try:
        status_result = oxapay.check_payment_status(track_id)
        payment_status = OxaPayStatus.PENDING

        if status_result.success:
            payment_status = status_result.data.get("status", OxaPayStatus.PENDING)
            transaction.update_status(payment_status, status_result.data)

            if status_result.is_payment_confirmed() and transaction.user_id and not transaction.completed_at:
                user = User.query.get(transaction.user_id)

                subscription_id = None
                if transaction.payment_data and "subscription_id" in transaction.payment_data:
                    subscription_id = transaction.payment_data.get("subscription_id")
                    subscription = Subscription.query.get(subscription_id)
                else:
                    subscription = (
                        Subscription.query.filter_by(price=transaction.amount).first()
                    )

                if user and subscription:
                    if abs(float(transaction.amount) - float(subscription.price)) < 0.01:
                        user.update_subscription(subscription_id=subscription.id)
                        transaction.completed_at = datetime.utcnow()
                        db.session.commit()
                        flash(
                            f"Your {subscription.name} subscription has been activated!",
                            "success",
                        )
                    else:
                        logger.error(
                            f"Payment amount {transaction.amount} does not match subscription price {subscription.price}"
                        )
                        flash("Payment amount does not match subscription price", "error")

        return render_template(
            "payments/success.html",
            transaction=transaction,
            payment_status=payment_status,
        )

    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        flash("Error checking payment status", "error")
        return render_template(
            "payments/success.html",
            transaction=transaction,
            payment_status=OxaPayStatus.ERROR,
            error_message="Could not verify payment status",
        )


@payments_bp.route("/callback", methods=["POST"])
@verify_idempotent_request
def payment_callback() -> Any:
    """Handle callback notifications from OxaPay.

    Returns:
        Any: JSON response indicating whether the callback was processed successfully.
    """
    try:
        ip_address = get_ip()
        data = request.get_json()

        if not data:
            logger.error("Invalid OxaPay callback data received")
            return jsonify({"result": "error", "message": "Invalid request data"}), 400

        is_confirmed, callback_data = oxapay.handle_callback(data)

        if not callback_data["valid"]:
            logger.warning(
                f"Invalid OxaPay callback verification for track_id: {callback_data['track_id']}"
            )
            return (
                jsonify({"result": "error", "message": "Invalid callback verification"}),
                400,
            )

        transaction = OxaPayTransaction.query.filter_by(
            track_id=callback_data["track_id"]
        ).first()

        if not transaction:
            logger.warning(
                f"OxaPay callback received for unknown transaction: {callback_data['track_id']}"
            )
            return jsonify({"result": "error", "message": "Transaction not found"}), 404

        old_status = transaction.status
        transaction.update_status(str(callback_data["status"]), callback_data["raw_data"])

        newly_confirmed = (
            old_status not in ["confirmed", "completed"]
            and is_confirmed
            and transaction.user_id
            and not transaction.completed_at
        )

        if newly_confirmed:
            subscription_id = None
            if transaction.payment_data and "subscription_id" in transaction.payment_data:
                subscription_id = transaction.payment_data.get("subscription_id")
                subscription = Subscription.query.get(subscription_id)
            else:
                subscription = (
                    Subscription.query.filter_by(price=transaction.amount).first()
                )

            user = User.query.get(transaction.user_id)

            if user and subscription:
                if abs(float(transaction.amount) - float(subscription.price)) < 0.01:
                    user.update_subscription(subscription_id=subscription.id)
                    transaction.completed_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(
                        f"User {user.id} subscription updated to {subscription.name} after payment confirmation"
                    )
                else:
                    logger.error(
                        f"Payment amount {transaction.amount} does not match subscription price {subscription.price}"
                    )

        callback_hash = (
            f"{callback_data['track_id']}:{callback_data['status']}:{callback_data['raw_data'].get('timestamp', '')}"
        )
        processed_transactions[callback_hash] = (datetime.utcnow(), None)

        return jsonify({"result": "success"})

    except Exception as e:
        logger.error(f"Error processing OxaPay callback: {str(e)}")
        return (
            jsonify({"result": "error", "message": "Internal server error"}),
            500,
        )


@payments_bp.route("/transactions", methods=["GET"])
@login_required
@limiter.limit("20/minute")
def transactions() -> Any:
    """List all transactions for the current user.

    Returns:
        Any: Transactions list template.
    """
    page = request.args.get("page", 1, type=int)
    per_page = 10
    oxapay_transactions = (
        OxaPayTransaction.query.filter_by(user_id=current_user.id)
        .order_by(OxaPayTransaction.created_at.desc())
        .all()
    )
    stripe_transactions = (
        StripeTransaction.query.filter_by(user_id=current_user.id)
        .order_by(StripeTransaction.created_at.desc())
        .all()
    )

    all_transactions = oxapay_transactions + stripe_transactions
    all_transactions.sort(key=lambda x: x.created_at, reverse=True)

    total = len(all_transactions)
    start = (page - 1) * per_page
    end = min(start + per_page, total)

    class Pagination:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page

        @property
        def has_prev(self):
            return self.page > 1

        @property
        def has_next(self):
            return self.page < self.pages

        @property
        def prev_num(self):
            return self.page - 1 if self.has_prev else None

        @property
        def next_num(self):
            return self.page + 1 if self.has_next else None

        def iter_pages(self, left_edge=2, left_current=2, right_current=2, right_edge=2):
            pages_to_yield = set()

            pages_to_yield.update(range(1, min(left_edge + 1, self.pages + 1)))

            pages_to_yield.update(
                range(
                    max(1, self.page - left_current),
                    min(self.pages + 1, self.page + right_current + 1),
                )
            )

            pages_to_yield.update(
                range(max(1, self.pages - right_edge + 1), self.pages + 1)
            )

            last = 0
            for p in sorted(pages_to_yield):
                if p > last + 1:
                    yield None
                yield p
                last = p

    paginated_transactions = all_transactions[start:end]
    pagination = Pagination(paginated_transactions, page, per_page, total)

    return render_template(
        "payments/transactions.html",
        transactions=paginated_transactions,
        pagination=pagination,
        current_time=datetime.utcnow(),
    )


@payments_bp.route("/payment-status/<track_id>", methods=["GET"])
@limiter.limit("30/minute")
def payment_status(track_id: str) -> Any:
    """Check the status of a payment transaction.

    Args:
        track_id (str): The tracking ID of the payment.

    Returns:
        Any: JSON response with the current payment status.
    """
    if not validate_track_id(track_id):
        return (
            jsonify({"success": False, "message": "Invalid track ID format"}),
            400,
        )

    transaction = OxaPayTransaction.query.filter_by(track_id=track_id).first()

    if not transaction:
        return (
            jsonify({"success": False, "message": "Transaction not found"}),
            404,
        )

    if current_user.is_authenticated and transaction.user_id and transaction.user_id != current_user.id:
        logger.warning(
            f"User {current_user.id} attempted to check status of transaction {track_id} belonging to user {transaction.user_id}"
        )
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    if transaction.status == OxaPayTransaction.STATUS_CANCELLED:
        return jsonify(
            {
                "success": True,
                "status": transaction.status,
                "track_id": track_id,
                "created_at": transaction.created_at.isoformat(),
                "updated_at": transaction.updated_at.isoformat(),
                "order_id": transaction.order_id,
                "description": transaction.description,
                "amount": float(transaction.amount),
                "currency": transaction.currency,
            }
        )

    try:
        result = oxapay.check_payment_status(track_id)

        if not result.success:
            logger.warning(
                f"Failed to check payment status for track_id {track_id}: {result.message}"
            )
            return jsonify(
                {"success": True, "message": "Using cached payment status", "status": transaction.status}
            )

        oxapay_status = result.data.get("status", "").lower()
        logger.info(f"Payment {track_id} status from OxaPay: {oxapay_status}")

        internal_status = oxapay_status
        if oxapay_status == "paid":
            internal_status = "completed"
        elif oxapay_status in ["new", "waiting", "confirming"]:
            internal_status = "pending"

        logger.info(f"Mapping OxaPay status '{oxapay_status}' to internal status '{internal_status}'")
        transaction.update_status(internal_status, result.data)

        response = {
            "success": True,
            "status": transaction.status,
            "track_id": track_id,
            "created_at": transaction.created_at.isoformat(),
            "updated_at": transaction.updated_at.isoformat(),
            "order_id": transaction.order_id,
            "description": transaction.description,
            "amount": float(transaction.amount),
            "currency": transaction.currency,
        }

        if transaction.amount_paid is not None:
            response["amount_paid"] = float(transaction.amount_paid)

        if transaction.currency_paid:
            response["currency_paid"] = transaction.currency_paid

        if transaction.fee is not None:
            response["fee"] = float(transaction.fee)

        if transaction.payment_address:
            response["payment_address"] = transaction.payment_address

        if transaction.timestamp:
            response["timestamp"] = transaction.timestamp

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error checking payment status: {str(e)}")
        return (
            jsonify({"success": False, "message": "Error checking payment status"}),
            500,
        )


@payments_bp.route("/transaction/<transaction_id>", methods=["GET"])
@login_required
@limiter.limit("20/minute")
def transaction_details(transaction_id: str) -> Any:
    """Show details for a specific transaction.

    Args:
        transaction_id (str): ID of the transaction to view.

    Returns:
        Any: Transaction details template.
    """
    transaction = OxaPayTransaction.query.filter_by(
        id=transaction_id, user_id=current_user.id
    ).first()

    if not transaction:
        transaction = StripeTransaction.query.filter_by(
            id=transaction_id, user_id=current_user.id
        ).first()

    if not transaction:
        flash("Transaction not found", "error")
        return redirect(url_for("payments.transactions"))

    return render_template("payments/transaction_details.html", transaction=transaction)


@payments_bp.route("/cancel/<track_id>", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def cancel_payment(track_id: str) -> Any:
    """Cancel a pending payment transaction.

    Args:
        track_id (str): The tracking ID of the payment to cancel.

    Returns:
        Any: Response indicating success or failure.
    """
    if not validate_track_id(track_id):
        return jsonify({"success": False, "message": "Invalid track ID format"}), 400

    transaction = OxaPayTransaction.query.filter_by(track_id=track_id).first()

    if not transaction:
        return jsonify({"success": False, "message": "Transaction not found"}), 404

    if (
        current_user.is_authenticated
        and transaction.user_id
        and transaction.user_id != current_user.id
    ):
        logger.warning(
            f"User {current_user.id} attempted to cancel transaction {track_id} belonging to user {transaction.user_id}"
        )
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    if transaction.status != OxaPayTransaction.STATUS_PENDING:
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Cannot cancel transaction in {transaction.status} status",
                }
            ),
            400,
        )

    try:
        success = transaction.update_status(OxaPayTransaction.STATUS_CANCELLED)

        if not success:
            return (
                jsonify({"success": False, "message": "Failed to update transaction status"}),
                500,
            )

        logger.info(f"Transaction {track_id} cancelled by user {current_user.id}")

        return jsonify({"success": True, "message": "Transaction cancelled successfully"})

    except Exception as e:
        logger.error(f"Error cancelling payment: {str(e)}")
        return (
            jsonify({"success": False, "message": "An unexpected error occurred"}),
            500,
        )


@payments_bp.route("/webhook/stripe", methods=["POST"])
@csrf.exempt
def stripe_webhook() -> Any:
    """Handles Stripe webhook events to update transaction status."""
    payload: str = request.get_data(as_text=True)
    sig_header: str = request.headers.get("Stripe-Signature")

    stripe_webhook_secret: str = webhook_secret
    if not stripe_webhook_secret:
        return jsonify({"error": "Webhook secret not configured"}), 500

    try:
        event: stripe.Event = stripe.Webhook.construct_event(
            payload, sig_header, stripe_webhook_secret
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {str(e)}")
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {str(e)}")
        return jsonify({"error": "Invalid signature"}), 400

    event_data: dict = event.data.get("object", {})
    event_type: str = event.type

    logger.info(f"Received Stripe webhook event: {event_type}")

    try:
        if event_type == "checkout.session.completed":
            session_id: str = event_data.get("id")
            if not session_id:
                logger.error("Missing session ID in checkout.session.completed event")
                return jsonify({"error": "Missing session ID"}), 400

            customer_id: str = event_data.get("customer")
            user_id: int = None

            if customer_id:
                user: User = User.query.filter_by(stripe_customer_id=customer_id).first()
                if user:
                    user_id = user.id

            if not user_id:
                customer_email: str = event_data.get("customer_details", {}).get("email")
                if customer_email:
                    logger.info(
                        f"Customer ID lookup failed, trying email lookup: {customer_email}"
                    )
                    user: User = User.query.filter_by(email=customer_email).first()
                    if user:
                        user_id = user.id
                        if customer_id and not user.stripe_customer_id:
                            user.stripe_customer_id = customer_id
                            db.session.commit()
                            logger.info(
                                f"Updated user {user_id} with Stripe customer ID: {customer_id}"
                            )

            transaction: StripeTransaction = StripeTransaction.query.filter_by(
                transaction_id=session_id
            ).first()

            if not transaction:
                transaction: StripeTransaction = StripeTransaction.create_from_webhook(
                    event_data, user_id
                )
                if not transaction:
                    logger.error(f"Failed to create transaction from webhook: {session_id}")
                    return jsonify({"error": "Failed to create transaction"}), 500

            if "total_details" in event_data and "discount" in event_data["total_details"]:
                discount_data: dict = event_data["total_details"]["discount"]
                if discount_data and discount_data.get("amount", 0) > 0:
                    discount_amount: float = float(discount_data["amount"]) / 100
                    logger.info(
                        f"Coupon applied to transaction {session_id}: discount amount {discount_amount}"
                    )

            transaction.update_status(StripeTransaction.STATUS_COMPLETED)

            if "subscription" in event_data and event_data["subscription"]:
                transaction.stripe_subscription_id = event_data["subscription"]
                db.session.commit()
                logger.info(
                    f"Updated transaction {session_id} with subscription ID: {event_data['subscription']}"
                )

            if user_id and (not transaction.user_id or transaction.user_id != user_id):
                transaction.user_id = user_id
                db.session.commit()
                logger.info(f"Updated transaction {session_id} with user ID: {user_id}")

            if user_id and transaction.subscription_id:
                user: User = User.query.get(user_id)
                subscription: Subscription = Subscription.query.get(transaction.subscription_id)

                if user and subscription:
                    duration_days: int = 30
                    if hasattr(subscription, "duration") and subscription.duration:
                        duration_days = subscription.duration

                    user.update_subscription(
                        subscription_id=subscription.id,
                        duration_days=duration_days,
                        stripe_customer_id=customer_id,
                        stripe_subscription_id=transaction.stripe_subscription_id,
                    )
                    db.session.commit()
                    logger.info(
                        f"Updated user {user_id} subscription to {subscription.name} from webhook"
                    )

        elif event_type == "invoice.payment_succeeded":
            invoice: dict = event_data
            customer_id: str = invoice.get("customer")
            subscription_id: str = invoice.get("subscription")

            if not customer_id or not subscription_id:
                logger.error("Missing customer or subscription ID in invoice.payment_succeeded event")
                return jsonify({"error": "Missing required data"}), 400

            user: User = User.query.filter_by(stripe_customer_id=customer_id).first()
            if not user:
                logger.error(f"User not found for Stripe customer: {customer_id}")
                return jsonify({"status": "success"}), 200

            amount: float = float(invoice.get("amount_paid", 0)) / 100
            transaction_id: str = invoice.get("id")

            coupon_id: str = None
            discount_amount: float = None

            if "discount" in invoice:
                discount_data: dict = invoice["discount"]
                if discount_data:
                    coupon_id = discount_data.get("coupon", {}).get("id")

                    if "amount_off" in discount_data.get("coupon", {}):
                        discount_amount = float(discount_data["coupon"]["amount_off"]) / 100
                    elif "percent_off" in discount_data.get("coupon", {}):
                        percent_off: float = discount_data["coupon"]["percent_off"]
                        subtotal: float = float(invoice.get("subtotal", 0)) / 100
                        discount_amount = subtotal * (percent_off / 100)

            transaction: StripeTransaction = StripeTransaction(
                user_id=user.id,
                transaction_id=transaction_id,
                customer_id=customer_id,
                amount=amount,
                currency=invoice.get("currency", "usd"),
                status=StripeTransaction.STATUS_COMPLETED,
                description=f"Subscription payment for {subscription_id}",
                payment_data=invoice,
                completed_at=datetime.utcnow(),
                stripe_subscription_id=subscription_id,
                coupon_id=coupon_id,
                discount_amount=discount_amount,
            )

            db.session.add(transaction)

            user.update_subscription(
                subscription_id=user.subscription_id,
                duration_days=30,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
            )

            db.session.commit()
            logger.info(
                f"Processed subscription payment: invoice={transaction_id}, user={user.id}, amount={amount}, discount={discount_amount}"
            )

    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

    return jsonify({"status": "success"}), 200


@payments_bp.route("/stripe/success", methods=["GET"])
def stripe_success() -> Any:
    """Handle successful Stripe payments.

    This endpoint is used as the return URL after a successful Stripe payment.

    Returns:
        Template: Success page
    """
    session_id: str = request.args.get("session_id")
    if not session_id:
        logger.warning("No session ID provided in Stripe success callback")
        flash("Payment verification failed. Please contact support.", "error")
        return redirect(url_for("index"))

    try:
        session: stripe.checkout.Session = stripe.checkout.Session.retrieve(session_id)

        customer_email: str = session.get("customer_details", {}).get("email")
        customer_id: str = session.get("customer")
        user: User = None

        if customer_email and current_user.is_authenticated:
            if current_user.email.lower() == customer_email.lower():
                user = current_user
            else:
                logger.warning(f"Email mismatch: {current_user.email} vs {customer_email}")
        elif customer_email:
            user: User = User.query.filter_by(email=customer_email).first()

        if user:
            if customer_id and not user.stripe_customer_id:
                user.stripe_customer_id = customer_id
                db.session.commit()
                logger.info(f"Updated user {user.id} with Stripe customer ID: {customer_id}")

            transaction: StripeTransaction = StripeTransaction.query.filter_by(
                transaction_id=session_id
            ).first()

            if not transaction:
                transaction: StripeTransaction = StripeTransaction.create_from_webhook(
                    session, user_id=user.id
                )

            if transaction:
                transaction.update_status(StripeTransaction.STATUS_COMPLETED)

                if transaction.user_id != user.id:
                    transaction.user_id = user.id
                    db.session.commit()

                if transaction.subscription_id:
                    subscription: Subscription = Subscription.query.get(transaction.subscription_id)
                    if subscription:
                        duration_days: int = 30
                        if hasattr(subscription, "duration") and subscription.duration:
                            duration_days = subscription.duration

                        user.update_subscription(
                            subscription_id=subscription.id,
                            duration_days=duration_days,
                            stripe_customer_id=customer_id,
                            stripe_subscription_id=session.get("subscription"),
                        )
                        db.session.commit()
                        logger.info(
                            f"Updated user {user.id} subscription to {subscription.name} from success page"
                        )
                        flash(f"Your {subscription.name} subscription has been activated!", "success")

                return redirect(
                    url_for("payments.transaction_details", transaction_id=transaction.id)
                )

        logger.warning(f"Could not find or create user/transaction for Stripe session {session_id}")
        flash("Payment received, but we could not update your account. Please contact support.", "warning")
        return redirect(url_for("index"))

    except Exception as e:
        logger.error(f"Error processing Stripe success: {str(e)}")
        flash("An error occurred while verifying your payment. Please contact support.", "error")
        return redirect(url_for("index"))


@payments_bp.route("/customer-portal", methods=["GET"])
@login_required
def customer_portal() -> Any:
    """Redirect to Stripe customer portal."""
    return redirect(get_stripe_link("portal"))


@payments_bp.route("/subscription/status", methods=["GET"])
@login_required
@limiter.limit("30/minute")
def subscription_status() -> Any:
    """Get current user's subscription status.

    Returns:
        JSON: Subscription status details
    """
    try:
        status: dict = current_user.get_subscription_status()
        return jsonify({"success": True, "subscription": status})
    except Exception as e:
        logger.error(f"Error getting subscription status: {str(e)}")
        return (
            jsonify({"success": False, "message": "Error retrieving subscription status"}),
            500,
        )


@payments_bp.route("/subscription/toggle-auto-renew", methods=["POST"])
@login_required
@limiter.limit("5/minute")
def toggle_auto_renew() -> Any:
    """Toggle auto-renewal for the current user's subscription.

    Returns:
        JSON: Updated auto-renewal status
    """
    if not current_user.stripe_subscription_id:
        return jsonify({"success": False, "message": "No Stripe subscription found"}), 404

    try:
        current_user.subscription_auto_renew = not current_user.subscription_auto_renew
        db.session.commit()

        if not current_user.subscription_auto_renew:
            try:
                stripe.Subscription.modify(
                    current_user.stripe_subscription_id, cancel_at_period_end=True
                )
                logger.info(
                    f"Subscription {current_user.stripe_subscription_id} set to cancel at period end"
                )
            except Exception as e:
                logger.error(f"Error cancelling Stripe subscription: {str(e)}")
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Error updating subscription in Stripe",
                            "auto_renew": current_user.subscription_auto_renew,
                        }
                    ),
                    500,
                )
        else:
            try:
                stripe.Subscription.modify(
                    current_user.stripe_subscription_id, cancel_at_period_end=False
                )
                logger.info(f"Subscription {current_user.stripe_subscription_id} set to auto-renew")
            except Exception as e:
                logger.error(f"Error updating Stripe subscription: {str(e)}")
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Error updating subscription in Stripe",
                            "auto_renew": current_user.subscription_auto_renew,
                        }
                    ),
                    500,
                )

        return jsonify(
            {
                "success": True,
                "auto_renew": current_user.subscription_auto_renew,
                "message": f"Auto-renewal {'enabled' if current_user.subscription_auto_renew else 'disabled'}",
            }
        )

    except Exception as e:
        logger.error(f"Error toggling auto-renewal: {str(e)}")
        return (
            jsonify({"success": False, "message": "Error updating auto-renewal status"}),
            500,
        )