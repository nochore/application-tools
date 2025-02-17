import logging
import os
import shutil
import sys
import subprocess

import pytest


ALLURE_RESULTS_DIR = "allure-results"
ALLURE_REPORT_DIR = "docs"

class IgnoreKeywordFilter(logging.Filter):
    def __init__(self, keyword="ExpectedError"):
        super().__init__()
        self.keyword = keyword

    def filter(self, record):
        return self.keyword not in record.getMessage()


@pytest.fixture(scope="session")
def check_env_vars(en_vars):
    """Ensure all required environment variables are set."""
    missing_vars = [var.name for var in en_vars if var.get_value() is None]
    if missing_vars:
        pytest.fail(f"Required environment variables are not set: {missing_vars}\n")


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Hook to add custom configurations or plugins."""
    sys.path.append("./src") # TODO: need to handle properly

    logging_filter = IgnoreKeywordFilter()
    handlers = [h for h in logging.getLogger().handlers]
    for handler in handlers:
        handler.addFilter(logging_filter)
    
    if not os.path.exists(ALLURE_RESULTS_DIR):
        os.makedirs(ALLURE_RESULTS_DIR)
    config.option.allure_report_dir = ALLURE_RESULTS_DIR


@pytest.fixture(scope="session", autouse=True)
def test_suite_cleanup_thing():
    yield


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Hook called after all tests finish and generate Allure report."""
    print(f"\nTest suite finished.\nExit status: {exitstatus}\n")
    generate_allure_report()


def generate_allure_report():
    """Generate Allure report from the results and clean up the results directory."""
    if os.path.isdir(ALLURE_RESULTS_DIR):
        if not os.path.exists(ALLURE_REPORT_DIR):
            os.makedirs(ALLURE_REPORT_DIR)

        try:
            subprocess.run(['allure', 'generate', ALLURE_RESULTS_DIR, '--output', ALLURE_REPORT_DIR, '-c'], check=True)
            print("Allure report generated.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to generate Allure report.\nError: {str(e)}\n", e)
        finally:
            # Clean up the allure-results directory after report generation
            shutil.rmtree(ALLURE_RESULTS_DIR)
            print(f"Cleaned up '{ALLURE_RESULTS_DIR}' directory.")
    else:
        print(f"No Allure results found for generating report in '{ALLURE_RESULTS_DIR}'.")
