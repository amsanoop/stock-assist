import requests
from .constants.api_constants import _GENERAL_API_URL, _METHODS

class SyncClient:
    def request(self, method: str, endpoint: str, json_data=None):
        if method not in _METHODS:
            raise ValueError(f'Unsupported method "{method}".')
        url = f'{_GENERAL_API_URL}/{endpoint}'
        response = requests.request(method, url, json=json_data)
        if response.status_code == 200:
            if response.headers.get('content-type') == 'application/json':
                return response.json()
            else:
                return response.text
        else:
            raise Exception(f'Failed to make request: {response.status_code} - {response.reason}')