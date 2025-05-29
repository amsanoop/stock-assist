import io
import base64
import random
import secrets
import string
import logging
from datetime import datetime, timedelta
import os

import pyotp
import qrcode
from flask import request
from flask_login import UserMixin
from sqlalchemy import BLOB, Index, LargeBinary, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from utils.eConfig import econfig

logger = logging.getLogger(__name__)
class User(UserMixin, db.Model):
    __tablename__  = "user"
    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_subscription", "subscription_id"),
        Index("idx_user_next_reset", "next_reset"),
        Index("idx_user_daily_limits", "daily_message_count", "daily_image_count"),
        Index("idx_user_subscription_end", "subscription_end_date"),
        Index("idx_user_referral_code", "referral_code"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscription.id"))
    subscription_end_date = db.Column(db.DateTime, nullable=True)
    messages = db.relationship(
        "ChatMessage", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    chats = db.relationship(
        "Chat", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    operations = db.relationship(
        "AIOperation", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    watchlist = db.relationship(
        "StockWatchlist", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    oxapay_transactions = db.relationship(
        "OxaPayTransaction", backref="user", lazy=True
    )
    stripe_transactions = db.relationship(
        "StripeTransaction", backref="user", lazy=True
    )
    daily_message_count = db.Column(db.Integer, default=0)
    daily_image_count = db.Column(db.Integer, default=0)
    last_reset = db.Column(db.DateTime, default=datetime.utcnow)
    preferred_language = db.Column(db.String(10), default="en")
    next_reset = db.Column(
        db.DateTime, default=lambda: datetime.utcnow() + timedelta(days=1)
    )
    redeemed_keys = db.relationship(
        "RedemptionKey",
        backref="redeemed_by",
        lazy=True,
        foreign_keys="RedemptionKey.redeemed_by_id",
    )
    created_keys = db.relationship(
        "RedemptionKey",
        backref="created_by",
        lazy=True,
        foreign_keys="RedemptionKey.created_by_id",
    )
    referral_code = db.Column(db.String(10), unique=True, nullable=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    referral_count = db.Column(db.Integer, default=0, nullable=False)
    referral_level = db.Column(db.Integer, default=0, nullable=False)
    referral_rewards_claimed = db.Column(db.JSON, default=lambda: {}, nullable=False)
    referred_by = db.relationship(
        "User", remote_side=[id], backref=db.backref("referrals", lazy="dynamic")
    )
    sessions = db.relationship(
        "UserSession", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    two_factor_secret = db.Column(db.String(32), nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_backup_codes = db.Column(db.JSON, default=lambda: [], nullable=True)
    tos_agreed = db.Column(db.Boolean, default=False, nullable=False)
    tos_agreed_at = db.Column(db.DateTime, nullable=True)
    tos_version = db.Column(db.String(20), nullable=True)
    tos_ip_address = db.Column(db.String(45), nullable=True)
    tos_user_agent = db.Column(db.String(255), nullable=True)
    tos_digital_signature = db.Column(db.String(64), nullable=True)
    stripe_customer_id = db.Column(db.String(64), nullable=True)
    stripe_subscription_id = db.Column(db.String(64), nullable=True)
    subscription_auto_renew = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password: str) -> None:
        """Set user's password hash.

        Args:
            password (str): The password to hash
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the user's password hash.

        Args:
            password (str): The password to check

        Returns:
            bool: True if password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)

    def reset_daily_limits(self) -> None:
        """Reset user's daily message and image counts."""
        now = datetime.utcnow()
        self.daily_message_count = 0
        self.daily_image_count = 0
        self.last_reset = now
        self.next_reset = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    @classmethod
    def reset_all_daily_limits(cls) -> int:
        """Reset daily limits for all users whose next_reset time has passed.

        Returns:
            int: Number of users whose limits were reset
        """
        now = datetime.utcnow()
        users = cls.query.filter(cls.next_reset <= now).all()
        for user in users:
            user.reset_daily_limits()
        db.session.commit()
        return len(users)

    def should_reset_limits(self) -> bool:
        """Check if user's daily limits should be reset.

        Returns:
            bool: True if current time is past next_reset time
        """
        return datetime.utcnow() >= self.next_reset

    def update_subscription(self, subscription_id: int, duration_days: int = 30, stripe_customer_id: str = None, stripe_subscription_id: str = None) -> None:
        """Update user's subscription and set end date.

        Args:
            subscription_id (int): The ID of the new subscription
            duration_days (int): Duration of the subscription in days
            stripe_customer_id (str): Optional Stripe customer ID
            stripe_subscription_id (str): Optional Stripe subscription ID
        """
        self.subscription_id = subscription_id

        if (
            not self.subscription_end_date
            or self.subscription_end_date < datetime.utcnow()
        ):
            self.subscription_end_date = datetime.utcnow() + timedelta(
                days=duration_days
            )
        else:
            self.subscription_end_date = self.subscription_end_date + timedelta(
                days=duration_days
            )
            
        if stripe_customer_id:
            self.stripe_customer_id = stripe_customer_id
            
        if stripe_subscription_id:
            self.stripe_subscription_id = stripe_subscription_id
            self.subscription_auto_renew = True

        self.reset_daily_limits()

    def generate_referral_code(self) -> str:
        """Generate a unique referral code for the user.

        Returns:
            str: The generated referral code
        """
        if not self.referral_code:
            while True:
                code = "".join(
                    secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8)
                )
                if not User.query.filter_by(referral_code=code).first():
                    self.referral_code = code
                    try:
                        db.session.commit()
                    except Exception as e:
                        db.session.rollback()
                        print(f"Error generating referral code: {str(e)}")
                    break
        return self.referral_code

    def get_referral_url(self, base_url: str) -> str:
        """Get the user's referral URL.

        Args:
            base_url (str): The base URL of the application

        Returns:
            str: The complete referral URL
        """
        if not self.referral_code:
            self.generate_referral_code()
        return f"{base_url}/auth/r/{self.referral_code}"

    def add_referral(self) -> None:
        """Increment the user's referral count and update level if needed."""
        if self.referral_count is None:
            self.referral_count = 0

        self.referral_count += 1

        if self.referral_count >= 50:
            self.referral_level = 5
        elif self.referral_count >= 25:
            self.referral_level = 4
        elif self.referral_count >= 10:
            self.referral_level = 3
        elif self.referral_count >= 5:
            self.referral_level = 2
        elif self.referral_count >= 1:
            self.referral_level = 1

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Error updating referral count: {str(e)}")

    def can_claim_reward(self, level: int) -> bool:
        """Check if the user can claim a reward for a specific level.

        Args:
            level (int): The referral level to check

        Returns:
            bool: True if user can claim the reward, False otherwise
        """
        claimed_rewards = self.referral_rewards_claimed or {}
        user_level = self.referral_level or 0
        return user_level >= level and str(level) not in claimed_rewards

    def claim_reward(self, level: int) -> bool:
        """Claim a reward for a specific referral level.

        Args:
            level (int): The referral level to claim the reward for

        Returns:
            bool: True if reward was claimed successfully, False otherwise
        """
        if not self.can_claim_reward(level):
            return False

        claimed_rewards = self.referral_rewards_claimed or {}
        claimed_rewards[str(level)] = datetime.utcnow().isoformat()
        self.referral_rewards_claimed = claimed_rewards

        if level == 1:
            subscription = Subscription.query.get(self.subscription_id)
            if subscription:
                subscription.message_limit += 5
        elif level == 2:
            subscription = Subscription.query.get(self.subscription_id)
            if subscription:
                subscription.message_limit += 10
        elif level == 3:
            subscription = Subscription.query.get(self.subscription_id)
            if subscription:
                subscription.image_limit += 5
        elif level == 4:
            pro_subscription = Subscription.query.filter_by(name="Pro").first()
            if pro_subscription:
                self.update_subscription(pro_subscription.id, 7)
        elif level == 5:
            pro_subscription = Subscription.query.filter_by(name="Pro").first()
            if pro_subscription:
                self.update_subscription(pro_subscription.id, 30)

        db.session.commit()
        return True

    def generate_2fa_secret(self) -> str:
        """Generate a new 2FA secret for the user.

        Returns:
            str: The generated secret
        """
        self.two_factor_secret = pyotp.random_base32()
        db.session.commit()
        return self.two_factor_secret

    def get_2fa_uri(self) -> str:
        """Get the otpauth URI for the user's 2FA.

        Returns:
            str: The otpauth URI
        """
        if not self.two_factor_secret:
            return None

        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.provisioning_uri(name=self.email, issuer_name="StockAssist")

    def get_2fa_qr_code(self) -> str:
        """Generate a QR code for the 2FA setup.

        Returns:
            str: Base64 encoded QR code image
        """
        if not self.two_factor_secret:
            return None

        uri = self.get_2fa_uri()
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="white", back_color="transparent")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def verify_2fa_code(self, code: str) -> bool:
        """Verify a 2FA code.

        Args:
            code (str): The code to verify

        Returns:
            bool: Whether the code is valid
        """
        if not self.two_factor_secret or not self.two_factor_enabled:
            return True

        if self.two_factor_backup_codes and code in self.two_factor_backup_codes:
            self.two_factor_backup_codes.remove(code)
            db.session.commit()
            return True

        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(code)

    def generate_backup_codes(self, count: int = 8) -> list:
        """Generate backup codes for 2FA.

        Args:
            count (int): Number of backup codes to generate

        Returns:
            list: The generated backup codes
        """
        codes = []
        for _ in range(count):
            code = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )
            codes.append(code)

        self.two_factor_backup_codes = codes
        db.session.commit()
        return codes

    def enable_2fa(self) -> bool:
        """Enable 2FA for the user.

        Returns:
            bool: Whether 2FA was enabled
        """
        if not self.two_factor_secret:
            return False

        self.two_factor_enabled = True
        db.session.commit()
        return True

    def disable_2fa(self) -> bool:
        """Disable 2FA for the user.

        Returns:
            bool: Whether 2FA was disabled
        """
        self.two_factor_enabled = False
        self.two_factor_secret = None
        self.two_factor_backup_codes = []
        db.session.commit()
        return True

    @classmethod
    def create_user(cls, email: str, password: str, name: str) -> "User":
        """Create a new user with default Free subscription.

        Args:
            email (str): User's email
            password (str): User's password
            name (str): User's name

        Returns:
            User: The created user
        """
        free_plan = Subscription.query.filter_by(name="Free").first()
        if not free_plan:
            free_plan = Subscription(
                name="Free",
                price=0,
                message_limit=6,
                image_limit=0,
                features={
                    "multi_stock_chat": False,
                    "basic_stock_search": True,
                    "aggregated_data": True,
                }
            )
            db.session.add(free_plan)
            db.session.commit()

        user = cls(email=email, name=name, subscription_id=free_plan.id)
        user.set_password(password)
        return user

    def ensure_subscription(self) -> None:
        """Make sure user has a subscription. If not, assign free tier."""
        if not self.subscription_id:
            free_sub = Subscription.query.filter(Subscription.price == 0).first()
            if free_sub:
                self.subscription_id = free_sub.id
                db.session.commit()
                
    def is_subscription_active(self) -> bool:
        """Check if the user has an active subscription.
        
        Returns:
            bool: True if user has an active subscription
        """
        if not self.subscription_end_date:
            return False
            
        return self.subscription_end_date > datetime.utcnow()
    
    def is_subscription_auto_renewal(self) -> bool:
        """Check if the user's subscription will auto-renew.
        
        Returns:
            bool: True if subscription will auto-renew
        """
        return (
            self.subscription_auto_renew and 
            self.stripe_customer_id and 
            self.stripe_subscription_id
        )
        
    def get_subscription_status(self) -> dict:
        """Get comprehensive subscription status info.
        
        Returns:
            dict: Subscription status information
        """
        subscription = None
        if self.subscription_id:
            subscription = Subscription.query.get(self.subscription_id)
            
        return {
            "is_active": self.is_subscription_active(),
            "auto_renew": self.is_subscription_auto_renewal(),
            "end_date": self.subscription_end_date.isoformat() if self.subscription_end_date else None,
            "days_remaining": (self.subscription_end_date - datetime.utcnow()).days if self.subscription_end_date else 0,
            "plan": subscription.name if subscription else "None",
            "plan_id": self.subscription_id,
            "customer_id": self.stripe_customer_id,
            "subscription_id": self.stripe_subscription_id
        }


class ReferralReward(db.Model):
    __tablename__ = "referral_reward"

    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    required_referrals = db.Column(db.Integer, nullable=False)

    @classmethod
    def init_rewards(cls) -> None:
        """Initialize the default referral rewards if they don't exist."""
        if not cls.query.first():
            rewards = [
                cls(level=1, description="+5 daily messages", required_referrals=1),
                cls(level=2, description="+10 daily messages", required_referrals=5),
                cls(level=3, description="+5 image generation", required_referrals=10),
                cls(
                    level=4,
                    description="7 days of Pro subscription",
                    required_referrals=25,
                ),
                cls(
                    level=5,
                    description="30 days of Pro subscription",
                    required_referrals=50,
                ),
            ]
            db.session.add_all(rewards)
            db.session.commit()


class Subscription(db.Model):
    __tablename__ = "subscription"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
    message_limit = db.Column(db.Integer, nullable=False)
    image_limit = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.Text)
    features = db.Column(db.JSON)

    users = db.relationship("User", backref=db.backref("subscription", lazy=True))
    redemption_keys = db.relationship(
        "RedemptionKey", backref="subscription", lazy=True
    )


class RedemptionKey(db.Model):
    __tablename__  = "redemption_key"
    __table_args__ = (
        Index("idx_redemption_key", "key"),
        Index("idx_redemption_status", "is_redeemed"),
    )

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    subscription_id = db.Column(
        db.Integer, db.ForeignKey("subscription.id"), nullable=False
    )
    duration_days = db.Column(db.Integer, default=30, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_redeemed = db.Column(db.Boolean, default=False)
    redeemed_at = db.Column(db.DateTime, nullable=True)
    redeemed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    @classmethod
    def generate_key(cls, length: int = 16) -> str:
        """Generate a random redemption key.

        Args:
            length (int): Length of the key in bytes

        Returns:
            str: A random key string
        """
        return secrets.token_hex(length)

    @classmethod
    def create_key(
        cls,
        subscription_id: int,
        duration_days: int = 30,
        expires_at: datetime = None,
        created_by_id: int = None,
    ) -> "RedemptionKey":
        """Create a new redemption key.

        Args:
            subscription_id (int): The subscription ID this key will redeem
            duration_days (int): Duration of the subscription in days
            expires_at (datetime): When the key expires if not redeemed
            created_by_id (int): User ID who created this key

        Returns:
            RedemptionKey: The newly created key
        """
        key = cls.generate_key()

        if expires_at is None:
            expires_at = datetime.utcnow() + timedelta(days=90)

        redemption_key = cls(
            key=key,
            subscription_id=subscription_id,
            duration_days=duration_days,
            expires_at=expires_at,
            created_by_id=created_by_id,
        )

        db.session.add(redemption_key)
        db.session.commit()

        return redemption_key

    def redeem(self, user_id: int) -> bool:
        """Redeem this key for a user.

        Args:
            user_id (int): The ID of the user redeeming the key

        Returns:
            bool: True if redemption was successful, False otherwise
        """
        if self.is_redeemed:
            return False

        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False

        self.is_redeemed = True
        self.redeemed_at = datetime.utcnow()
        self.redeemed_by_id = user_id

        user = User.query.get(user_id)
        if user:
            user.update_subscription(self.subscription_id, self.duration_days)

        db.session.commit()
        return True


class Chat(db.Model):
    __tablename__ = "chat"
    __table_args__ = (
        Index("idx_chat_user_updated", "user_id", "updated_at"),
        Index("idx_chat_created", "created_at"),
        Index("idx_chat_user_created", "user_id", "created_at"),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages = db.relationship(
        "ChatMessage",
        backref="chat",
        lazy=True,
        order_by="ChatMessage.created_at",
        cascade="all, delete-orphan",
    )
    operations = db.relationship(
        "AIOperation", backref="chat", lazy=True, cascade="all, delete-orphan"
    )


class ChatMessage(db.Model):
    __tablename__ = "chat_message"
    __table_args__ = (
        Index("idx_chat_message_chat", "chat_id"),
        Index("idx_chat_message_user", "user_id"),
        Index("idx_chat_message_created", "created_at"),
        Index("idx_chat_message_chat_created", "chat_id", "created_at"),
        Index("idx_chat_message_user_created", "user_id", "created_at"),
        Index("idx_chat_message_is_user", "is_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chat.id", ondelete="CASCADE"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"))
    content = db.Column(db.Text, nullable=False)
    stock_symbols = db.Column(db.JSON)
    is_user = db.Column(db.Boolean, default=True)
    has_image = db.Column(db.Boolean, default=False)
    has_ephemeral_image = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    images = db.relationship(
        "ChatImage", back_populates="message", cascade="all, delete-orphan"
    )


class ChatImage(db.Model):
    __tablename__ = "chat_image"
    __table_args__ = (
        Index("idx_chat_image_message", "message_id"),
        Index("idx_chat_image_created", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(
        db.Integer, db.ForeignKey("chat_message.id", ondelete="CASCADE")
    )
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    compressed_data = db.Column(db.LargeBinary(length=(2**32)-1), nullable=False)
    mime_type = db.Column(db.String(127), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    message = db.relationship("ChatMessage", back_populates="images")

    def to_dict(self) -> dict:
        """Convert ChatImage to a dictionary.

        Returns:
            dict: Dictionary representation of ChatImage
        """
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "created_at": self.created_at.isoformat(),
            "data_url": f"/api/chat/image/{self.id}",
        }


class StockWatchlist(db.Model):
    __tablename__  = "stock_watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="unique_user_stock"),
        Index("idx_watchlist_user", "user_id"),
        Index("idx_watchlist_symbol", "symbol"),
        Index("idx_watchlist_added", "added_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    symbol = db.Column(db.String(30), nullable=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)


class News(db.Model):
    __tablename__ = "news"
    __table_args__ = (
        Index("idx_news_published", "published_at"),
        Index("idx_news_created", "created_at"),
        Index("idx_news_paid", "is_paid_content"),
        Index("idx_news_urgency", "urgency"),
        Index("idx_news_source_link", "source_link", unique=True),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(100), nullable=False)
    source_link = db.Column(db.String(500), nullable=False, unique=True)
    published_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    symbols = db.Column(db.JSON)
    summary = db.Column(db.Text)
    paid_summary = db.Column(db.Text)
    is_paid_content = db.Column(db.Boolean, default=False)
    urgency = db.Column(db.Integer)
    provider = db.Column(db.String(100))


class AIOperation(db.Model):
    __tablename__ = "ai_operation"
    __table_args__ = (
        Index("idx_operation_user_status", "user_id", "status"),
        Index("idx_operation_chat", "chat_id"),
        Index("idx_operation_created", "created_at"),
        Index("idx_operation_updated", "updated_at"),
        Index("idx_operation_status", "status"),
        Index("idx_operation_message", "message_id"),
    )
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    chat_id = db.Column(db.Integer, db.ForeignKey("chat.id", ondelete="CASCADE"), nullable=True)
    message_id = db.Column(
        db.Integer, db.ForeignKey("chat_message.id", ondelete="SET NULL"), nullable=True
    )
    status = db.Column(db.String(50), default="pending")
    current_step = db.Column(db.String(200))
    result = db.Column(db.Text)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    message = db.Column(db.Text)
    symbols = db.Column(db.JSON)
    steps = db.Column(db.JSON, default=lambda: [])
    image_data = db.Column(db.JSON, nullable=True)
    ephemeral_images = db.Column(db.JSON, nullable=True)

    def update_step(self, step_description: str) -> None:
        """Update current step and add to steps history.

        Args:
            step_description (str): Description of the current step
        """
        if step_description and len(step_description) > 190:
            truncated_step = step_description[:187] + "..."
        else:
            truncated_step = step_description

        self.current_step = truncated_step
        if not self.steps:
            self.steps = []
        self.steps.append(
            {"description": step_description, "timestamp": datetime.utcnow().isoformat()}
        )
        db.session.commit()

    def complete(self, result: str) -> None:
        """Mark operation as completed with result.

        Args:
            result (str): The result of the operation
        """
        self.status = "completed"
        self.result = result
        self.current_step = "Completed"
        db.session.commit()

    def fail(self, error: str) -> None:
        """Mark operation as failed with error.

        Args:
            error (str): The error message
        """
        self.status = "failed"
        self.error = str(error)
        self.current_step = "Failed"
        db.session.commit()


class UserSession(db.Model):
    __tablename__ = "user_session"
    __table_args__ = (
        Index("idx_session_user", "user_id"),
        Index("idx_session_token", "session_token"),
        Index("idx_session_expires", "expires_at"),
        Index("idx_session_active", "is_active"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    session_token = db.Column(db.String(64), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    device_info = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    @staticmethod
    def get_device_info(user_agent_string: str) -> str:
        """Get device info from user agent string.

        Args:
            user_agent_string (str): The user agent string to parse

        Returns:
            str: Device type identifier
        """
        if not user_agent_string:
            return "Unknown"

        user_agent_lower = user_agent_string.lower()

        if "iphone" in user_agent_lower:  return "iPhone"
        if "ipad" in user_agent_lower:    return "iPad"
        if "android" in user_agent_lower: return "Android"
        if "windows" in user_agent_lower: return "Windows"
        if "macintosh" in user_agent_lower or "mac os" in user_agent_lower: return "Mac"
        if "linux" in user_agent_lower:   return "Linux"
        return "Other"

    @classmethod
    def create_session(cls, user_id: int, remember: bool = False, request=None) -> "UserSession":
        """Create a new user session.

        Args:
            user_id (int): ID of the user
            remember (bool): Whether to extend session duration
            request: The Flask request object

        Returns:
            UserSession: The created session
        """
        token = secrets.token_hex(32)

        ip = None
        user_agent_string = None
        device_info = "Unknown"

        if request:
            from utils.ip import get_ip
            ip = get_ip()
            user_agent_string = request.headers.get("User-Agent")
            device_info = cls.get_device_info(user_agent_string)

        expires_at = datetime.utcnow() + timedelta(days=30 if remember else 1)

        session = cls(
            user_id=user_id,
            session_token=token,
            ip_address=ip,
            user_agent=user_agent_string,
            device_info=device_info,
            expires_at=expires_at,
        )

        db.session.add(session)
        db.session.commit()

        return session

    def update_activity(self) -> None:
        """Update the last activity time for this session."""
        self.last_active = datetime.utcnow()
        db.session.commit()

    def terminate(self) -> None:
        """Terminate this session."""
        self.is_active = False
        db.session.commit()

    @classmethod
    def get_by_token(cls, token: str) -> "UserSession":
        """Get an active session by token.

        Args:
            token (str): The session token

        Returns:
            UserSession: The session if found and active
        """
        return cls.query.filter_by(session_token=token, is_active=True).first()

    @classmethod
    def cleanup_expired_sessions(cls) -> int:
        """Clean up expired sessions.

        Returns:
            int: Number of sessions cleaned up
        """
        now = datetime.utcnow()
        expired_sessions = cls.query.filter(cls.expires_at < now, cls.is_active == True).all()
        
        for session in expired_sessions:
            session.is_active = False
        
        db.session.commit()
        return len(expired_sessions)


class OxaPayTransaction(db.Model):
    """
    Model to store OxaPay transaction information.
    """
    __tablename__  = "oxapay_transaction"
    __table_args__ = (
        Index("idx_oxapay_track_id", "track_id"),
        Index("idx_oxapay_user",     "user_id"),
        Index("idx_oxapay_order",    "order_id"),
        Index("idx_oxapay_status",   "status"),
        Index("idx_oxapay_created",  "created_at"),
    )
    
    STATUS_PENDING   = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_PAID      = "paid"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED    = "failed"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    track_id = db.Column(db.String(64), unique=True, nullable=False)
    pay_link = db.Column(db.String(255), nullable=False)
    order_id = db.Column(db.String(64), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    payment_data = db.Column(db.JSON, nullable=True)
    
    amount_paid = db.Column(db.Float, nullable=True)
    fee = db.Column(db.Float, nullable=True)
    currency_paid = db.Column(db.String(10), nullable=True)
    payment_address = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.String(64), nullable=True)
    
    @property
    def subscription_name(self) -> str:
        """
        Get the subscription name associated with this transaction.
        
        Returns:
            str: The subscription name or a generic label if not found
        """
        subscription_id = None
        if self.payment_data and isinstance(self.payment_data, dict):
            subscription_id = self.payment_data.get('subscription_id')
        
        if subscription_id is not None:
            try:
                from extensions import db
                from sqlalchemy import text
                
                result = db.session.execute(
                    text("SELECT name FROM subscription WHERE id = :id"),
                    {"id": subscription_id}
                ).fetchone()
                
                if result and result[0]:
                    return result[0]
            except Exception:
                pass

        if self.amount:
            return f"Payment (${self.amount:.2f})"
        return "Payment"
    
    def update_status(self, status: str, payment_data: dict = None) -> bool:
        """
        Update the transaction status.
        
        Args:
            status: New status value
            payment_data: Optional payment data to store
            
        Returns:
            Boolean indicating success
        """
        if status not in [self.STATUS_PENDING, self.STATUS_COMPLETED, self.STATUS_PAID, 
                         self.STATUS_CANCELLED, self.STATUS_FAILED]:
            logger.warning(f"Invalid status update attempt: {status}")
            return False
            
        if self.status in [self.STATUS_COMPLETED, self.STATUS_CANCELLED] and status != self.status:
            logger.warning(f"Attempted to change status of {self.status} transaction to {status}")
            return False
            
        self.status = status
        
        if payment_data:
            self.payment_data = payment_data
            
            if 'amountPaid' in payment_data:
                try:
                    self.amount_paid = float(payment_data['amountPaid'])
                except (ValueError, TypeError):
                    pass
                
            if 'fee' in payment_data:
                try:
                    self.fee = float(payment_data['fee'])
                except (ValueError, TypeError):
                    pass
                
            if 'currencyPaid' in payment_data:
                self.currency_paid = payment_data['currencyPaid']
                
            if 'address' in payment_data:
                self.payment_address = payment_data['address']
                
            if 'timestamp' in payment_data:
                self.timestamp = payment_data['timestamp']
        
        if status in ['completed', 'paid']:
            self.completed_at = datetime.utcnow()
        
        self.updated_at = datetime.utcnow()
        db.session.commit()
        return True
    
    @classmethod
    def from_oxapay_response(cls, result, user_id=None, order_id=None, description=None):
        """
        Create a new transaction from an OxaPay API response.
        
        Args:
            result: OxaPayResponse object from the API
            user_id: Optional user ID to associate with transaction
            order_id: Optional order ID for the transaction
            description: Optional description for the transaction
            
        Returns:
            OxaPayTransaction: New transaction instance
        """
        track_id = result.get_track_id()
        pay_link = result.get_payment_link()
        
        if not track_id or not pay_link:
            logger.error(f"Missing required fields in OxaPay response: trackId={track_id}, payLink={pay_link}, data={result.data}")
            return None
            
        amount = None
        try:
            amount = float(result.data.get('amount', 0))
            
            if not amount:
                if 'payAmount' in result.data:
                    amount = float(result.data['payAmount'])
                elif 'receivedAmount' in result.data:
                    amount = float(result.data['receivedAmount'])

            if not amount:
                logger.warning(f"Could not find amount in OxaPay response data: {result.data}")
                
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing amount from OxaPay response: {e}, data={result.data}")
            amount = 0
        
        transaction = cls(
            user_id=user_id,
            track_id=track_id,
            pay_link=pay_link,
            order_id=order_id,
            amount=amount,
            currency=result.data.get('currency', 'BTC'),
            status=result.data.get('status', 'pending'),
            description=description,
            payment_data=result.data
        )
        
        logger.info(f"Created transaction record: track_id={track_id}, amount={amount}, status={transaction.status}")
        return transaction


class StripeTransaction(db.Model):
    """
    Model to store Stripe transaction information.
    """
    __tablename__  = "stripe_transaction"
    __table_args__ = (
        Index("idx_stripe_transaction_id", "transaction_id"),
        Index("idx_stripe_user", "user_id"),
        Index("idx_stripe_customer", "customer_id"),
        Index("idx_stripe_status", "status"),
        Index("idx_stripe_created", "created_at"),
        Index("idx_stripe_email", "customer_email"),
    )
    
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True)
    transaction_id = db.Column(db.String(128), unique=True, nullable=False)
    customer_id = db.Column(db.String(128), nullable=True)
    customer_email = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="usd", nullable=False)
    status = db.Column(db.String(20), default=STATUS_PENDING, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    payment_data = db.Column(db.JSON, nullable=True)
    product_id = db.Column(db.String(128), nullable=True)
    price_id = db.Column(db.String(128), nullable=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey("subscription.id"), nullable=True)
    stripe_subscription_id = db.Column(db.String(128), nullable=True)
    coupon_id = db.Column(db.String(128), nullable=True)
    discount_amount = db.Column(db.Float, nullable=True)
    
    @property
    def subscription_name(self) -> str:
        """
        Get the subscription name associated with this transaction.
        
        Returns:
            str: The subscription name or a generic label if not found
        """
        if self.subscription_id is not None:
            try:
                from extensions import db
                from sqlalchemy import text
                
                result = db.session.execute(
                    text("SELECT name FROM subscription WHERE id = :id"),
                    {"id": self.subscription_id}
                ).fetchone()
                
                if result and result[0]:
                    return result[0]
            except Exception:
                pass

        if self.amount:
            return f"Payment (${self.amount:.2f})"
        return "Payment"
    
    def update_status(self, status: str, payment_data: dict = None) -> bool:
        """
        Update the transaction status.
        
        Args:
            status: New status value
            payment_data: Optional payment data to store
            
        Returns:
            Boolean indicating success
        """
        if status not in [self.STATUS_PENDING, self.STATUS_COMPLETED, self.STATUS_FAILED, self.STATUS_REFUNDED]:
            logger.warning(f"Invalid status update attempt: {status}")
            return False
            
        self.status = status
        
        if payment_data:
            self.payment_data = payment_data
            
            if 'customer_id' in payment_data:
                self.customer_id = payment_data['customer_id']
        
        if status == self.STATUS_COMPLETED:
            self.completed_at = datetime.utcnow()
            
            if self.user_id and self.subscription_id:
                user = User.query.get(self.user_id)
                if user:
                    stripe_customer_id = self.customer_id
                    stripe_subscription_id = self.stripe_subscription_id
                    
                    user.update_subscription(
                        self.subscription_id, 
                        30, 
                        stripe_customer_id, 
                        stripe_subscription_id
                    )
        
        self.updated_at = datetime.utcnow()
        db.session.commit()
        return True
    
    @classmethod
    def create_from_webhook(cls, event_data, user_id=None):
        """
        Create a new transaction from a Stripe webhook event.
        
        Args:
            event_data: Stripe event data
            user_id: Optional user ID to associate with the transaction
            
        Returns:
            StripeTransaction: New transaction instance or None on failure
        """
        try:
            if not isinstance(event_data, dict) and hasattr(event_data, 'to_dict'):
                event_data = event_data.to_dict()
                
            if event_data.get('object') != 'checkout.session':
                return None
                
            transaction_id = event_data.get('id')
            customer_id = event_data.get('customer')
            
            if not transaction_id:
                logger.error(f"Missing transaction ID in Stripe webhook data: {event_data}")
                return None
                
            existing = cls.query.filter_by(transaction_id=transaction_id).first()
            if existing:
                return existing
                
            amount = 0
            if 'amount_total' in event_data:
                amount = float(event_data['amount_total']) / 100
            
            coupon_id = None
            discount_amount = None
            
            if 'total_details' in event_data and 'discount' in event_data['total_details']:
                discount_data = event_data['total_details']['discount']
                if discount_data and discount_data.get('amount', 0) > 0:
                    discount_amount = float(discount_data['amount']) / 100
            
            if 'payment_intent' in event_data and event_data['payment_intent']:
                payment_intent_data = event_data.get('payment_intent_data', {})
                if payment_intent_data.get('metadata', {}).get('coupon'):
                    coupon_id = payment_intent_data['metadata']['coupon']
            
            subscription_id = None
            product_id = event_data.get('metadata', {}).get('product_id')
            
            if not product_id and transaction_id:
                try:
                    import stripe
                    line_items = stripe.checkout.Session.list_line_items(transaction_id)
                    
                    if line_items and line_items.data:
                        price_id = line_items.data[0].price.id if line_items.data[0].price else None
                        if price_id:
                            price = stripe.Price.retrieve(price_id)
                            product_id = price.product
                            
                            logger.info(f"Retrieved product_id {product_id} from line items for session {transaction_id}")
                except Exception as e:
                    logger.error(f"Error retrieving line items: {str(e)}")
            
            stripe_mode = os.getenv('STRIPE_MODE', 'live').lower()
            if product_id:
                db_name = econfig.get_db_name_by_product_id(product_id, stripe_mode)
                if db_name:
                    subscription = Subscription.query.filter_by(name=db_name).first()
                    if subscription:
                        subscription_id = subscription.id
                        logger.info(f"Identified {db_name} subscription from product ID {product_id}")
                else:
                    logger.warning(f"Unknown product ID {product_id} for mode {stripe_mode}")
            
            transaction = cls(
                user_id=user_id,
                transaction_id=transaction_id,
                customer_id=customer_id,
                amount=amount,
                currency=event_data.get('currency', 'usd'),
                status=cls.STATUS_PENDING,
                product_id=product_id,
                price_id=event_data.get('metadata', {}).get('price_id'),
                payment_data=event_data,
                subscription_id=subscription_id,
                stripe_subscription_id=event_data.get('metadata', {}).get('subscription_id') or event_data.get('subscription'),
                coupon_id=coupon_id,
                discount_amount=discount_amount,
                customer_email=event_data.get('customer_details', {}).get('email')
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            logger.info(f"Created Stripe transaction: id={transaction_id}, amount={amount}, discount={discount_amount}, product={product_id}, subscription={subscription_id}")
            return transaction
            
        except Exception as e:
            logger.error(f"Error creating Stripe transaction: {str(e)}")
            db.session.rollback()
            return None


def init_db(app) -> None:
    """Initialize the database with default data.
    
    Args:
        app: The Flask application
    """
    with app.app_context():
        db.create_all()
        
        print("Checking for existing subscriptions...")
        if not Subscription.query.first():
            print("Creating default subscription plans...")
            free_plan = Subscription(
                name="Free",
                price=0,
                message_limit=6,
                image_limit=1,
                features={
                    "multi_stock_chat": False,
                    "basic_stock_search": True,
                    "aggregated_data": True,
                },
            )

            starter_plan = Subscription(
                name="Starter",
                price=5,
                message_limit=50,
                image_limit=15,
                features={
                    "multi_stock_chat": True,
                    "basic_stock_search": True,
                    "aggregated_data": True,
                    "expanded_historical": True,
                    "image_attachments": True,
                },
            )

            pro_plan = Subscription(
                name="Pro",
                price=15,
                message_limit=150,
                image_limit=50,
                features={
                    "multi_stock_chat": True,
                    "basic_stock_search": True,
                    "aggregated_data": True,
                    "expanded_historical": True,
                    "image_attachments": True,
                    "premium_analytics": True,
                    "advanced_chat": True,
                },
            )

            admin_plan = Subscription(
                name="Admin",
                price=0,
                message_limit=999999,
                image_limit=999999,
                features={
                    "multi_stock_chat": True,
                    "basic_stock_search": True,
                    "aggregated_data": True,
                    "expanded_historical": True,
                    "image_attachments": True,
                    "premium_analytics": True,
                    "advanced_chat": True,
                    "admin_features": True,
                    "key_management": True,
                },
            )

            try:
                print("Adding subscription plans to database...")
                db.session.add_all([free_plan, starter_plan, pro_plan, admin_plan])
                db.session.commit()
                print("Successfully created subscription plans!")
            except Exception as e:
                print(f"Error creating subscription plans: {str(e)}")
                db.session.rollback()
                raise

        print("Initializing referral rewards...")
        try:
            ReferralReward.init_rewards()
            print("Successfully initialized referral rewards!")
        except Exception as e:
            print(f"Error initializing referral rewards: {str(e)}")
            db.session.rollback()
            raise

        print("Generating missing referral codes...")
        try:
            users = User.query.filter(User.referral_code.is_(None)).all()
            for user in users:
                user.generate_referral_code()
            db.session.commit()
            print(f"Generated referral codes for {len(users)} users!")
        except Exception as e:
            print(f"Error generating referral codes: {str(e)}")
            db.session.rollback()
            raise

        print("Database initialization completed successfully!")