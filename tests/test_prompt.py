import json
from pathlib import Path

import pandas as pd
import tomli
from MockAzureOpenAIEnv import MockAzureOpenAI

from discharge_docs.processing.processing import (
    get_patient_file,
    process_data_metavision_dp,
)
from discharge_docs.prompts.prompt import (
    load_additional_information_prompt,
    load_all_templates_prompts_into_dict,
    load_evaluatie_prompt,
    load_information_correction_prompt,
    load_information_intersection_prompt,
    load_information_union_prompt,
    load_missing_information_prompt,
    load_prompts,
    load_segment_prompt,
    load_template_prompt,
)
from discharge_docs.prompts.prompt_builder import PromptBuilder


def test_load_prompts():
    # Test loading regular prompts
    user_prompt, system_prompt = load_prompts()
    assert isinstance(user_prompt, str)
    assert isinstance(system_prompt, str)

    # Test loading iterative prompts
    user_prompt_iterative, system_prompt_iterative = load_prompts(iterative=True)
    assert isinstance(user_prompt_iterative, str)
    assert isinstance(system_prompt_iterative, str)

    # Test that the content of the prompts is not empty
    assert len(user_prompt) > 0
    assert len(system_prompt) > 0
    assert len(user_prompt_iterative) > 0
    assert len(system_prompt_iterative) > 0


def test_load_template_prompt():
    # Test loading template prompt for existing department
    department = "Neonatologie"
    template_prompt = load_template_prompt(department)
    assert isinstance(template_prompt, str)
    assert len(template_prompt) > 0


def test_prompt_builder():
    with open(
        Path(__file__).parents[1] / "src/discharge_docs/api/deployment_config.toml",
        "rb",
    ) as f:
        deployment_config_dict = tomli.load(f)
    prompt_builder = PromptBuilder(
        temperature=deployment_config_dict["TEMPERATURE"],
        deployment_name=deployment_config_dict["deployment_name"],
        client=MockAzureOpenAI,
    )

    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)
        test_data = pd.DataFrame.from_records(test_data)
        test_data = process_data_metavision_dp(test_data, nifi=True)

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
    assert isinstance(discharge_letter, list)


def test_load_evaluatie_prompt():
    evaluatie_prompt = load_evaluatie_prompt()
    assert isinstance(evaluatie_prompt, str)
    assert len(evaluatie_prompt) > 0


def test_load_all_templates_prompts_into_dict():
    # Test loading template prompts for specified departments
    departments = [
        "Neonatologie",
        "Intensive Care Centrum",
    ]
    template_prompts_dict = load_all_templates_prompts_into_dict(departments)

    assert isinstance(template_prompts_dict, dict)
    assert (
        len(template_prompts_dict) == len(departments) + 1
    )  # Including "demo" department

    for department in departments:
        assert department.lower() in template_prompts_dict
        assert isinstance(template_prompts_dict[department.lower()], str)
        assert len(template_prompts_dict[department.lower()]) > 0

    assert "demo" in template_prompts_dict
    assert isinstance(template_prompts_dict["demo"], str)
    assert len(template_prompts_dict["demo"]) > 0


def test_load_missing_information_prompt():
    missing_information_prompt = load_missing_information_prompt()
    assert isinstance(missing_information_prompt, str)
    assert len(missing_information_prompt) > 0


def test_load_additional_information_prompt():
    additional_information_prompt = load_additional_information_prompt()
    assert isinstance(additional_information_prompt, str)
    assert len(additional_information_prompt) > 0


def test_load_information_union_prompt():
    information_union_prompt = load_information_union_prompt()
    assert isinstance(information_union_prompt, str)
    assert len(information_union_prompt) > 0


def test_load_information_intersection_prompt():
    intersection_prompt = load_information_intersection_prompt()
    assert isinstance(intersection_prompt, str)
    assert len(intersection_prompt) > 0


def test_load_information_correction_prompt():
    information_correction_prompt = load_information_correction_prompt()
    assert isinstance(information_correction_prompt, str)
    assert len(information_correction_prompt) > 0


def test_load_segment_prompt():
    segment_prompt = load_segment_prompt()
    assert isinstance(segment_prompt, str)
    assert len(segment_prompt) > 0
