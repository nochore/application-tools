import pytest

from pydantic import ValidationError

from alita_tools.qtest.tool import QtestAction
from alita_tools.qtest.api_wrapper import QtestApiWrapper


@pytest.mark.unit
@pytest.mark.qtest
class TestQtestAction:
    @pytest.mark.positive
    def test_qtest_action_init(self):
        """Test successful initialization of QtestAction."""
        action = QtestAction(
            api_wrapper=QtestApiWrapper(base_url="http://test.mock", qtest_project_id=1, qtest_api_token="token"),
            name="test_action",
            mode="test_mode",
            description="Test Description",
        )
        assert action.name == "test_action"
        assert action.mode == "test_mode"
        assert action.description == "Test Description"

    @pytest.mark.positive
    def test_remove_spaces(self):
        """Test removing spaces from action name."""
        action = QtestAction(
            api_wrapper=QtestApiWrapper(base_url="http://test.mock", qtest_project_id=1, qtest_api_token="token"),
            name="test action with spaces",
            mode="test_mode",
            description="Test Description",
        )
        assert action.name == "testactionwithspaces"

    @pytest.mark.negative
    def test_invalid_qtest_action_init(self):
        """Test initialization of QtestAction with invalid input."""
        with pytest.raises(TypeError):
            QtestAction(
                api_wrapper="invalid_wrapper",  # type: ignore
                name="test_action",
                mode="test_mode",
                description="Test Description",
            )

