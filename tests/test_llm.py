import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from MockAzureOpenAIEnv import MockAzureOpenAI

from discharge_docs.config import DEPLOYMENT_NAME_ENV, TEMPERATURE
from discharge_docs.llm.helper import DischargeLetter
from discharge_docs.llm.prompt import (
    load_department_prompt,
    load_prompts,
)
from discharge_docs.llm.prompt_builder import (
    ContextLengthError,
    GeneralError,
    JSONError,
    PromptBuilder,
)
from discharge_docs.processing.processing import get_patient_file, process_data


def test_load_prompts():
    # Test loading regular prompts
    user_prompt, system_prompt = load_prompts()
    assert isinstance(user_prompt, str)
    assert isinstance(system_prompt, str)

    # Test that the content of the prompts is not empty
    assert len(user_prompt) > 0
    assert len(system_prompt) > 0


def test_load_template_prompt():
    # Test loading template prompt for existing department NICU
    department = "NICU"
    template_prompt = load_department_prompt(department)
    assert isinstance(template_prompt, str)
    assert len(template_prompt) > 0

    # Test loading template prompt for existing department IC
    department = "IC"
    template_prompt = load_department_prompt(department)
    assert isinstance(template_prompt, str)
    assert len(template_prompt) > 0

    # Test loading template prompt for existing department CAR
    department = "CAR"
    template_prompt = load_department_prompt(department)
    assert isinstance(template_prompt, str)
    assert len(template_prompt) > 0


def test_prompt_builder():
    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name=DEPLOYMENT_NAME_ENV,
        client=MockAzureOpenAI(),
    )

    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)
        test_data = pd.DataFrame.from_records(test_data)
        dtypes = {
            "enc_id": int,
            "admissionDate": "datetime64[ns]",
            "department": str,
            "date": "datetime64[ns]",
            "description": str,
            "content": str,
            "pseudo_id": str,
            "patient_id": int,
        }
        test_data["date"] = pd.to_datetime(test_data["date"].astype(float), unit="ms")
        test_data["admissionDate"] = pd.to_datetime(
            test_data["admissionDate"].astype(float), unit="ms"
        )
        test_data = test_data.astype(dtypes)
    test_data = process_data(test_data)

    patient_file_string, patient_df = get_patient_file(test_data, 1234)
    department = patient_df["department"].values[0]
    department_prompt = load_department_prompt(department)
    general_prompt, system_prompt = load_prompts()

    discharge_letter = prompt_builder.generate_discharge_doc(
        patient_file=patient_file_string,
        department_prompt=department_prompt,
        system_prompt=system_prompt,
        general_prompt=general_prompt,
    )
    assert isinstance(discharge_letter, dict)


def test_context_length_error():
    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name="aiva-gpt",
        client=MockAzureOpenAI(),
    )
    prompt_builder.max_context_length = 10

    with pytest.raises(ContextLengthError) as e:
        prompt_builder.generate_discharge_doc(
            patient_file="This is a patient file.",
            department_prompt="This is a template prompt.",
            system_prompt="This is a system prompt.",
            general_prompt="This is a user prompt.",
        )
    assert str(e.value) == "Token length exceeds maximum context length"
    assert e.value.type == "LengthError"
    assert e.value.dutch_message == (
        "De omvang van het patientendossier is te groot geworden voor het AI model."
        " Daardoor kan er geen ontslagbrief worden gegenereerd."
        " Schrijf de ontslagbrief op de oude manier."
    )


def test_json_error():
    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name="aiva-gpt",
        client=MockAzureOpenAI(json_error=True),
    )

    with pytest.raises(JSONError) as e:
        prompt_builder.generate_discharge_doc(
            patient_file="This is a patient file.",
            department_prompt="This is a template prompt.",
            system_prompt="This is a system prompt.",
            general_prompt="This is a user prompt.",
        )
    assert str(e.value) == "Error converting response to JSON"
    assert e.value.type == "JSONError"
    assert e.value.dutch_message == (
        "Er is een fout opgetreden bij het genereren van de ontslagbrief met AI."
        " Schrijf de ontslagbrief op de oude manier."
    )


def test_general_error():
    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name="aiva-gpt",
        client=MockAzureOpenAI(general_error=True),
    )

    with pytest.raises(GeneralError) as e:
        prompt_builder.generate_discharge_doc(
            patient_file="This is a patient file.",
            department_prompt="This is a template prompt.",
            system_prompt="This is a system prompt.",
            general_prompt="This is a user prompt.",
        )
    assert str(e.value) == "Error generating discharge docs"
    assert e.value.type == "GeneralError"
    assert e.value.dutch_message == (
        "Er is een fout opgetreden bij het genereren van de ontslagbrief met AI."
        " Schrijf de ontslagbrief op de oude manier."
    )


def test_discharge_letter_format():
    # Minimal generated_doc for testing
    generated_doc = {
        "Header1": "Some content [LEEFTIJD-1]-jarige",
        "Header2": "Beloop\nSome more content",
    }
    generation_time = datetime(2025, 10, 1, 12, 0, 0)
    letter = DischargeLetter(
        generated_doc=generated_doc,
        generation_time=generation_time,
        success_indicator=True,
        error_type=None,
    )

    # Test plain format with generation time and manual filtering
    plain = letter.format(
        format_type="plain", manual_filtering=True, include_generation_time=True
    )
    assert "Generatietijd: 2025-10-01 12:00:00" in plain
    assert "[LEEFTIJD-1]-jarige" not in plain
    assert "Beloop" not in plain  # Should be filtered out

    # Test markdown format returns a list of html.Div and check structure/content
    markdown = letter.format(
        format_type="markdown", manual_filtering=True, include_generation_time=True
    )

    assert isinstance(markdown, list)
    assert len(markdown) == 3  # Generatietijd + 2 headers
    assert "Generatietijd" in str(markdown[0])
    headers = [str(div) for div in markdown]
    assert any("Header1" in h for h in headers)
    assert any("Header2" in h for h in headers)
    assert all("[LEEFTIJD-1]-jarige" not in h for h in headers)
    assert all("Beloop" not in h for h in headers)
