import json
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session
from test_evaluate_docs import MockAzureOpenAI

import discharge_docs.api.app as app
from discharge_docs.api.app import (
    process_and_generate_discharge_docs,
    remove_old_discharge_docs,
)


class FakeExecute:
    def all(self):
        print("requested all results...")
        return []

    def scalar_one_or_none(self):
        print("requested scalar one or none...")
        return None

    @property
    def rowcount(self):
        return 0


class FakeDB(Session):
    def commit(self):
        print("committed")

    def merge(self, table):
        print(f"{table} merged...")

    def add(self, tmp):
        print(f"{tmp} added")

    def execute(self, stmt):
        print(f"{stmt} executed...")
        return FakeExecute()

    def scalars(self, stmt):
        execute_res = FakeExecute()
        print(f"{stmt} executed (with scalars)...")
        return execute_res

    def get(self, table, index):
        print(f"Requesting {table} at index {index}...")
        return None


@pytest.mark.asyncio
async def test_api_discharge_docs(monkeypatch):
    """Test the process_and_generate_discharge_docs endpoint in the API."""
    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)

    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    output = await process_and_generate_discharge_docs(test_data, FakeDB())
    assert output == {"message": "Success"}


@pytest.mark.asyncio
async def test_api_remove_discharge_docs(monkeypatch):
    """Test the remove_old_discharge_docs endpoint in the API."""
    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    output = await remove_old_discharge_docs(datetime(2023, 1, 1), FakeDB())
    assert output == {"message": "Success"}
