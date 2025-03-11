from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from MockAzureOpenAIEnv import MockAzureOpenAI

from discharge_docs.processing.bulk_generation import bulk_generate


def test_bulk_generate(monkeypatch):
    """Tests the bulk generation of discharge documents."""
    enc_ids_dict = {
        "NICU": [1, 2],
        "IC": [3],
    }
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
        }
    )
    # Create a temp folder for saving the generated documents using tempfile
    with TemporaryDirectory() as temp_dir:
        save_folder = Path(temp_dir)
        bulk_generate(df, save_folder, enc_ids_dict, MockAzureOpenAI())
