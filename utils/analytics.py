import json
import os
import uuid
import requests


def send_ga_event(event_name: str, user_id: str = None, event_params: dict = None) -> None:
    """Sends an event to Google Analytics.

    Args:
        event_name (str): The name of the event to send.
        user_id (str, optional): The ID of the user associated with the event. Defaults to None.
        event_params (dict, optional): Additional parameters to send with the event. Defaults to None.
    """
    try:
        measurement_id: str = os.environ.get("GA4_MEASUREMENT_ID", "")
        api_secret    : str = os.environ.get("GA4_API_SECRET", "")

        if not api_secret:
            return

        client_id   : str  = user_id or str(uuid.uuid4())
        event_data  : dict = {
            "client_id": client_id,
            "events": [{"name": event_name, "params": event_params or {}}],
        }

        if user_id:
            event_data["user_id"] = user_id

        requests.post(
            f"https://www.google-analytics.com/mp/collect?measurement_id={measurement_id}&api_secret={api_secret}",
            data=json.dumps(event_data),
            headers={"Content-Type": "application/json"},
            timeout=2,
        )
    except Exception as e:
        print(f"Error sending GA event: {e}")