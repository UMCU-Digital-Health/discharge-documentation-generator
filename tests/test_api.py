import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.exceptions import HTTPException
from MockAzureOpenAIEnv import MockAzureOpenAI
from sqlalchemy.orm import Session

import discharge_docs.api.app_on_demand as app_on_demand
import discharge_docs.api.app_periodic as app_periodic
from discharge_docs.api.api_helper import remove_outdated_discharge_docs
from discharge_docs.api.app_on_demand import (
    generate_hix_discharge_docs,
    process_hix_data,
)
from discharge_docs.api.app_periodic import (
    process_and_generate_discharge_docs,
    remove_all_discharge_docs,
    retrieve_discharge_doc,
    save_feedback,
)
from discharge_docs.api.pydantic_models import (
    HixInput,
    HixOutput,
    LLMOutput,
    MetavisionPatientFile,
)


class FakeScalars:
    def all(self):
        return []


class FakeExecute:
    def scalar_one_or_none(self):
        print("requested scalar one or none...")
        return None

    def fetchall(self):
        print("requested fetchall...")
        return None

    def scalars(self):
        print("requested scalars...")
        return FakeScalars()


class FakeDB(Session):
    def commit(self):
        print("committed")

    def add(self, tmp):
        print(f"{tmp} added")

    def execute(self, stmt):
        print(f"{stmt} executed...")
        return FakeExecute()


# Test the root endpoint
@pytest.mark.asyncio
async def test_root():
    """Test the root endpoint in the API."""
    response = await app_periodic.root()
    assert response == {"message": "Hello World"}


# Test the process_and_generate_discharge_docs endpoint
@pytest.mark.asyncio
async def test_api_wrong_api_key(monkeypatch):
    """Test the process_and_generate_discharge_docs endpoint in the API."""
    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_generate", "test")
    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)

    test_data = [MetavisionPatientFile(**item) for item in test_data]

    with pytest.raises(HTTPException) as e:
        await process_and_generate_discharge_docs(test_data, FakeDB(), "wrong_api_key")
    assert e.value.status_code == 403
    assert e.value.detail == "You are not authorized to access this endpoint"


@pytest.mark.asyncio
async def test_process_and_generate_discharge_docs(monkeypatch):
    """Test the process_and_generate_discharge_docs endpoint in the API."""
    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_generate", "test")
    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)

    test_data = [MetavisionPatientFile(**item) for item in test_data]

    output = await process_and_generate_discharge_docs(test_data, FakeDB(), "test")
    assert output == {"message": "Success"}


# test the retrieve_discharge_doc endpoint
@pytest.mark.asyncio
async def test_api_retrieve_discharge_docs(monkeypatch):
    """Test the retrieve endpoint in the API."""
    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_retrieve", "test")

    output = await retrieve_discharge_doc("1234", FakeDB(), "test")
    assert isinstance(output, str)


@pytest.mark.parametrize(
    "previous_status", ["Success", "GeneralError", "JSONError", "LengthError"]
)
@pytest.mark.asyncio
async def test_api_retrieve_discharge_doc_success(monkeypatch, previous_status):
    """Test retrieving a successful discharge letter for a patient."""
    mock_data = [
        (
            '{"Letter": "Most Recent Successful Discharge Letter"}',
            9,
            "Success",
            "1234",
            "123456",
            datetime.now(),
        ),
        (
            '{"Letter": "Older Successful Discharge Letter"}',
            8,
            previous_status,
            "1234",
            "123456",
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
            None,
            9,
            f"{error}",
            "1234",
            "123456",
            datetime.now(),
        ),
        (
            '{"Letter": "Older But Successful Discharge Letter"}',
            8,
            "Success",
            "1234",
            "123456",
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
    assert "Older But Successful Discharge Letter" in output
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

    with pytest.raises(HTTPException) as e:
        await app_periodic.retrieve_discharge_doc("1234", FakeDB(), "wrong_api_key")
    assert e.value.status_code == 403
    assert e.value.detail == "You are not authorized to access this endpoint"


# Test the save_feedback endpoint
@pytest.mark.asyncio
async def test_api_save_feedback(monkeypatch):
    """Test the give_feedback endpoint in the API."""
    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_feedback", "test")

    output = await save_feedback("1_Ja", FakeDB(), "test")
    assert output == "success"


# Test the remove_outdated_discharge_docs endpoint
def test_remove_outdated_discharge_docs():
    """Test the remove_outdated_discharge_docs endpoint in the API."""
    output = remove_outdated_discharge_docs(FakeDB(), 1)
    assert output is None


# Test the remove_all_discharge_docs endpoint
@pytest.mark.asyncio
async def test_remove_all_discharge_docs(monkeypatch):
    """Test the remove_all_discharge_docs endpoint in the API."""
    monkeypatch.setattr(app_periodic, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_remove", "test")

    output = await remove_all_discharge_docs(7, FakeDB(), "test")
    assert output == {"message": "No matching discharge docs found"}


# Test on demand root
@pytest.mark.asyncio
async def test_root_on_demand():
    """Test the root endpoint in the API."""
    response = await app_on_demand.root()
    assert response == {"message": "Hello World"}


# Test process hix data
@pytest.mark.asyncio
async def test_process_hix_data(monkeypatch):
    """Test the process_hix_data endpoint in the API."""
    monkeypatch.setattr(app_on_demand, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_HIX", "test")
    with open(Path(__file__).parent / "data" / "example_hix_data.json", "r") as f:
        test_data = json.load(f)

    test_data = HixInput(**test_data)

    output = await process_hix_data(test_data, FakeDB(), "test")
    assert isinstance(output, HixOutput)


# test the generate_hix_discharge_docs endpoint
@pytest.mark.asyncio
async def test_generate_hix_discharge_docs(monkeypatch):
    """Test the generate_hix_discharge_docs endpoint in the API."""
    monkeypatch.setattr(app_on_demand, "client", MockAzureOpenAI())
    monkeypatch.setenv("X_API_KEY_HIX", "test")

    hix_output = HixOutput(department="NICU", value="Example patient file string")

    output = await generate_hix_discharge_docs(hix_output, FakeDB(), "test")
    assert isinstance(output, LLMOutput)
    assert output.message == (
        f"Deze brief is door AI gegenereerd op: "
        f"{datetime.now():%d-%m-%Y %H:%M}\n\n\n"
        "Categorie1\nBeloop1\n\nCategorie2\nBeloop2\n\n"
    )
