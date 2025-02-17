# application-tools
Default set of tools available in ELITEA for Agents

# pytest
### Dependencies
- pytest-env==1.1.5
- allure-pytest==2.13.5

### pyproject.toml

```python
[tool.pytest.ini_options]
minversion = "8.3.4"
addopts = "-vvv -ra -q -p no:warnings --ignore=src/alita_tools/ado/test_plan --rootdir=src --alluredir=./allure-results"
log_cli = true
log_cli_level = "INFO"
log_format = "%(asctime)s %(levelname)s %(message)s"
log_date_format = "%Y-%m-%d %H:%M:%S"
filterwarnings = "ignore"
cache_dir = ".pytest_cache"
testpaths = [
    "tests",
    "tests/ado"
]
env = [
    "ADO_REPOS_ORGANIZATION_URL=https://dev.azure.com/<repoName>",
    "ADO_REPOS_BASE_BRANCH=master",
    "ADO_REPOS_ACTIVE_BRANCH=master",
    "ADO_REPOS_PROJECT=<project_name>",
    "ADO_REPOS_REPOSITORY_ID=<repo_id>",
    "ADO_REPOS_TOKEN=<token>"
]
```

### Run

Execute the next commnd:\
For `macOS`:\
`pytest`
