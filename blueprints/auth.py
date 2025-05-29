from datetime import datetime
import hashlib
import uuid
from urllib.parse import urlparse

from flask import (Blueprint, flash, redirect, render_template, request,
                   session, url_for, jsonify)
from flask_login import (current_user, login_required, login_user, logout_user)
from flask_wtf import FlaskForm
from wtforms import (BooleanField, PasswordField, StringField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length)
from flask_turnstile import Turnstile

from extensions import db
from models import ReferralReward, Subscription, User, UserSession
from utils.analytics import send_ga_event
from utils.ip import get_ip

auth = Blueprint("auth", __name__)


class LoginForm(FlaskForm):
    """Form for user login."""

    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")


class RegistrationForm(FlaskForm):
    """Form for user registration."""

    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )
    agree_tos = BooleanField("I agree to the Terms of Service", validators=[DataRequired()])


class TwoFactorForm(FlaskForm):
    code = StringField("Verification Code", validators=[DataRequired(), Length(min=6, max=8)])


@auth.route("/login", methods=["GET", "POST"])
def login():
    """Logs in a user.

    Returns:
        str: The rendered HTML template for the login page or a redirect.
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = LoginForm()
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("auth.login"))

        if not form.validate():
            flash("Invalid form submission. Please try again.")
            return redirect(url_for("auth.login"))

        turnstile = Turnstile()
        if not turnstile.verify():
            flash("Please complete the Turnstile verification.")
            return redirect(url_for("auth.login"))

        email = request.form.get("email")
        password = request.form.get("password")
        remember = True if request.form.get("remember") else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Please check your login details and try again.")
            return redirect(url_for("auth.login"))

        if user.two_factor_enabled:
            session["two_factor_user_id"] = user.id
            session["two_factor_remember"] = remember
            return redirect(url_for("auth.two_factor_verify"))

        user.ensure_subscription()
        login_user(user, remember=remember)
        session['remember'] = remember

        user_session = UserSession.create_session(user.id, remember=remember, request=request)
        session["session_token"] = user_session.session_token
        session['user_id'] = user.id

        send_ga_event(
            "user_login",
            user_id=str(user.id),
            event_params={
                "subscription_type": user.subscription.name if user.subscription else "Free",
                "device_info": UserSession.get_device_info(request.headers.get("User-Agent")),
            },
        )
        
        next_page = request.args.get("next")
        if not next_page or urlparse(next_page).netloc != "" or not next_page.startswith(url_for('')):
            next_page = url_for("chat")
        return redirect(next_page)

    return render_template("auth/login.html", form=form)


@auth.route("/two-factor-verify", methods=["GET", "POST"])
def two_factor_verify():
    """Verify 2FA code during login.

    Returns:
        str: The rendered HTML template for 2FA verification or a redirect.
    """
    user_id = session.get("two_factor_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for("auth.login"))

    form = TwoFactorForm()

    if request.method == "POST":
        code = request.form.get("code")

        if user.verify_2fa_code(code):
            remember = session.get("two_factor_remember", False)
            login_user(user, remember=remember)

            user_session = UserSession.create_session(user.id, remember=remember, request=request)
            session["session_token"] = user_session.session_token

            session.pop("two_factor_user_id", None)
            session.pop("two_factor_remember", None)

            send_ga_event(
                "user_login",
                user_id=str(user.id),
                event_params={
                    "subscription_type": user.subscription.name if user.subscription else "Free",
                    "remember_me": remember,
                    "login_method": "email_2fa",
                },
            )

            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        else:
            flash("Invalid verification code. Please try again.")

    return render_template("auth/two_factor_verify.html", form=form, email=user.email)


@auth.route("/register", methods=["GET", "POST"])
def register():
    """Registers a new user.

    Returns:
        str: The rendered HTML template for the registration page or a redirect.
    """
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form = RegistrationForm()
    if request.method == "POST":
        if request.form.get("website"):
            return redirect(url_for("auth.register"))

        if not form.validate():
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{getattr(form, field).label.text}: {error}")
            return redirect(url_for("auth.register"))

        turnstile = Turnstile()
        if not turnstile.verify():
            flash("Please complete the Turnstile verification.")
            return redirect(url_for("auth.register"))

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        agree_tos = request.form.get("agree_tos")

        if not agree_tos:
            flash("You must agree to the Terms of Service to register.")
            return redirect(url_for("auth.register"))

        user = User.query.filter_by(email=email).first()
        if user:
            flash("Email address already exists.")
            return redirect(url_for("auth.register"))
        
        referral_code = session.get("referral_code") or request.form.get("referral_code")
        referred_by = None

        if referral_code:
            referred_by = User.query.filter_by(referral_code=referral_code).first()
            if not referred_by:
                flash("Invalid referral code.")
                return redirect(url_for("auth.register"))

        tos_version = "1.0"
        tos_agreed_at = datetime.utcnow()
        ip_address = request.remote_addr
        user_agent = request.headers.get("User-Agent", "")

        signature_data = f"{email}|{tos_version}|{tos_agreed_at.isoformat()}|{ip_address}|{user_agent}|{uuid.uuid4()}"
        digital_signature = hashlib.sha256(signature_data.encode()).hexdigest()

        new_user = User(
            email=email,
            name=name,
            referred_by=referred_by,
            tos_agreed=True,
            tos_agreed_at=tos_agreed_at,
            tos_version=tos_version,
            tos_ip_address=ip_address,
            tos_user_agent=user_agent,
            tos_digital_signature=digital_signature
        )
        new_user.set_password(password)
        new_user.generate_referral_code()
        new_user.ensure_subscription()

        db.session.add(new_user)
        db.session.commit()

        if referred_by:
            referred_by.add_referral()
            session.pop("referral_code", None)
        
        ga_event_data = {
            'event': 'registration',
            'user_email': email,
            'referral_code': referral_code,
            'ip_address': ip_address,
            'user_agent': user_agent
        }
        send_ga_event(ga_event_data)

        flash("Registration successful! You can now log in.")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth.route("/logout")
@login_required
def logout():
    """Logs out the current user.

    Returns:
        str: A redirect to the index page.
    """
    user_id = str(current_user.id)
    subscription_type = "Free"
    if current_user.subscription:
        subscription_type = current_user.subscription.name

    session_token = session.get("session_token")
    if session_token:
        user_session = UserSession.query.filter_by(
            session_token=session_token,
            user_id=current_user.id,
            is_active=True,
        ).first()

        if user_session:
            user_session.terminate()
            flash("Your session has been terminated.", "info")
        else:
            active_sessions = UserSession.query.filter_by(user_id=current_user.id, is_active=True).all()

            for active_session in active_sessions:
                active_session.terminate()

            if active_sessions:
                flash(f"Terminated {len(active_sessions)} active sessions.", "info")

        session.pop("session_token", None)
    else:
        active_sessions = UserSession.query.filter_by(
            user_id=current_user.id,
            is_active=True,
        ).all()

        for active_session in active_sessions:
            active_session.terminate()

        if active_sessions:
            flash(f"Terminated {len(active_sessions)} active sessions.", "info")

    send_ga_event(
        "user_logout",
        user_id=user_id,
        event_params={"subscription_type": subscription_type},
    )

    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("index"))


@auth.route("/referrals")
@login_required
def referrals():
    """Display the user's referral dashboard.

    Returns:
        str: The rendered HTML template for the referral dashboard.
    """
    if not current_user.referral_code:
        current_user.generate_referral_code()
        db.session.commit()

    rewards = ReferralReward.query.order_by(ReferralReward.level).all()

    user_referrals = User.query.filter_by(referred_by_id=current_user.id).all()

    return render_template(
        "auth/referrals.html",
        rewards=rewards,
        referrals=user_referrals,
        referral_url=current_user.get_referral_url(request.host_url.rstrip("/")),
    )


@auth.route("/referrals/claim/<int:level>", methods=["POST"])
@login_required
def claim_referral_reward(level: int):
    """Claim a referral reward.

    Args:
        level (int): The level of the reward to claim.

    Returns:
        str: A redirect to the referral dashboard.
    """
    if current_user.claim_reward(level):
        flash(f"You've successfully claimed your Level {level} reward!", "success")
        return redirect(url_for("auth.referrals", success=True, level=level))
    else:
        flash("You're not eligible for this reward yet.", "error")
        return redirect(url_for("auth.referrals"))


@auth.route("/r/<referral_code>")
def referral_redirect(referral_code: str):
    """Redirect to the registration page with the referral code.

    Args:
        referral_code (str): The referral code to use.

    Returns:
        str: A redirect to the registration page with the referral code.
    """
    session["referral_code"] = referral_code
    return redirect(url_for("auth.register", ref=referral_code))


@auth.route("/sessions")
@login_required
def sessions():
    """Display the user's active sessions.

    Returns:
        str: The rendered HTML template for the sessions page.
    """
    active_sessions = UserSession.query.filter_by(user_id=current_user.id, is_active=True).order_by(
        UserSession.last_active.desc()
    ).all()

    current_session_token = session.get("session_token")

    return render_template(
        "auth/sessions.html",
        sessions=active_sessions,
        current_session_token=current_session_token,
    )


@auth.route("/sessions/terminate/<int:session_id>", methods=["POST"])
@login_required
def terminate_session(session_id: int):
    """Terminate a specific session.

    Args:
        session_id (int): The ID of the session to terminate.

    Returns:
        str: A redirect to the sessions page.
    """
    user_session = UserSession.query.filter_by(id=session_id, user_id=current_user.id).first()

    if not user_session:
        flash("Session not found.", "error")
        return redirect(url_for("auth.sessions"))

    current_session_token = session.get("session_token")

    if user_session.session_token == current_session_token:
        user_session.terminate()
        session.pop("session_token", None)
        logout_user()
        flash("Your current session has been terminated. You have been logged out.", "success")
        return redirect(url_for("auth.login"))

    user_session.terminate()
    flash("Session terminated successfully.", "success")

    return redirect(url_for("auth.sessions"))


@auth.route("/sessions/terminate-all", methods=["POST"])
@login_required
def terminate_all_sessions():
    """Terminate all sessions except the current one.

    Returns:
        str: A redirect to the sessions page.
    """
    current_session_token = session.get("session_token")

    if not current_session_token:
        flash("Current session not found.", "error")
        return redirect(url_for("auth.sessions"))

    sessions_to_terminate = UserSession.query.filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True,
        UserSession.session_token != current_session_token,
    ).all()

    for user_session in sessions_to_terminate:
        user_session.terminate()

    flash(f"{len(sessions_to_terminate)} other sessions terminated successfully.", "success")

    return redirect(url_for("auth.sessions"))


@auth.route("/security")
@login_required
def security():
    """Display the user's security settings.

    Returns:
        str: The rendered HTML template for the security page.
    """
    return render_template("auth/security.html")


@auth.route("/security/2fa/setup", methods=["GET", "POST"])
@login_required
def two_factor_setup():
    """Set up 2FA for the user.

    Returns:
        str: The rendered HTML template for 2FA setup or a redirect.
    """
    if current_user.two_factor_enabled:
        flash("Two-factor authentication is already enabled.")
        return redirect(url_for("auth.security"))

    if not current_user.two_factor_secret:
        current_user.generate_2fa_secret()

    qr_code = current_user.get_2fa_qr_code()

    if request.method == "POST":
        code = request.form.get("code")

        if current_user.verify_2fa_code(code):
            current_user.enable_2fa()

            backup_codes = current_user.generate_backup_codes()

            flash("Two-factor authentication has been enabled.")
            return render_template("auth/two_factor_backup_codes.html", backup_codes=backup_codes)
        else:
            flash("Invalid verification code. Please try again.")

    return render_template(
        "auth/two_factor_setup.html",
        qr_code=qr_code,
        secret=current_user.two_factor_secret,
    )


@auth.route("/security/2fa/disable", methods=["POST"])
@login_required
def two_factor_disable():
    """Disable 2FA for the user.

    Returns:
        redirect: A redirect to the security page.
    """
    if not current_user.two_factor_enabled:
        flash("Two-factor authentication is not enabled.")
        return redirect(url_for("auth.security"))

    password = request.form.get("password")
    if not current_user.check_password(password):
        flash("Incorrect password. Please try again.")
        return redirect(url_for("auth.security"))

    current_user.disable_2fa()

    flash("Two-factor authentication has been disabled.")
    return redirect(url_for("auth.security"))


@auth.route("/sessions/debug")
@login_required
def debug_session():
    """Debug the current session status.

    Returns:
        str: JSON with session debug information.
    """
    current_session_token = session.get("session_token")
    remember = session.get("remember", False)
    
    user_session = None
    if current_session_token:
        user_session = UserSession.query.filter_by(
            session_token=current_session_token,
            user_id=current_user.id,
            is_active=True
        ).first()
    
    active_sessions = UserSession.query.filter_by(
        user_id=current_user.id, 
        is_active=True
    ).count()
    
    all_sessions = UserSession.query.filter_by(
        user_id=current_user.id
    ).count()
    
    current_ip = get_ip(request)
    remote_addr = request.remote_addr
    
    ip_headers = {}
    for header in [
        'X-Forwarded-For', 'X-Real-IP', 'CF-Connecting-IP', 
        'True-Client-IP', 'X-Client-IP', 'X-Cluster-Client-IP',
        'X-Forwarded', 'Forwarded-For', 'Forwarded'
    ]:
        if header in request.headers:
            ip_headers[header] = request.headers.get(header)
    
    debug_info = {
        "has_session_token": bool(current_session_token),
        "remember_preference": remember,
        "valid_session": bool(user_session),
        "active_sessions_count": active_sessions,
        "all_sessions_count": all_sessions,
        "ip_info": {
            "detected_ip": current_ip,
            "remote_addr": remote_addr,
            "ip_headers": ip_headers
        }
    }
    
    if user_session:
        debug_info["session_info"] = {
            "id": user_session.id,
            "created_at": user_session.created_at.isoformat(),
            "last_active": user_session.last_active.isoformat(),
            "expires_at": user_session.expires_at.isoformat(),
            "device_info": user_session.device_info,
            "ip_address": user_session.ip_address
        }
    
    return jsonify(debug_info)
