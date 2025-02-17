from unittest.mock import MagicMock, patch

import pytest

from alita_tools.ado.repos.repos_wrapper import EnvVars, ReposApiWrapper, ToolException

from ...utils import check_schema


def setup_git_client_mock():
    git_client_mock = MagicMock()
    valid_branch_mock = MagicMock(
        name="MockBranch", commit=MagicMock(commit_id="1234567890abcdef")
    )
    invalid_branch_mock = None

    def branch_side_effect(repository_id, name, project):
        if name in [
            "master",
            "refs/heads/master",
            "refs/heads/valid_source_branch",
            "refs/heads/valid_target_branch",
        ]:
            return valid_branch_mock
        else:
            return invalid_branch_mock

    git_client_mock.get_branch.side_effect = branch_side_effect

    def create_pr_side_effect(git_pull_request_to_create, repository_id, project):
        source_branch = git_pull_request_to_create["sourceRefName"]
        target_branch = git_pull_request_to_create["targetRefName"]
        source_branch_result = git_client_mock.get_branch(
            repository_id, name=source_branch, project=project
        )
        target_branch_result = git_client_mock.get_branch(
            repository_id, name=target_branch, project=project
        )

        if source_branch_result is None or target_branch_result is None:
            raise Exception(
                "ExpectedError: One or more of the source or target branches does not exist."
            )
        return MagicMock(pull_request_id=101)

    git_client_mock.create_pull_request.side_effect = create_pr_side_effect


    def create_thread_side_effect(comment_thread, repository_id, pull_request_id, project):
        return f"Commented on pull request {pull_request_id}"

    git_client_mock.create_thread.side_effect = create_thread_side_effect

    return git_client_mock


@pytest.fixture
def mock_git_client():
    return setup_git_client_mock()


@pytest.fixture
def repo_api_wrapper(mock_git_client):
    with patch(
        "alita_tools.ado.repos.repos_wrapper.GitClient", return_value=mock_git_client
    ):
        return ReposApiWrapper.from_env()


@pytest.fixture
def fresh_mock_api_method():
    def _mock_method(method_name):
        original_method = getattr(ReposApiWrapper, method_name)
        setattr(ReposApiWrapper, method_name, MagicMock())

        def _restore():
            setattr(ReposApiWrapper, method_name, original_method)
        
        return _restore

    return _mock_method


@pytest.mark.e2e
@pytest.mark.positive
def test_check_schema(repo_api_wrapper: ReposApiWrapper):
    check_schema(repo_api_wrapper)


@pytest.mark.e2e
@pytest.mark.positive
def test_environment_setup():
    missing_vars = [var.name for var in EnvVars if var.get_value() is None]
    assert not missing_vars, (
        f"Required environment variables are not set: {missing_vars}"
    )


@pytest.mark.e2e
@pytest.mark.positive
def test_api_initialization(repo_api_wrapper: ReposApiWrapper):
    assert repo_api_wrapper
    for env_var in EnvVars:
        attribute_value = getattr(repo_api_wrapper, env_var.name.lower())
        env_value = env_var.get_value()
        assert attribute_value == env_value, (
            f"Mismatch for {env_var.name}: Expected {env_value}, got {attribute_value}"
        )


@pytest.mark.e2e
@pytest.mark.positive
def test_run_list_branches_in_repo(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.list_branches_in_repo = MagicMock()
    repo_api_wrapper.run("list_branches_in_repo")
    ReposApiWrapper.list_branches_in_repo.assert_called_once()


@pytest.mark.e2e
@pytest.mark.positive
def test_run_set_active_branch(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.set_active_branch = MagicMock()
    repo_api_wrapper.run("set_active_branch", "branch")
    ReposApiWrapper.set_active_branch.assert_called_once_with("branch")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_list_files(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.list_files = MagicMock()
    repo_api_wrapper.run("list_files", "/")
    ReposApiWrapper.list_files.assert_called_once_with("/")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_list_open_pull_requests(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.list_open_pull_requests = MagicMock()
    repo_api_wrapper.run("list_open_pull_requests")
    ReposApiWrapper.list_open_pull_requests.assert_called_once()


@pytest.mark.e2e
@pytest.mark.positive
def test_run_get_pull_request(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.get_pull_request = MagicMock()
    repo_api_wrapper.run("get_pull_request", "1")
    ReposApiWrapper.get_pull_request.assert_called_once_with("1")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_list_pull_request_diffs(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.list_pull_request_diffs = MagicMock()
    repo_api_wrapper.run("list_pull_request_files", "1")
    ReposApiWrapper.list_pull_request_diffs.assert_called_once_with("1")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_create_branch(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.create_branch = MagicMock()
    repo_api_wrapper.run("create_branch", "branch-name")
    ReposApiWrapper.create_branch.assert_called_once_with("branch-name")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_read_file(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.read_file = MagicMock()
    repo_api_wrapper.run("read_file", "file-path")
    ReposApiWrapper.read_file.assert_called_once_with("file-path")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_create_file(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.create_file = MagicMock()
    repo_api_wrapper.run("create_file", "file-path", "file-contents", "branch-name")
    ReposApiWrapper.create_file.assert_called_once_with(
        "file-path", "file-contents", "branch-name"
    )


@pytest.mark.e2e
@pytest.mark.positive
def test_run_update_file(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.update_file = MagicMock()
    repo_api_wrapper.run("update_file", "branch-name", "file-path", "update_query")
    ReposApiWrapper.update_file.assert_called_once_with(
        "branch-name", "file-path", "update_query"
    )


@pytest.mark.e2e
@pytest.mark.positive
def test_run_delete_file(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.delete_file = MagicMock()
    repo_api_wrapper.run("delete_file", "branch-name", "file-path")
    ReposApiWrapper.delete_file.assert_called_once_with("branch-name", "file-path")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_get_work_items(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.get_work_items = MagicMock()
    repo_api_wrapper.run("get_work_items", "1")
    ReposApiWrapper.get_work_items.assert_called_once_with("1")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_comment_on_pull_request(repo_api_wrapper: ReposApiWrapper):
    ReposApiWrapper.comment_on_pull_request = MagicMock()
    repo_api_wrapper.run("comment_on_pull_request", "comment-query")
    ReposApiWrapper.comment_on_pull_request.assert_called_once_with("comment-query")


@pytest.mark.e2e
@pytest.mark.positive
def test_run_create_pr(repo_api_wrapper: ReposApiWrapper, fresh_mock_api_method):
    restore = fresh_mock_api_method('create_pr')
    repo_api_wrapper.run(
        "create_pull_request", "pull-request-title", "pull-request-body", "branch-name"
    )
    ReposApiWrapper.create_pr.assert_called_once_with(
        "pull-request-title", "pull-request-body", "branch-name"
    )
    restore()


@pytest.mark.e2e
@pytest.mark.positive
def test_create_pr_success(repo_api_wrapper: ReposApiWrapper):
    repo_api_wrapper.active_branch = "valid_source_branch"
    response = repo_api_wrapper.create_pr(
        pull_request_title="Test Successful PR",
        pull_request_body="This is a test for creating a successful PR",
        branch_name="valid_target_branch",
    )
    assert "Successfully created PR with ID 101" in response


@pytest.mark.e2e
@pytest.mark.negative
def test_create_pr_fail_no_such_branch(repo_api_wrapper: ReposApiWrapper):
    repo_api_wrapper.active_branch = "valid_source_branch"
    with pytest.raises(Exception) as exc_info:
        repo_api_wrapper.create_pr(
            pull_request_title="Fail PR",
            pull_request_body="This should fail because of a non-existing target branch",
            branch_name="invalid_target_branch",
        )
    assert (
        "ExpectedError: One or more of the source or target branches does not exist."
        in str(exc_info.value)
    )


@pytest.mark.skip(reason="no run due to mock")
@pytest.mark.e2e
@pytest.mark.positive
def test_comment_on_pr_success(repo_api_wrapper: ReposApiWrapper):
    comment_query = "1\n\nThis is a successful comment"
    response = repo_api_wrapper.comment_on_pull_request(comment_query)
    assert "Commented on pull request 1" in response


@pytest.mark.skip(reason="no run due to mock")
@pytest.mark.e2e
@pytest.mark.negative
def test_comment_on_pr_fail_invalid_query(repo_api_wrapper: ReposApiWrapper):
    comment_query = "invalid-query-format"
    response = repo_api_wrapper.comment_on_pull_request(comment_query)
        
    assert isinstance(response, ToolException), "Expected method to return a ToolException instance"
    assert "Unable to make comment due to error:\ninvalid literal for int() with base 10: 'invalid-query-format'" in str(response), "Error message not in response"