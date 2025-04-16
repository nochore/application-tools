import json
from unittest.mock import MagicMock, patch

import pytest
import requests
from langchain_core.tools import ToolException

from src.alita_tools.salesforce.api_wrapper import SalesforceApiWrapper
from src.alita_tools.salesforce.model import (
    SalesforceCreateCase,
    SalesforceCreateLead,
    SalesforceSearch,
    SalesforceUpdateCase,
    SalesforceUpdateLead,
    SalesforceInput,
    NoInput
)

# --- Fixtures ---

@pytest.fixture
def mock_requests():
    """Fixture to mock the requests library."""
    with patch('src.alita_tools.salesforce.api_wrapper.requests') as mock_req:
        yield mock_req

@pytest.fixture
def salesforce_wrapper(mock_requests):
    """Fixture to create a SalesforceApiWrapper instance with mocks."""
    wrapper = SalesforceApiWrapper(
        base_url="https://test.salesforce.com",
        client_id="test_client_id",
        client_secret="test_client_secret",
        api_version="v59.0"
    )
    # Mock successful authentication by default in the fixture setup
    mock_auth_response = MagicMock()
    mock_auth_response.status_code = 200
    mock_auth_response.json.return_value = {"access_token": "mock_access_token"}
    mock_requests.post.return_value = mock_auth_response
    # wrapper.authenticate() # Call authenticate to set the token initially if needed, or let methods call it
    return wrapper

# --- Helper Function for Mock Responses ---

def mock_response(status_code=200, json_data=None, text_data=None, raise_for_status_error=None):
    """Creates a mock requests.Response object."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json.return_value = json_data
    if text_data is not None:
        mock_resp.text = text_data
    if status_code >= 400:
        mock_resp.json.side_effect = requests.exceptions.JSONDecodeError("Mock JSON decode error", "doc", 0) if json_data is None else None # Simulate JSON error if no json_data for error codes
        if raise_for_status_error:
            mock_resp.raise_for_status.side_effect = raise_for_status_error
        else:
            # Default behavior for raise_for_status based on status code
            http_error = requests.exceptions.HTTPError(f"{status_code} Client Error")
            http_error.response = mock_resp
            mock_resp.raise_for_status.side_effect = http_error if status_code >= 400 else None
    else:
         mock_resp.raise_for_status.return_value = None # Successful status codes don't raise

    # Ensure json() can be called multiple times if needed, returning the same data
    if json_data is not None:
         mock_resp.json.side_effect = None # Reset side effect if json_data is provided
         mock_resp.json.return_value = json_data


    return mock_resp

# --- Test Class ---

@pytest.mark.unit
@pytest.mark.salesforce
class TestSalesforceApiWrapper:

    # --- Authentication Tests ---
    @pytest.mark.positive
    def test_authenticate_success(self, salesforce_wrapper, mock_requests):
        """Test successful authentication."""
        mock_auth_response = mock_response(200, {"access_token": "new_mock_token"})
        mock_requests.post.return_value = mock_auth_response

        salesforce_wrapper.authenticate()

        assert salesforce_wrapper._access_token == "new_mock_token"
        mock_requests.post.assert_called_once_with(
            f"{salesforce_wrapper.base_url}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": salesforce_wrapper.client_id,
                "client_secret": salesforce_wrapper.client_secret
            }
        )

    @pytest.mark.negative
    def test_authenticate_failure(self, salesforce_wrapper, mock_requests):
        """Test authentication failure."""
        mock_auth_response = mock_response(status_code=400, raise_for_status_error=requests.exceptions.HTTPError("Auth failed"))
        mock_requests.post.return_value = mock_auth_response

        with pytest.raises(requests.exceptions.HTTPError, match="Auth failed"):
            salesforce_wrapper.authenticate()
        assert salesforce_wrapper._access_token is None # Token should not be set

    @pytest.mark.positive
    def test_headers_calls_authenticate(self, salesforce_wrapper, mock_requests):
        """Test that _headers calls authenticate if no token exists."""
        salesforce_wrapper._access_token = None # Ensure no token initially
        mock_auth_response = mock_response(200, {"access_token": "mock_access_token"})
        mock_requests.post.return_value = mock_auth_response # Mock auth call within _headers

        headers = salesforce_wrapper._headers()

        assert headers["Authorization"] == "Bearer mock_access_token"
        mock_requests.post.assert_called_once() # Authenticate should have been called

    @pytest.mark.positive
    def test_headers_uses_existing_token(self, salesforce_wrapper, mock_requests):
        """Test that _headers uses existing token without calling authenticate."""
        salesforce_wrapper._access_token = "existing_token" # Set token directly

        headers = salesforce_wrapper._headers()

        assert headers["Authorization"] == "Bearer existing_token"
        mock_requests.post.assert_not_called() # Authenticate should NOT have been called

    # --- Error Parsing Tests ---
    @pytest.mark.positive
    def test_parse_salesforce_error_success_200(self, salesforce_wrapper):
        """Test parsing a successful 200 response."""
        response = mock_response(200, {"id": "123", "success": True})
        error = salesforce_wrapper._parse_salesforce_error(response)
        assert error is None

    @pytest.mark.positive
    def test_parse_salesforce_error_success_201(self, salesforce_wrapper):
        """Test parsing a successful 201 created response."""
        response = mock_response(201, {"id": "456", "success": True})
        error = salesforce_wrapper._parse_salesforce_error(response)
        assert error is None

    @pytest.mark.positive
    def test_parse_salesforce_error_success_204(self, salesforce_wrapper):
        """Test parsing a successful 204 No Content response."""
        response = mock_response(204)
        error = salesforce_wrapper._parse_salesforce_error(response)
        assert error is None

    @pytest.mark.negative
    def test_parse_salesforce_error_single_error_dict(self, salesforce_wrapper):
        """Test parsing a single error dictionary."""
        response = mock_response(400, {"message": "Required field missing", "errorCode": "MISSING_FIELD"})
        error = salesforce_wrapper._parse_salesforce_error(response)
        assert error == "Required field missing"

    @pytest.mark.negative
    def test_parse_salesforce_error_list_of_errors(self, salesforce_wrapper):
        """Test parsing a list of error dictionaries."""
        response = mock_response(400, [
            {"message": "Invalid email address", "errorCode": "INVALID_EMAIL"},
            {"message": "Field integrity exception", "errorCode": "FIELD_INTEGRITY_EXCEPTION"}
        ])
        error = salesforce_wrapper._parse_salesforce_error(response)
        assert error == "Invalid email address; Field integrity exception"

    @pytest.mark.negative
    def test_parse_salesforce_error_duplicate_detected(self, salesforce_wrapper):
        """Test parsing a duplicate detected error."""
        response = mock_response(400, [{"message": "Use one of these records?", "errorCode": "DUPLICATES_DETECTED"}])
        error = salesforce_wrapper._parse_salesforce_error(response)
        assert error == "Duplicate detected: Salesforce found similar records. Consider updating an existing record."

    @pytest.mark.negative
    def test_parse_salesforce_error_no_json(self, salesforce_wrapper):
        """Test parsing an error response with no JSON body."""
        response = mock_response(500, json_data=None) # Simulate no JSON body
        # Manually set side_effect for json() on this specific mock
        response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "doc", 0)
        error = salesforce_wrapper._parse_salesforce_error(response)
        assert error == "No JSON response from Salesforce. HTTP Status: 500"

    @pytest.mark.negative
    def test_parse_salesforce_error_unexpected_format(self, salesforce_wrapper):
        """Test parsing an error response with an unexpected format."""
        response = mock_response(400, {"unexpected": "format"})
        error = salesforce_wrapper._parse_salesforce_error(response)
        assert error == "Unexpected response format: {'unexpected': 'format'}"


    # --- Create Case Tests ---
    @pytest.mark.positive
    def test_create_case_success(self, salesforce_wrapper, mock_requests):
        """Test successful case creation."""
        mock_api_response = mock_response(201, {"id": "case123", "success": True})
        mock_requests.post.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token" # Ensure token is set

        result = salesforce_wrapper.create_case(
            subject="Test Subject",
            description="Test Description",
            origin="Web",
            status="New"
        )

        assert result == {"id": "case123", "success": True}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/sobjects/Case/"
        expected_payload = {
            "Subject": "Test Subject",
            "Description": "Test Description",
            "Origin": "Web",
            "Status": "New"
        }
        mock_requests.post.assert_called_once_with(
            expected_url,
            json=expected_payload,
            headers=salesforce_wrapper._headers()
        )

    @pytest.mark.negative
    def test_create_case_failure(self, salesforce_wrapper, mock_requests):
        """Test case creation failure."""
        mock_error_response = mock_response(400, [{"message": "Missing required field", "errorCode": "REQUIRED_FIELD_MISSING"}])
        mock_requests.post.return_value = mock_error_response
        salesforce_wrapper._access_token = "mock_token"

        result = salesforce_wrapper.create_case("Test", "Desc", "Phone", "Open")

        assert isinstance(result, ToolException)
        assert "Failed to create Case. Error: Missing required field" in str(result)


    # --- Create Lead Tests ---
    @pytest.mark.positive
    def test_create_lead_success(self, salesforce_wrapper, mock_requests):
        """Test successful lead creation."""
        mock_api_response = mock_response(201, {"id": "lead456", "success": True})
        mock_requests.post.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"

        result = salesforce_wrapper.create_lead(
            last_name="Doe",
            company="Acme Corp",
            email="john.doe@acme.com",
            phone="1234567890"
        )

        assert result == {"id": "lead456", "success": True}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/sobjects/Lead/"
        expected_payload = {
            "LastName": "Doe",
            "Company": "Acme Corp",
            "Email": "john.doe@acme.com",
            "Phone": "1234567890"
        }
        mock_requests.post.assert_called_once_with(
            expected_url,
            json=expected_payload,
            headers=salesforce_wrapper._headers()
        )

    @pytest.mark.negative
    def test_create_lead_failure(self, salesforce_wrapper, mock_requests):
        """Test lead creation failure."""
        mock_error_response = mock_response(400, [{"message": "Invalid Email", "errorCode": "INVALID_EMAIL_ADDRESS"}])
        mock_requests.post.return_value = mock_error_response
        salesforce_wrapper._access_token = "mock_token"

        result = salesforce_wrapper.create_lead("Smith", "Test Inc", "invalid-email", "9876543210")

        assert isinstance(result, ToolException)
        assert "Failed to create Lead. Error: Invalid Email" in str(result)


    # --- Search Salesforce Tests ---
    @pytest.mark.positive
    def test_search_salesforce_success(self, salesforce_wrapper, mock_requests):
        """Test successful SOQL search."""
        mock_api_response = mock_response(200, {"totalSize": 1, "records": [{"Id": "case789"}]})
        mock_requests.get.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        query = "SELECT Id FROM Case WHERE Status='New'"
        encoded_query = requests.utils.quote(query) # URL encode the query

        result = salesforce_wrapper.search_salesforce(object_type="Case", query=query)

        assert result == {"totalSize": 1, "records": [{"Id": "case789"}]}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/query?q={encoded_query}"
        mock_requests.get.assert_called_once_with(
            expected_url,
            headers=salesforce_wrapper._headers()
        )

    @pytest.mark.negative
    def test_search_salesforce_failure(self, salesforce_wrapper, mock_requests):
        """Test SOQL search failure."""
        mock_error_response = mock_response(400, [{"message": "Invalid SOQL", "errorCode": "MALFORMED_QUERY"}])
        mock_requests.get.return_value = mock_error_response
        salesforce_wrapper._access_token = "mock_token"
        query = "SELECT NonExistentField FROM Case"
        encoded_query = requests.utils.quote(query)

        result = salesforce_wrapper.search_salesforce(object_type="Case", query=query)

        assert isinstance(result, ToolException)
        assert "Failed to execute SOQL query. Errors: Invalid SOQL" in str(result)

    @pytest.mark.negative
    def test_search_salesforce_failure_single_error_dict(self, salesforce_wrapper, mock_requests):
        """Test SOQL search failure with a single error dictionary response."""
        mock_error_response = mock_response(400, {"message": "Specific error message", "errorCode": "SOME_CODE"})
        mock_requests.get.return_value = mock_error_response
        salesforce_wrapper._access_token = "mock_token"
        query = "SELECT Id FROM Account"
        encoded_query = requests.utils.quote(query)

        result = salesforce_wrapper.search_salesforce(object_type="Account", query=query)

        assert isinstance(result, ToolException)
        # This assertion specifically checks the message extracted from the dictionary
        assert "Failed to execute SOQL query. Errors: Specific error message" in str(result)
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/query?q={encoded_query}"
        mock_requests.get.assert_called_once_with(
            expected_url,
            headers=salesforce_wrapper._headers()
        )


    @pytest.mark.negative
    def test_search_salesforce_failure_no_json(self, salesforce_wrapper, mock_requests):
        """Test SOQL search failure with no JSON response."""
        mock_error_response = mock_response(500, json_data=None)
        mock_error_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "doc", 0)
        mock_requests.get.return_value = mock_error_response
        salesforce_wrapper._access_token = "mock_token"
        query = "SELECT Id FROM Case"

        result = salesforce_wrapper.search_salesforce(object_type="Case", query=query)

        assert isinstance(result, ToolException)
        assert "Failed to execute SOQL query. No JSON response. Status: 500" in str(result)


    # --- Update Case Tests ---
    @pytest.mark.positive
    def test_update_case_success_no_desc(self, salesforce_wrapper, mock_requests):
        """Test successful case update without description."""
        mock_api_response = mock_response(204) # Successful update returns 204
        mock_requests.patch.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        case_id = "case123"

        result = salesforce_wrapper.update_case(case_id=case_id, status="Closed")

        assert result == {"success": True, "message": f"Case {case_id} updated successfully."}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/sobjects/Case/{case_id}"
        expected_payload = {"Status": "Closed"}
        mock_requests.patch.assert_called_once_with(
            expected_url,
            json=expected_payload,
            headers=salesforce_wrapper._headers()
        )

    @pytest.mark.positive
    def test_update_case_success_with_desc(self, salesforce_wrapper, mock_requests):
        """Test successful case update with description."""
        mock_api_response = mock_response(204)
        mock_requests.patch.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        case_id = "case456"

        result = salesforce_wrapper.update_case(case_id=case_id, status="Working", description="Updated description")

        assert result == {"success": True, "message": f"Case {case_id} updated successfully."}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/sobjects/Case/{case_id}"
        expected_payload = {"Status": "Working", "Description": "Updated description"}
        mock_requests.patch.assert_called_once_with(
            expected_url,
            json=expected_payload,
            headers=salesforce_wrapper._headers()
        )

    @pytest.mark.negative
    def test_update_case_failure(self, salesforce_wrapper, mock_requests):
        """Test case update failure."""
        mock_error_response = mock_response(404, [{"message": "Case not found", "errorCode": "NOT_FOUND"}])
        mock_requests.patch.return_value = mock_error_response
        salesforce_wrapper._access_token = "mock_token"
        case_id = "nonexistent_case"

        with pytest.raises(ToolException, match=f"Failed to update Case {case_id}. Error: Case not found"):
            salesforce_wrapper.update_case(case_id=case_id, status="Closed")


    # --- Update Lead Tests ---
    @pytest.mark.positive
    def test_update_lead_success_email_only(self, salesforce_wrapper, mock_requests):
        """Test successful lead update with only email."""
        mock_api_response = mock_response(204)
        mock_requests.patch.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        lead_id = "lead123"

        result = salesforce_wrapper.update_lead(lead_id=lead_id, email="new.email@example.com")

        assert result == {"success": True, "message": f"Lead {lead_id} updated successfully."}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/sobjects/Lead/{lead_id}"
        expected_payload = {"Email": "new.email@example.com"}
        mock_requests.patch.assert_called_once_with(
            expected_url,
            json=expected_payload,
            headers=salesforce_wrapper._headers()
        )

    @pytest.mark.positive
    def test_update_lead_success_phone_only(self, salesforce_wrapper, mock_requests):
        """Test successful lead update with only phone."""
        mock_api_response = mock_response(204)
        mock_requests.patch.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        lead_id = "lead456"

        result = salesforce_wrapper.update_lead(lead_id=lead_id, phone="1112223333")

        assert result == {"success": True, "message": f"Lead {lead_id} updated successfully."}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/sobjects/Lead/{lead_id}"
        expected_payload = {"Phone": "1112223333"}
        mock_requests.patch.assert_called_once_with(
            expected_url,
            json=expected_payload,
            headers=salesforce_wrapper._headers()
        )

    @pytest.mark.positive
    def test_update_lead_success_both(self, salesforce_wrapper, mock_requests):
        """Test successful lead update with both email and phone."""
        mock_api_response = mock_response(204)
        mock_requests.patch.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        lead_id = "lead789"

        result = salesforce_wrapper.update_lead(lead_id=lead_id, email="another@example.com", phone="4445556666")

        assert result == {"success": True, "message": f"Lead {lead_id} updated successfully."}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}/sobjects/Lead/{lead_id}"
        expected_payload = {"Email": "another@example.com", "Phone": "4445556666"}
        mock_requests.patch.assert_called_once_with(
            expected_url,
            json=expected_payload,
            headers=salesforce_wrapper._headers()
        )

    @pytest.mark.negative
    def test_update_lead_failure(self, salesforce_wrapper, mock_requests):
        """Test lead update failure."""
        mock_error_response = mock_response(400, [{"message": "Invalid phone number", "errorCode": "INVALID_FIELD"}])
        mock_requests.patch.return_value = mock_error_response
        salesforce_wrapper._access_token = "mock_token"
        lead_id = "lead_abc"

        result = salesforce_wrapper.update_lead(lead_id=lead_id, phone="invalid-phone")

        assert isinstance(result, ToolException)
        assert f"Failed to update Lead {lead_id}. Error: Invalid phone number" in str(result)


    # --- Execute Generic Request Tests ---
    @pytest.mark.positive
    def test_execute_generic_rq_get_success(self, salesforce_wrapper, mock_requests):
        """Test successful generic GET request."""
        mock_api_response = mock_response(200, {"records": [{"Id": "1"}]})
        mock_requests.request.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        relative_url = "/sobjects/Account/describe"

        result = salesforce_wrapper.execute_generic_rq(method="GET", relative_url=relative_url)

        assert result == {"records": [{"Id": "1"}]}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}{relative_url}"
        mock_requests.request.assert_called_once_with(
            "GET",
            expected_url,
            headers=salesforce_wrapper._headers(),
            json=None # No JSON body for GET
        )

    @pytest.mark.positive
    def test_execute_generic_rq_post_success(self, salesforce_wrapper, mock_requests):
        """Test successful generic POST request."""
        mock_api_response = mock_response(201, {"id": "new_record", "success": True})
        mock_requests.request.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        relative_url = "/sobjects/Contact/"
        params = json.dumps({"LastName": "Test"})

        result = salesforce_wrapper.execute_generic_rq(method="POST", relative_url=relative_url, params=params)

        assert result == {"id": "new_record", "success": True}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}{relative_url}"
        mock_requests.request.assert_called_once_with(
            "POST",
            expected_url,
            headers=salesforce_wrapper._headers(),
            json={"LastName": "Test"}
        )

    @pytest.mark.positive
    def test_execute_generic_rq_patch_success_204(self, salesforce_wrapper, mock_requests):
        """Test successful generic PATCH request returning 204."""
        mock_api_response = mock_response(204)
        mock_requests.request.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        relative_url = "/sobjects/Account/acc123"
        params = json.dumps({"Name": "Updated Name"})

        result = salesforce_wrapper.execute_generic_rq(method="PATCH", relative_url=relative_url, params=params)

        assert result == {"success": True, "message": f"PATCH request to {relative_url} executed successfully."}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}{relative_url}"
        mock_requests.request.assert_called_once_with(
            "PATCH",
            expected_url,
            headers=salesforce_wrapper._headers(),
            json={"Name": "Updated Name"}
        )

    @pytest.mark.positive
    def test_execute_generic_rq_delete_success_204(self, salesforce_wrapper, mock_requests):
        """Test successful generic DELETE request returning 204."""
        mock_api_response = mock_response(204)
        mock_requests.request.return_value = mock_api_response
        salesforce_wrapper._access_token = "mock_token"
        relative_url = "/sobjects/Task/task456"

        result = salesforce_wrapper.execute_generic_rq(method="DELETE", relative_url=relative_url) # No params needed

        assert result == {"success": True, "message": f"DELETE request to {relative_url} executed successfully."}
        expected_url = f"{salesforce_wrapper.base_url}/services/data/{salesforce_wrapper.api_version}{relative_url}"
        mock_requests.request.assert_called_once_with(
            "DELETE",
            expected_url,
            headers=salesforce_wrapper._headers(),
            json={} # Default empty dict for params=None
        )

    @pytest.mark.negative
    def test_execute_generic_rq_invalid_json_params(self, salesforce_wrapper):
        """Test generic request with invalid JSON in params."""
        with pytest.raises(ToolException, match="Invalid JSON format in 'params'."):
            salesforce_wrapper.execute_generic_rq(method="POST", relative_url="/sobjects/Test", params="{invalid json")

    @pytest.mark.negative
    def test_execute_generic_rq_api_error(self, salesforce_wrapper, mock_requests):
        """Test generic request failure due to API error."""
        mock_error_response = mock_response(400, [{"message": "Generic API error", "errorCode": "API_ERROR"}])
        mock_requests.request.return_value = mock_error_response
        salesforce_wrapper._access_token = "mock_token"
        relative_url = "/sobjects/InvalidObject"

        result = salesforce_wrapper.execute_generic_rq(method="GET", relative_url=relative_url)

        assert isinstance(result, ToolException)
        assert f"Failed GET request to {relative_url}. Error: Generic API error" in str(result)


    # --- Get Available Tools Test ---
    @pytest.mark.positive
    def test_get_available_tools(self, salesforce_wrapper):
        """Test getting available tools."""
        tools = salesforce_wrapper.get_available_tools()

        assert isinstance(tools, list)
        assert len(tools) == 6 # Should match the number of tools defined

        # Check structure of the first tool
        first_tool = tools[0]
        assert "name" in first_tool
        assert "description" in first_tool
        assert "args_schema" in first_tool
        assert "ref" in first_tool
        assert first_tool["name"] == "create_case"
        assert first_tool["args_schema"] == SalesforceCreateCase
        assert first_tool["ref"] == salesforce_wrapper.create_case

        # Check structure of the last tool
        last_tool = tools[-1]
        assert last_tool["name"] == "execute_generic_rq"
        assert last_tool["args_schema"] == SalesforceInput
        assert last_tool["ref"] == salesforce_wrapper.execute_generic_rq


    # --- Model Tests (Basic validation) ---
    @pytest.mark.positive
    def test_salesforce_create_case_model(self):
        """Test SalesforceCreateCase model validation."""
        data = {"subject": "S", "description": "D", "origin": "O", "status": "St"}
        model = SalesforceCreateCase(**data)
        assert model.subject == "S"
        assert model.description == "D"
        assert model.origin == "O"
        assert model.status == "St"

    @pytest.mark.positive
    def test_salesforce_create_lead_model(self):
        """Test SalesforceCreateLead model validation."""
        data = {"last_name": "L", "company": "C", "email": "E", "phone": "P"}
        model = SalesforceCreateLead(**data)
        assert model.last_name == "L"
        assert model.company == "C"
        assert model.email == "E"
        assert model.phone == "P"

    @pytest.mark.positive
    def test_salesforce_search_model(self):
        """Test SalesforceSearch model validation."""
        data = {"object_type": "OT", "query": "Q"}
        model = SalesforceSearch(**data)
        assert model.object_type == "OT"
        assert model.query == "Q"

    @pytest.mark.positive
    def test_salesforce_update_case_model(self):
        """Test SalesforceUpdateCase model validation with defaults."""
        data = {"case_id": "CID", "status": "S"}
        model = SalesforceUpdateCase(**data)
        assert model.case_id == "CID"
        assert model.status == "S"
        assert model.description == "" # Default value

        data_with_desc = {"case_id": "CID2", "status": "S2", "description": "Desc"}
        model_with_desc = SalesforceUpdateCase(**data_with_desc)
        assert model_with_desc.description == "Desc"

    @pytest.mark.positive
    def test_salesforce_update_lead_model(self):
        """Test SalesforceUpdateLead model validation with defaults."""
        data = {"lead_id": "LID"}
        model = SalesforceUpdateLead(**data)
        assert model.lead_id == "LID"
        assert model.email == "" # Default value
        assert model.phone == "" # Default value

        data_with_values = {"lead_id": "LID2", "email": "E", "phone": "P"}
        model_with_values = SalesforceUpdateLead(**data_with_values)
        assert model_with_values.email == "E"
        assert model_with_values.phone == "P"

    @pytest.mark.positive
    def test_salesforce_input_model(self):
        """Test SalesforceInput model validation with defaults."""
        data = {"method": "M", "relative_url": "RU"}
        model = SalesforceInput(**data)
        assert model.method == "M"
        assert model.relative_url == "RU"
        assert model.params == "{}" # Default value

        data_with_params = {"method": "M2", "relative_url": "RU2", "params": '{"key": "value"}'}
        model_with_params = SalesforceInput(**data_with_params)
        assert model_with_params.params == '{"key": "value"}'

    @pytest.mark.positive
    def test_no_input_model(self):
        """Test NoInput model (should accept no input)."""
        model = NoInput()
        assert isinstance(model, NoInput)

    # Add negative tests for models if more complex validation is added later
    # e.g., testing pydantic validation errors for missing required fields
