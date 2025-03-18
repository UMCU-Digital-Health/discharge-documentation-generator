import json
from pathlib import Path

import pandas as pd
import pytest
from MockAzureOpenAIEnv import MockAzureOpenAI

from discharge_docs.config import DEPLOYMENT_NAME_ACC, TEMPERATURE
from discharge_docs.llm.prompt import (
    load_all_templates_prompts_into_dict,
    load_prompts,
    load_template_prompt,
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
    template_prompt = load_template_prompt(department)
    assert isinstance(template_prompt, str)
    assert len(template_prompt) > 0

    # Test loading template prompt for existing department IC
    department = "IC"
    template_prompt = load_template_prompt(department)
    assert isinstance(template_prompt, str)
    assert len(template_prompt) > 0

    # Test loading template prompt for existing department CAR
    department = "CAR"
    template_prompt = load_template_prompt(department)
    assert isinstance(template_prompt, str)
    assert len(template_prompt) > 0


def test_prompt_builder():
    prompt_builder = PromptBuilder(
        temperature=TEMPERATURE,
        deployment_name=DEPLOYMENT_NAME_ACC,
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
    template_prompt = load_template_prompt(department)
    user_prompt, system_prompt = load_prompts()

    discharge_letter = prompt_builder.generate_discharge_doc(
        patient_file=patient_file_string,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        template_prompt=template_prompt,
    )
    assert isinstance(discharge_letter, dict)


def test_load_all_templates_prompts_into_dict():
    departments = ["NICU", "IC", "CAR"]
    template_prompts_dict = load_all_templates_prompts_into_dict(departments)

    assert isinstance(template_prompts_dict, dict)
    assert (
        len(template_prompts_dict) == len(departments) + 1
    )  # Including "demo" department

    for department in departments:
        assert department in template_prompts_dict
        assert isinstance(template_prompts_dict[department], str)
        assert len(template_prompts_dict[department]) > 0

    assert "DEMO" in template_prompts_dict
    assert isinstance(template_prompts_dict["DEMO"], str)
    assert len(template_prompts_dict["DEMO"]) > 0


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
            system_prompt="This is a system prompt.",
            user_prompt="This is a user prompt.",
            template_prompt="This is a template prompt.",
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
            system_prompt="This is a system prompt.",
            user_prompt="This is a user prompt.",
            template_prompt="This is a template prompt.",
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
            system_prompt="This is a system prompt.",
            user_prompt="This is a user prompt.",
            template_prompt="This is a template prompt.",
        )
    assert str(e.value) == "Error generating discharge docs"
    assert e.value.type == "GeneralError"
    assert e.value.dutch_message == (
        "Er is een fout opgetreden bij het genereren van de ontslagbrief met AI."
        " Schrijf de ontslagbrief op de oude manier."
    )
