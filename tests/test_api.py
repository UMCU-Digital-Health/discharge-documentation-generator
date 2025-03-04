import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.exceptions import HTTPException
from MockAzureOpenAIEnv import MockAzureOpenAI
from pydantic import ValidationError
from sqlalchemy.orm import Session

import discharge_docs.api.app_periodic as app_periodic
from discharge_docs.api.app_periodic import (
    process_and_generate_discharge_docs,
)
from discharge_docs.api.pydantic_models import (
    MetavisionPatientFile,
)


class FakeExecute:
    def all(self):
        print("requested all results...")
        return []

    def scalar_one_or_none(self):
        print("requested scalar one or none...")
        return None

    def fetchone(self):
        print("requested fetchone...")
        return None

    def fetchall(self):
        print("requested fetchall...")
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
async def test_api_wrong_api_key(monkeypatch):
    """Test the process_and_generate_discharge_docs endpoint in the API."""
    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)

    try:
        test_data = [MetavisionPatientFile(**item) for item in test_data]
    except ValidationError as e:
        pytest.fail(f"JSON data does not match PatientFile schema: {e}")

    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_generate", "test")

    try:
        await process_and_generate_discharge_docs(test_data, FakeDB(), "wrong_api_key")
    except HTTPException as e:
        assert e.status_code == 403
        assert e.detail == "You are not authorized to access this endpoint"


@pytest.mark.asyncio
async def test_api_retrieve_discharge_docs(monkeypatch):
    """Test the retrieve endpoint in the API."""
    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    output = await app_periodic.retrieve_discharge_doc("1234", FakeDB(), "test")
    assert isinstance(output, str)


@pytest.mark.parametrize(
    "previous_status", ["Success", "GeneralError", "JSONError", "LengthError"]
)
@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_success(monkeypatch, previous_status):
    """Test retrieving a successful discharge letter for a patient."""
    mock_data = [
        (
            "Most Recent Successful Discharge Letter",
            9,
            "Success",
            "1234",
            datetime.now(),
        ),
        (
            "Older Discharge Letter",
            8,
            previous_status,
            "1234",
            datetime.now() - timedelta(days=1),
        ),
    ]
    mock_data = sorted(mock_data, key=lambda x: x[2], reverse=True)

    class FakeExecuteSuccess(FakeExecute):
        def fetchall(self):
            print("requested fetchall with results...")
            return mock_data

    class FakeDBWithResults(FakeDB):
        def execute(self, stmt):
            print(f"{stmt} executed with fetchall data...")
            return FakeExecuteSuccess()

    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")
    output = await app_periodic.retrieve_discharge_doc(
        "1234", FakeDBWithResults(), "test"
    )

    assert isinstance(output, str)
    assert "Most Recent Successful Discharge Letter" in output
    assert "Older Discharge Letter" not in output


@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_no_results(monkeypatch):
    """Test retrieving discharge docs with no results for a patient."""
    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    output = await app_periodic.retrieve_discharge_doc("1234", FakeDB(), "test")

    assert isinstance(output, str)
    assert "Er is geen ontslagbrief in de database gevonden" in output


@pytest.mark.asyncio
@pytest.mark.parametrize("error", ["GeneralError", "JSONError", "LengthError"])
@pytest.mark.parametrize("days", [2, 8])
async def test_api_retrieve_discharge_doc_older_letter(monkeypatch, error, days):
    """Test retrieving older discharge docs as newer has an error."""
    mock_data = [
        (
            "No discharge letter due to error",
            9,
            f"{error}",
            "1234",
            datetime.now(),
        ),
        (
            f"Older But Successful Discharge Letter ({days} days ago)",
            8,
            "Success",
            "1234",
            datetime.now() - timedelta(days=days),
        ),
    ]
    mock_data = sorted(mock_data, key=lambda x: x[1], reverse=True)

    class FakeExecuteError(FakeExecute):
        def fetchall(self):
            print("requested fetchall with Error...")
            return mock_data

    class FakeDBWithError(FakeDB):
        def execute(self, stmt):
            print(f"{stmt} executed with Error data...")
            return FakeExecuteError()

    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    output = await app_periodic.retrieve_discharge_doc(
        "1234", FakeDBWithError(), "test"
    )

    assert isinstance(output, str)
    assert f"Older But Successful Discharge Letter ({days} days ago)" in output
    assert "No discharge letter due to error" not in output
    if error == "LengthError":
        assert (
            "Dit komt doordat het patientendossier te lang is geworden voor het AI "
            "model." in output
        )
    if days == 2:
        assert (
            "NB Let erop dat deze AI-brief niet afgelopen nacht is gegenereerd, maar"
            f" {days} dagen geleden." in output
        )
    elif days == 8:
        assert (
            "NB Let erop dat deze AI-brief meer dan een week geleden is gegenereerd, "
            f"namelijk {days} dagen geleden." in output
        )


@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_wrong_api_key(monkeypatch):
    """Test retrieving discharge docs with an incorrect API key."""
    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    try:
        await app_periodic.retrieve_discharge_doc("1234", FakeDB(), "wrong_api_key")
    except HTTPException as e:
        assert e.status_code == 403
        assert e.detail == "You are not authorized to access this endpoint"
