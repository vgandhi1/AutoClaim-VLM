import pytest


@pytest.mark.dev
def test_placeholder_vlm_endpoint():
    pytest.skip("Requires SageMaker endpoint in dev.")
