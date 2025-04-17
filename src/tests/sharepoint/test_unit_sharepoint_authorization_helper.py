import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import jwt
import pytest
import requests

from src.alita_tools.sharepoint.authorization_helper import SharepointAuthorizationHelper


# --- Fixtures ---

@pytest.fixture
def mock_requests_post():
    """Fixture to mock requests.post."""
    with patch('src.alita_tools.sharepoint.authorization_helper.requests.post') as mock_post:
        yield mock_post

@pytest.fixture
def mock_jwt_decode():
    """Fixture to mock jwt.decode."""
    with patch('src.alita_tools.sharepoint.authorization_helper.jwt.decode') as mock_decode:
        yield mock_decode

@pytest.fixture
def valid_token_json():
    """Fixture for a valid-looking token structure (content doesn't matter for structure)."""
    # The actual access token within this structure will be mocked by jwt.decode
    return {
        "token_type": "Bearer",
        "scope": "Files.ReadWrite.All",
        "expires_in": 3599,
        "ext_expires_in": 3599,
        "access_token": "valid_access_token_string", # This value is checked by is_token_valid
        "refresh_token": "valid_refresh_token_string" # This value is used by refresh_access_token
    }

@pytest.fixture
def auth_helper(valid_token_json):
    """Fixture to create a SharepointAuthorizationHelper instance."""
    return SharepointAuthorizationHelper(
        tenant="test_tenant",
        client_id="test_client_id",
        client_secret="test_client_secret",
        scope="Files.ReadWrite.All",
        token_json=valid_token_json['refresh_token'] # Pass only the refresh token string
    )

# --- Helper Function for Mock Responses ---

def mock_response(status_code=200, json_data=None, text_data=None, raise_for_status_error=None):
    """Creates a mock requests.Response object."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json.return_value = json_data
    mock_resp.text = text_data if text_data is not None else str(json_data) # Default text
    if status_code >= 400:
        mock_resp.json.side_effect = requests.exceptions.JSONDecodeError("Mock JSON decode error", "doc", 0) if json_data is None else None
        if raise_for_status_error:
            mock_resp.raise_for_status.side_effect = raise_for_status_error
        else:
            http_error = requests.exceptions.HTTPError(f"{status_code} Client Error")
            http_error.response = mock_resp
            mock_resp.raise_for_status.side_effect = http_error if status_code >= 400 else None
    else:
         mock_resp.raise_for_status.return_value = None

    if json_data is not None:
         mock_resp.json.side_effect = None
         mock_resp.json.return_value = json_data

    return mock_resp

# --- Test Class ---

@pytest.mark.unit
@pytest.mark.sharepoint
class TestSharepointAuthorizationHelper:

    # --- __init__ Test ---
    @pytest.mark.positive
    def test_init(self, auth_helper, valid_token_json):
        """Test initialization of SharepointAuthorizationHelper."""
        assert auth_helper.tenant == "test_tenant"
        assert auth_helper.client_id == "test_client_id"
        assert auth_helper.client_secret == "test_client_secret"
        assert auth_helper.scope == "Files.ReadWrite.All"
        assert auth_helper.token_json == valid_token_json['refresh_token'] # Ensure it stores the refresh token
        assert auth_helper.access_token is None # Initially no access token
        assert auth_helper.state == "12345" # Static state

    # --- refresh_access_token Tests ---
    @pytest.mark.positive
    def test_refresh_access_token_success(self, auth_helper, mock_requests_post, valid_token_json):
        """Test successful token refresh."""
        mock_api_response = mock_response(200, {"access_token": "new_refreshed_token"})
        mock_requests_post.return_value = mock_api_response

        new_token = auth_helper.refresh_access_token()

        assert new_token == "new_refreshed_token"
        expected_url = f"https://login.microsoftonline.com/{auth_helper.tenant}/oauth2/v2.0/token"
        expected_data = {
            'grant_type': 'refresh_token',
            'client_id': auth_helper.client_id,
            'client_secret': auth_helper.client_secret,
            'refresh_token': valid_token_json['refresh_token'], # Use the refresh token
            'scope': auth_helper.scope
        }
        expected_headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        mock_requests_post.assert_called_once_with(expected_url, headers=expected_headers, data=expected_data)

    @pytest.mark.negative
    def test_refresh_access_token_failure(self, auth_helper, mock_requests_post, capsys):
        """Test failed token refresh."""
        mock_api_response = mock_response(400, text_data="Invalid grant")
        mock_requests_post.return_value = mock_api_response

        result = auth_helper.refresh_access_token()

        assert result is None
        captured = capsys.readouterr()
        assert "Error: 400" in captured.out
        assert "Invalid grant" in captured.out
        mock_requests_post.assert_called_once() # Ensure request was made

    # --- is_token_valid Tests ---
    @pytest.mark.positive
    def test_is_token_valid_success(self, auth_helper, mock_jwt_decode):
        """Test token validation with a valid, non-expired token."""
        future_exp = time.time() + 3600 # 1 hour in the future
        mock_jwt_decode.return_value = {"exp": future_exp}

        is_valid = auth_helper.is_token_valid("some_access_token_string")

        assert is_valid is True
        mock_jwt_decode.assert_called_once_with("some_access_token_string", options={"verify_signature": False})

    @pytest.mark.negative
    def test_is_token_valid_expired_signature(self, auth_helper, mock_jwt_decode):
        """Test token validation when jwt.decode raises ExpiredSignatureError."""
        mock_jwt_decode.side_effect = jwt.ExpiredSignatureError("Signature has expired")

        is_valid = auth_helper.is_token_valid("expired_token_string")

        assert is_valid is False
        mock_jwt_decode.assert_called_once_with("expired_token_string", options={"verify_signature": False})

    @pytest.mark.negative
    def test_is_token_valid_invalid_token(self, auth_helper, mock_jwt_decode):
        """Test token validation when jwt.decode raises InvalidTokenError."""
        mock_jwt_decode.side_effect = jwt.InvalidTokenError("Invalid token")

        is_valid = auth_helper.is_token_valid("invalid_token_string")

        assert is_valid is False
        mock_jwt_decode.assert_called_once_with("invalid_token_string", options={"verify_signature": False})

    @pytest.mark.negative
    def test_is_token_valid_no_exp_claim(self, auth_helper, mock_jwt_decode):
        """Test token validation when the decoded token has no 'exp' claim."""
        mock_jwt_decode.return_value = {"sub": "user123"} # No 'exp'

        is_valid = auth_helper.is_token_valid("token_without_exp")

        assert is_valid is False
        mock_jwt_decode.assert_called_once_with("token_without_exp", options={"verify_signature": False})

    @pytest.mark.negative
    def test_is_token_valid_past_exp(self, auth_helper, mock_jwt_decode):
        """Test token validation with an 'exp' claim in the past."""
        past_exp = time.time() - 3600 # 1 hour in the past
        mock_jwt_decode.return_value = {"exp": past_exp}

        is_valid = auth_helper.is_token_valid("past_exp_token")

        assert is_valid is False
        mock_jwt_decode.assert_called_once_with("past_exp_token", options={"verify_signature": False})

    # --- get_access_token Tests ---
    @pytest.mark.positive
    @patch.object(SharepointAuthorizationHelper, 'is_token_valid')
    @patch.object(SharepointAuthorizationHelper, 'refresh_access_token')
    def test_get_access_token_valid_token_present(self, mock_refresh, mock_is_valid, auth_helper, valid_token_json):
        """Test get_access_token when a valid token is already stored (simulated)."""
        # Simulate that a valid access token exists and is_token_valid confirms it
        auth_helper.access_token = "existing_valid_token" # Manually set for test
        mock_is_valid.return_value = True

        token = auth_helper.get_access_token()

        assert token == "existing_valid_token"
        # Pass the currently stored access_token to is_token_valid
        mock_is_valid.assert_called_once_with(auth_helper.access_token)
        mock_refresh.assert_not_called() # Refresh should not be called

    @pytest.mark.positive
    @patch.object(SharepointAuthorizationHelper, 'is_token_valid')
    @patch.object(SharepointAuthorizationHelper, 'refresh_access_token')
    def test_get_access_token_invalid_token_refresh_success(self, mock_refresh, mock_is_valid, auth_helper):
        """Test get_access_token when token is invalid/missing and refresh succeeds."""
        auth_helper.access_token = "old_or_invalid_token" # Set some token
        mock_is_valid.return_value = False # Simulate token is invalid
        mock_refresh.return_value = "newly_refreshed_token" # Simulate successful refresh

        token = auth_helper.get_access_token()

        assert token == "newly_refreshed_token"
        mock_is_valid.assert_called_once_with("old_or_invalid_token")
        mock_refresh.assert_called_once() # Refresh should be called
        assert auth_helper.access_token == "newly_refreshed_token" # Ensure token is updated

    @pytest.mark.positive
    @patch.object(SharepointAuthorizationHelper, 'is_token_valid')
    @patch.object(SharepointAuthorizationHelper, 'refresh_access_token')
    def test_get_access_token_no_token_refresh_success(self, mock_refresh, mock_is_valid, auth_helper):
        """Test get_access_token when no token exists initially and refresh succeeds."""
        auth_helper.access_token = None # Ensure no token initially
        # is_token_valid should return False if token is None (or handle appropriately)
        # Let's assume is_token_valid handles None gracefully or isn't called if token is None.
        # The current logic calls is_token_valid even if self.access_token is None.
        mock_is_valid.return_value = False # Simulate token is invalid (or None)
        mock_refresh.return_value = "newly_refreshed_token" # Simulate successful refresh

        token = auth_helper.get_access_token()

        assert token == "newly_refreshed_token"
        # is_token_valid is short-circuited because self.access_token is None initially
        mock_is_valid.assert_not_called()
        mock_refresh.assert_called_once() # Refresh should be called
        assert auth_helper.access_token == "newly_refreshed_token" # Ensure token is updated


    @pytest.mark.negative
    @patch.object(SharepointAuthorizationHelper, 'is_token_valid')
    @patch.object(SharepointAuthorizationHelper, 'refresh_access_token')
    def test_get_access_token_invalid_token_refresh_failure(self, mock_refresh, mock_is_valid, auth_helper):
        """Test get_access_token when token is invalid and refresh fails."""
        auth_helper.access_token = "invalid_token"
        mock_is_valid.return_value = False # Simulate token is invalid
        mock_refresh.return_value = None # Simulate failed refresh

        token = auth_helper.get_access_token()

        assert token is None
        mock_is_valid.assert_called_once_with("invalid_token")
        mock_refresh.assert_called_once()
        # Access token should become None after a failed refresh attempt
        assert auth_helper.access_token is None
