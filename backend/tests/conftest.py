import pytest


@pytest.fixture(autouse=True)
def reset_bq():
    from backend.core import bq_client
    bq_client.reset_bq_client()
    yield
    bq_client.reset_bq_client()
