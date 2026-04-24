from google.cloud import bigquery
from backend.core.config import settings

_client: bigquery.Client | None = None


def get_bq_client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=settings.bq_project)
    return _client


def reset_bq_client() -> None:
    global _client
    _client = None
