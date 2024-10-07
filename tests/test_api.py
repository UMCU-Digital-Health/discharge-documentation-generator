import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.exceptions import HTTPException
from MockAzureOpenAIEnv import MockAzureOpenAI
from pydantic import ValidationError
from sqlalchemy.orm import Session

import discharge_docs.api.app as app
from discharge_docs.api.app import (
    PatientFile,
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
async def test_api_discharge_docs(monkeypatch):
    """Test the process_and_generate_discharge_docs endpoint in the API."""
    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)
        test_data = [PatientFile(**item) for item in test_data]

    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_generate", "test")
    output = await process_and_generate_discharge_docs(test_data, FakeDB(), "test")
    assert output["message"] == "Success"
    assert isinstance(output["discharge_letter"], str)


@pytest.mark.asyncio
async def test_api_remove_discharge_docs(monkeypatch):
    """Test the remove_old_discharge_docs endpoint in the API."""
    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_remove", "test")
    output = await remove_old_discharge_docs(datetime(2023, 1, 1), FakeDB(), "test")
    assert output == {"message": "Success"}


@pytest.mark.asyncio
async def test_api_wrong_api_key(monkeypatch):
    """Test the process_and_generate_discharge_docs endpoint in the API."""
    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)

    try:
        test_data = [PatientFile(**item) for item in test_data]
    except ValidationError as e:
        pytest.fail(f"JSON data does not match PatientFile schema: {e}")

    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_generate", "test")

    try:
        await process_and_generate_discharge_docs(test_data, FakeDB(), "wrong_api_key")
    except HTTPException as e:
        assert e.status_code == 403
        assert e.detail == "You are not authorized to access this endpoint"


@pytest.mark.asyncio
async def test_api_retrieve_discharge_docs(monkeypatch):
    """Test the retrieve endpoint in the API."""
    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    output = await app.retrieve_discharge_doc("test_patient_id", FakeDB(), "test")
    assert isinstance(output, str)


@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_success(monkeypatch):
    """Test retrieving a successful discharge letter for a patient."""
    mock_data = [
        (
            "Discharge letter content",
            "enc123",
            1,
            "Success",
            datetime.now() - timedelta(days=8),
        ),
        (
            "Discharge letter content",
            "enc123",
            2,
            "Success",
            datetime.now() - timedelta(days=7),
        ),
        (
            "Discharge letter content",
            "enc123",
            3,
            "Success",
            datetime.now() - timedelta(days=6),
        ),
        (
            "Discharge letter content",
            "enc123",
            4,
            "Success",
            datetime.now() - timedelta(days=5),
        ),
        (
            "Discharge letter content",
            "enc123",
            5,
            "Success",
            datetime.now() - timedelta(days=4),
        ),
        (
            "Discharge letter content",
            "enc123",
            6,
            "Success",
            datetime.now() - timedelta(days=3),
        ),
        (
            "Discharge letter content",
            "enc123",
            7,
            "Success",
            datetime.now() - timedelta(days=2),
        ),
        (
            "Discharge Letter content",
            "enc123",
            8,
            "Success",
            datetime.now() - timedelta(days=1),
        ),
        (
            "Most Recent Successful Discharge Letter",
            "enc123",
            9,
            "Success",
            datetime.now(),
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

    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")
    output = await app.retrieve_discharge_doc(
        "test_patient_id", FakeDBWithResults(), "test"
    )

    assert isinstance(output, str)
    assert "Most Recent Successful Discharge Letter" in output


@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_no_results(monkeypatch):
    """Test retrieving discharge docs with no results for a patient."""
    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    output = await app.retrieve_discharge_doc("test_patient_id", FakeDB(), "test")

    assert isinstance(output, str)
    assert "Er is geen ontslagbrief in de database gevonden" in output


@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_older_letter(monkeypatch):
    """Test retrieving discharge docs with a LengthError."""
    mock_data = [
        (
            "Discharge letter content",
            "enc123",
            1,
            "Success",
            datetime.now() - timedelta(days=8),
        ),
        (
            "Discharge letter content",
            "enc123",
            2,
            "Success",
            datetime.now() - timedelta(days=7),
        ),
        (
            "Discharge letter content",
            "enc123",
            3,
            "Success",
            datetime.now() - timedelta(days=6),
        ),
        (
            "Discharge letter content",
            "enc123",
            4,
            "Success",
            datetime.now() - timedelta(days=5),
        ),
        (
            "Discharge letter content",
            "enc123",
            5,
            "Success",
            datetime.now() - timedelta(days=4),
        ),
        (
            "Discharge letter content",
            "enc123",
            6,
            "Success",
            datetime.now() - timedelta(days=3),
        ),
        (
            "Discharge letter content",
            "enc123",
            7,
            "Success",
            datetime.now() - timedelta(days=2),
        ),
        (
            "Most Recent Successful Discharge Letter",
            "enc123",
            8,
            "Success",
            datetime.now() - timedelta(days=1),
        ),
        (
            "Too Long Discharge Letter",
            "enc123",
            9,
            "LengthError",
            datetime.now(),
        ),
    ]
    mock_data = sorted(mock_data, key=lambda x: x[2], reverse=True)

    class FakeExecuteLengthError(FakeExecute):
        def fetchall(self):
            print("requested fetchall with LengthError...")
            return mock_data

    class FakeDBWithLengthError(FakeDB):
        def execute(self, stmt):
            print(f"{stmt} executed with LengthError data...")
            return FakeExecuteLengthError()

    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    output = await app.retrieve_discharge_doc(
        "test_patient_id", FakeDBWithLengthError(), "test"
    )

    assert isinstance(output, str)
    assert "Most Recent Successful Discharge Letter" in output


@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_outdated(monkeypatch):
    """Test retrieving an outdated discharge letter."""
    mock_data = [
        (
            "Discharge Letter Content",
            "enc123",
            1,
            "Success",
            datetime.now() - timedelta(days=8),
        ),
        (
            "Discharge Letter Content",
            "enc123",
            2,
            "Success",
            datetime.now() - timedelta(days=7),
        ),
        (
            "Discharge Letter Content",
            "enc123",
            3,
            "Success",
            datetime.now() - timedelta(days=6),
        ),
        (
            "Discharge Letter Content",
            "enc123",
            4,
            "Success",
            datetime.now() - timedelta(days=5),
        ),
        (
            "Discharge Letter Content",
            "enc123",
            5,
            "Success",
            datetime.now() - timedelta(days=4),
        ),
        (
            "Discharge Letter Content",
            "enc123",
            6,
            "Success",
            datetime.now() - timedelta(days=3),
        ),
        (
            "Most Recent Discharge Letter Content",
            "enc123",
            7,
            "Success",
            datetime.now() - timedelta(days=2),
        ),
        (
            "",
            "enc123",
            8,
            "GeneralError",
            datetime.now() - timedelta(days=1),
        ),
        (
            "",
            "enc123",
            9,
            "GeneralError",
            datetime.now(),
        ),
    ]
    mock_data = sorted(mock_data, key=lambda x: x[2], reverse=True)

    class FakeExecuteOutdated(FakeExecute):
        def fetchall(self):
            print("requested fetchall with outdated data...")
            return mock_data

    class FakeDBWithOutdatedData(FakeDB):
        def execute(self, stmt):
            print(f"{stmt} executed with outdated data...")
            return FakeExecuteOutdated()

    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    output = await app.retrieve_discharge_doc(
        "test_patient_id", FakeDBWithOutdatedData(), "test"
    )

    assert isinstance(output, str)
    assert "NB Let erop dat deze brief niet afgelopen nacht is gegenereerd" in output
    assert "Most Recent Discharge Letter Content" in output


@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_wrong_api_key(monkeypatch):
    """Test retrieving discharge docs with an incorrect API key."""
    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    try:
        await app.retrieve_discharge_doc("test_patient_id", FakeDB(), "wrong_api_key")
    except HTTPException as e:
        assert e.status_code == 403
        assert e.detail == "You are not authorized to access this endpoint"


@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc__general_error_then_success(
    monkeypatch,
):
    """Test retrieving discharge docs with first a GeneralError, then a success"""

    mock_data = [
        ("", "enc123", 1, "GeneralError", datetime.now() - timedelta(days=8)),
        ("", "enc123", 2, "GeneralError", datetime.now() - timedelta(days=7)),
        ("", "enc123", 3, "GeneralError", datetime.now() - timedelta(days=6)),
        ("", "enc123", 4, "GeneralError", datetime.now() - timedelta(days=5)),
        ("", "enc123", 5, "GeneralError", datetime.now() - timedelta(days=4)),
        ("", "enc123", 6, "GeneralError", datetime.now() - timedelta(days=3)),
        ("", "enc123", 7, "GeneralError", datetime.now() - timedelta(days=2)),
        (
            "Successful Discharge Letter",
            "enc123",
            8,
            "Success",
            datetime.now() - timedelta(days=1),
        ),
        (
            "Most Recent Successful Discharge Letter",
            "enc123",
            9,
            "Success",
            datetime.now(),
        ),
    ]
    mock_data = sorted(mock_data, key=lambda x: x[2], reverse=True)

    class FakeExecuteEveryDayEntry(FakeExecute):
        def fetchall(self):
            print(
                "requested fetchall with entries for every day over more than a week..."
            )
            return mock_data

    class FakeDBEveryDayEntry(FakeDB):
        def execute(self, stmt):
            print(f"{stmt} executed with entries for every day...")
            return FakeExecuteEveryDayEntry()

    # Use the mocked DB session and mock Azure client
    monkeypatch.setattr(app, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")
    output = await app.retrieve_discharge_doc(
        "test_patient_id", FakeDBEveryDayEntry(), "test"
    )

    assert isinstance(output, str)
    assert "Most Recent Successful Discharge Letter" in output
