import pytest


@pytest.mark.dev
def test_placeholder_requires_aws():
    pytest.skip("Run in a deployed dev environment with AWS_INTEGRATION=1 (not enabled in CI).")
