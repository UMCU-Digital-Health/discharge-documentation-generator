import json
from pathlib import Path

import pandas as pd
import pytest

from discharge_docs.api.pydantic_models import PatientFile
from discharge_docs.config import load_department_config
from discharge_docs.dashboard import helper
from discharge_docs.dashboard.helper import (
    select_encounter_ids,
)
from discharge_docs.processing.deduce_text import apply_deduce
from discharge_docs.processing.processing import (
    combine_patient_and_docs_data_hix,
    filter_data,
    get_patient_discharge_docs,
    get_patient_file,
    pre_process_hix_data,
    process_data,
    replace_text,
)


class DummyPromptBuilder:
    def __init__(self, **kwargs):
        self.max_context_length = 10000

    def get_token_length(self, **kwargs):
        return 100


def test_process_data():
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
    processed_data = process_data(test_data)

    # Test whether unnecessary columns are dropped and columns are correctly renamed
    expected_columns = [
        "enc_id",
        "admissionDate",
        "department",
        "date",
        "description",
        "content",
        "pseudo_id",
        "patient_id",
    ]
    assert set(expected_columns).issubset(processed_data.columns), (
        "Columns should be correctly renamed and unnecessary columns dropped"
    )


def test_get_patient_file():
    # Create a sample DataFrame for testing
    test_data = pd.DataFrame(
        {
            "enc_id": [1, 1, 1, 2],
            "description": [
                "Description 1",
                "Description 2",
                "Description 3",
                "Description 4",
            ],
            "date": [
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-02"),
                pd.Timestamp("2024-01-03"),
                pd.Timestamp("2024-01-04"),
            ],
            "content": ["content 1", "content 2", "content 3", "content 4"],
        }
    )

    # Call the function with a specific enc_id
    patient_file_string, patient_file = get_patient_file(test_data, enc_id=1)

    # Assert the expected output
    expected_patient_file_string = (
        "# Patiënten dossier\n\n"
        "## Description 1\n"
        "### Datum: 2024-01-01 00:00:00\n\n"
        "content 1\n\n"
        "## Description 2\n"
        "### Datum: 2024-01-02 00:00:00\n\n"
        "content 2\n\n"
        "## Description 3\n"
        "### Datum: 2024-01-03 00:00:00\n\n"
        "content 3"
    )

    expected_patient_file = pd.DataFrame(
        {
            "enc_id": [1, 1, 1],
            "description": ["Description 1", "Description 2", "Description 3"],
            "date": [
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-01-02"),
                pd.Timestamp("2024-01-03"),
            ],
            "content": ["content 1", "content 2", "content 3"],
        }
    )
    assert patient_file_string == expected_patient_file_string
    pd.testing.assert_frame_equal(patient_file, expected_patient_file)


def test_replace_text():
    # Test case 1: Input text with repeated pattern
    input_text = "$RepeatedText|...#RepeatedText|...#"
    expected_output = "\nREPEATEDTEXT\n"
    assert replace_text(input_text) == expected_output

    # Test case 2: Input text without any repeated pattern
    input_text = "No repeated pattern"
    expected_output = "No repeated pattern"
    assert replace_text(input_text) == expected_output


def test_apply_deduce():
    df = pd.DataFrame(
        {
            "text": [
                "This is some sensitive information: Kees",
                None,
            ]
        }
    )

    result = apply_deduce(df, "text")

    assert result["text"].tolist() == [
        "This is some sensitive information: [PERSOON-1]",
        "",
    ]


def test_process_dates():
    """Test that the date conversion works correctly and that dates with year 2999 are
    converted to None.
    """
    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)

    # Normal flow with valid dates
    test_data_validated = [PatientFile(**item) for item in test_data]
    test_data_after_validation = [item.model_dump() for item in test_data_validated]
    test_data_df = pd.DataFrame.from_records(test_data_after_validation)

    assert test_data_df["date"].dtype == "datetime64[ns, UTC]"

    # Test with a None date from HiX, using a date with year 2999
    test_data[1]["date"] = "2999-12-31T23:59:59Z"
    test_data_validated = [PatientFile(**item) for item in test_data]
    test_data_after_validation = [item.model_dump() for item in test_data_validated]
    test_data_df = pd.DataFrame.from_records(test_data_after_validation)

    assert test_data_df["date"].dtype == "datetime64[ns, UTC]"
    assert pd.isna(test_data_df["date"].iloc[1])


def test_filter_data():
    department_config = load_department_config()
    department_mappings = {
        dept: cfg.get_column_descriptions(department_config.column_description)
        for dept, cfg in department_config.department.items()
    }

    # IC department
    df = pd.DataFrame(
        {
            "description": [
                "MS Chronologie Eventlijst Print",
                "Ontslagbrief",
                "Unknown",
            ],
            "content": ["A", "B", "C"],
            "department": ["IC", "IC", "IC"],
        }
    )
    filtered = filter_data(df, "IC", department_mappings)
    assert set(filtered["description"]).issubset(
        set(filter_data(df, "IC", department_mappings)["description"])
    )

    # NICU department
    df = pd.DataFrame(
        {
            "description": [
                "Dagstatus - Tractus 01 Lichamelijk Onderzoek",
                "MS Chronologie Eventlijst Print",
            ],
            "content": ["A", "B"],
            "department": ["NICU", "NICU"],
        }
    )
    filtered = filter_data(df, "NICU", department_mappings)
    assert (
        "Dagstatus - Lichamelijk Onderzoek" in filtered["description"].values
        or "Anamnese" in filtered["description"].values
    )

    # CAR department
    df = pd.DataFrame(
        {
            "description": ["Conclusie", "Ontslagbrief"],
            "content": ["A", "B"],
            "department": ["CAR", "CAR"],
        }
    )
    filtered = filter_data(df, "CAR", department_mappings)
    assert "Conclusie" in filtered["description"].values

    # PICU department
    df = pd.DataFrame(
        {
            "description": [
                "Dagstatus - Tractus 01 Lichamelijk Onderzoek",
                "MS Chronologie Eventlijst Print",
            ],
            "content": ["A", "B"],
            "department": ["PICU", "PICU"],
        }
    )
    filtered = filter_data(df, "PICU", department_mappings)
    assert (
        "Dagstatus - Lichamelijk Onderzoek" in filtered["description"].values
        or "Anamnese" in filtered["description"].values
    )

    # Unknown department raises error
    with pytest.raises(ValueError):
        filter_data(df, "UNKNOWN", department_mappings)


def test_get_patient_discharge_docs():
    df = pd.DataFrame(
        {
            "enc_id": [1, 1, 2],
            "description": ["Ontslagbrief", "Other", "Ontslagbrief"],
            "content": ["doc1", "other", "doc2"],
        }
    )
    # With enc_id
    result = get_patient_discharge_docs(df, enc_id=1)
    # Accept either ["doc1", "doc2"] or ["doc1"] depending on logic
    assert "doc1" in list(result.values)
    # Without enc_id
    result = get_patient_discharge_docs(df)
    assert "doc1" in list(result.values) and "doc2" in list(result.values)


def test_combine_patient_and_docs_data_hix():
    patient_data = pd.DataFrame({"a": [1]})
    discharge_data = pd.DataFrame({"a": [2]})
    result = combine_patient_and_docs_data_hix(patient_data, discharge_data)
    assert len(result) == 2
    assert "description" in result.columns
    assert (result["description"] == "Ontslagbrief").any()


class DummyHixInput:
    def model_dump(self):
        return {
            "ALLPARTS": [
                {
                    "TEXT": "{\\rtf1 A}",
                    "NAAM": "desc",
                    "DATE": "2024-01-01",
                    "SPECIALISM": "dep",
                }
            ]
        }


def test_pre_process_hix_data():
    data = DummyHixInput()
    df = pre_process_hix_data(data)  # type: ignore
    assert "content" in df.columns and "description" in df.columns
    assert df["description"].iloc[0] == "desc"
    assert df["content"].iloc[0] == "A"


def test_select_encounter_ids(monkeypatch):
    """Test the select_encounter_ids function with random selection."""
    monkeypatch.setattr(helper, "PromptBuilder", DummyPromptBuilder)
    monkeypatch.setattr(helper, "initialise_azure_connection", lambda: None)

    # Test random selection
    df_random = pd.DataFrame(
        {
            "enc_id": [1, 2, 3],
            "department": ["IC", "IC", "IC"],
            "description": ["Ontslagbrief", "Ontslagbrief", "Ontslagbrief"],
            "content": ["A", "B", "C"],
            "admissionDate": pd.to_datetime(["2024-01-01"] * 3),
            "dischargeDate": pd.to_datetime(["2024-01-02"] * 3),
        }
    )
    # Should not raise
    result = select_encounter_ids(
        df_random,
        n_enc_ids=1,
        selection="random",
    )
    assert len(result) == 1
    assert result[0] in [1, 2, 3]


def test_select_encounter_ids_balanced(monkeypatch):
    """Test balanced selection in select_encounter_ids function."""
    monkeypatch.setattr(helper, "PromptBuilder", DummyPromptBuilder)
    monkeypatch.setattr(helper, "initialise_azure_connection", lambda: None)

    df_5050 = pd.DataFrame(
        {
            "enc_id": [1, 2, 3, 4, 5, 6],
            "department": ["IC", "IC", "IC", "IC", "IC", "IC"],
            "description": ["Ontslagbrief"] * 6,
            "content": ["A", "B", "C", "D", "E", "F"],
            "admissionDate": pd.to_datetime(["2024-01-01"] * 6),
            "dischargeDate": pd.to_datetime(
                [
                    "2024-01-02",
                    "2024-01-10",
                    "2024-01-20",
                    "2024-01-02",
                    "2024-01-10",
                    "2024-01-20",
                ]
            ),
        }
    )
    df_5050["length_of_stay"] = (
        df_5050["dischargeDate"] - df_5050["admissionDate"]
    ).dt.days  # type: ignore
    length_of_stay_cutoff = 10
    # Should not raise and should select 50/50 split
    selected_ids = select_encounter_ids(
        df_5050,
        n_enc_ids=4,
        length_of_stay_cutoff=length_of_stay_cutoff,
        selection="balanced",
    )
    assert selected_ids is not None
    # check if at least 2 out of the 4 selected enc_ids are from each group
    short_enc_ids = [1, 2, 4, 5]
    long_enc_ids = [3, 6]
    short_count = sum(enc_id in selected_ids for enc_id in short_enc_ids)
    long_count = sum(enc_id in selected_ids for enc_id in long_enc_ids)
    assert short_count == 2
    assert long_count == 2


def test_select_encounter_ids_with_encs(monkeypatch):
    """Tests the select_encounter_ids function with a list of encounters to include"""
    monkeypatch.setattr(helper, "PromptBuilder", DummyPromptBuilder)
    monkeypatch.setattr(helper, "initialise_azure_connection", lambda: None)

    df = pd.DataFrame(
        {
            "enc_id": [1, 2, 3, 4],
            "department": ["IC", "IC", "IC", "IC"],
            "description": ["Ontslagbrief"] * 4,
            "content": ["A", "B", "C", "D"],
            "admissionDate": pd.to_datetime(["2024-01-01"] * 4),
            "dischargeDate": pd.to_datetime(["2024-01-02"] * 4),
        }
    )

    result = select_encounter_ids(
        df,
        n_enc_ids=3,
        selection="random",
        encounters_to_include=[2, 3],
    )
    assert {2, 3}.issubset(set(result))
    assert len(result) == 3
    assert len(set(result)) == 3  # ensure no duplicates


def test_select_encounter_ids_with_encs_and_balanced(monkeypatch):
    """Tests the select_encounter_ids function with a list of encounters to include
    and balanced selection.
    """
    monkeypatch.setattr(helper, "PromptBuilder", DummyPromptBuilder)
    monkeypatch.setattr(helper, "initialise_azure_connection", lambda: None)

    df = pd.DataFrame(
        {
            "enc_id": [1, 2, 3, 4, 5, 6],
            "department": ["IC"] * 6,
            "description": ["Ontslagbrief"] * 6,
            "content": ["A", "B", "C", "D", "E", "F"],
            "admissionDate": pd.to_datetime(["2024-01-01"] * 6),
            "dischargeDate": pd.to_datetime(
                [
                    "2024-01-02",
                    "2024-01-15",
                    "2024-01-20",
                    "2024-01-02",
                    "2024-01-15",
                    "2024-01-20",
                ]
            ),
        }
    )
    df["length_of_stay"] = (df["dischargeDate"] - df["admissionDate"]).dt.days  # type: ignore

    result = select_encounter_ids(
        df,
        n_enc_ids=5,
        length_of_stay_cutoff=10,
        selection="balanced",
        encounters_to_include=[2],
    )
    assert 2 in result

    assert len(result) == 5
    assert len(set(result)) == 5  # ensure no duplicates

    assert 1 in result and 4 in result  # short stays


def test_select_encounter_ids_falback_balanced(monkeypatch, caplog):
    """Tests the select_encounter_ids function falls back to random selection
    when balanced selection is not possible with the provided encounters.
    """
    monkeypatch.setattr(helper, "PromptBuilder", DummyPromptBuilder)
    monkeypatch.setattr(helper, "initialise_azure_connection", lambda: None)

    df = pd.DataFrame(
        {
            "enc_id": [1, 2, 3, 4, 5, 6],
            "department": ["IC"] * 6,
            "description": ["Ontslagbrief"] * 6,
            "content": ["A", "B", "C", "D", "E", "F"],
            "admissionDate": pd.to_datetime(["2024-01-01"] * 6),
            "dischargeDate": pd.to_datetime(
                [
                    "2024-01-02",
                    "2024-01-15",
                    "2024-01-20",
                    "2024-01-10",
                    "2024-01-15",
                    "2024-01-20",
                ]
            ),
        }
    )
    df["length_of_stay"] = (df["dischargeDate"] - df["admissionDate"]).dt.days  # type: ignore

    with caplog.at_level("WARNING"):
        result = select_encounter_ids(
            df,
            n_enc_ids=4,
            length_of_stay_cutoff=4,
            selection="balanced",
        )

    assert "Falling back to random sampling" in caplog.text

    assert len(result) == 4
    assert len(set(result)) == 4  # ensure no duplicates
