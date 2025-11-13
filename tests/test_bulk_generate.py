import pandas as pd
from MockAzureOpenAIEnv import MockAzureOpenAI

from discharge_docs.config import load_department_config
from discharge_docs.processing.bulk_generation import bulk_generate


def test_bulk_generate(monkeypatch):
    """Tests the bulk generation of discharge documents."""
    df = pd.DataFrame(
        {
            "enc_id": [1, 1, 2, 3],
            "date": ["2022-01-01", "2022-01-02", "2022-01-03", "2022-01-04"],
            "description": [
                "Description 1",
                "Description 2",
                "Description 1",
                "Description 1",
            ],
            "content": ["Content 1", "Content 2", "Content 3", "Content 4"],
            "department": ["NICU", "NICU", "NICU", "IC"],
            "length_of_stay": [5, 5, 3, 7],
        }
    )
    # Create a temp folder for saving the generated documents using tempfile
    data = bulk_generate(df, MockAzureOpenAI(), load_department_config())
    assert len(data) == 3
