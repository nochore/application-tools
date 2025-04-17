from datetime import datetime, timezone

import jwt
import requests

class SharepointAuthorizationHelper:

    def __init__(self, tenant, client_id, client_secret, scope, token_json):
        self.tenant = tenant
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.auth_code = None
        self.access_token = None
        self.token_json = token_json
        self.state = "12345"  # Static state for this example
        self.redirect_url = None

    def refresh_access_token(self) -> str:
        url = f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.token_json,
            'scope': self.scope
        }
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None

    def get_access_token(self) -> str:
        # Check the current access_token, not the refresh token (token_json)
        if self.access_token and self.is_token_valid(self.access_token):
            return self.access_token
        else:
            # If invalid or missing, refresh it
            new_token = self.refresh_access_token()
            self.access_token = new_token # Store the new token
            return new_token


    def is_token_valid(self, access_token) -> bool:
        # Handle None input gracefully
        if not access_token:
            return False
        try:
            # Ensure access_token is a string before decoding
            if not isinstance(access_token, str):
                 # Or log an error, depending on expected input types
                return False
            decoded_token = jwt.decode(access_token, options={"verify_signature": False})
            exp_timestamp = decoded_token.get("exp")
            if exp_timestamp is None:
                return False
            expiration_time = datetime.fromtimestamp(exp_timestamp, timezone.utc)
            return expiration_time > datetime.now(timezone.utc)
        except jwt.ExpiredSignatureError:
            return False
        except jwt.InvalidTokenError:
            return False
