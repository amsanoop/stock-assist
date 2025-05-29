from models import User, UserSession

def cleanup_expired_sessions():
    """Clean up expired sessions."""
    count = UserSession.cleanup_expired_sessions()
    print(f"Cleaned up {count} expired sessions.") 
