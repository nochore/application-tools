from unittest.mock import MagicMock

import pytest

from ....alita_tools.ado.repos.repos_wrapper import ReposApiWrapper


@pytest.mark.unit
@pytest.mark.positive
def test_run_list_files():
    ReposApiWrapper.set_active_branch = MagicMock()
    ReposApiWrapper.set_active_branch("branch-name")
    ReposApiWrapper.set_active_branch.assert_called_once_with("branch-name")
