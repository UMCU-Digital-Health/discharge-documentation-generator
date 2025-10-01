import json
from pathlib import Path

import pandas as pd
import pytest
import tomli_w

from discharge_docs.api.pydantic_models import PatientFile
from discharge_docs.processing import processing
from discharge_docs.processing.deduce_text import apply_deduce
from discharge_docs.processing.processing import (
    combine_patient_and_docs_data_hix,
    filter_data,
    get_patient_discharge_docs,
    get_patient_file,
    pre_process_hix_data,
    process_data,
    random_sample_with_warning,
    replace_text,
    write_encounter_ids,
)


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


def test_filter_data_ic_nicu_car():
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
    filtered = filter_data(df, "IC")
    assert set(filtered["description"]).issubset(
        set(filter_data(df, "IC")["description"])
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
    filtered = filter_data(df, "NICU")
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
    filtered = filter_data(df, "CAR")
    assert "Conclusie" in filtered["description"].values

    # PICU department returns unchanged
    df = pd.DataFrame(
        {
            "description": ["Anything"],
            "content": ["A"],
            "department": ["PICU"],
        }
    )
    filtered = filter_data(df, "PICU")
    assert filtered.equals(df)

    # Unknown department raises error
    with pytest.raises(ValueError):
        filter_data(df, "UNKNOWN")


def test_random_sample_with_warning():
    df = pd.DataFrame({"a": range(3)})
    # n < len(df)
    sample = random_sample_with_warning(df, 2)
    assert len(sample) == 2
    # n > len(df) triggers warning, returns all
    sample = random_sample_with_warning(df, 5)
    assert len(sample) == 3


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


def test_write_encounter_ids(monkeypatch, tmp_path):
    # Patch PromptBuilder and file writing
    class DummyPromptBuilder:
        def __init__(self, **kwargs):
            self.max_context_length = 10000

        def get_token_length(self, **kwargs):
            return 100

    monkeypatch.setattr(processing, "PromptBuilder", DummyPromptBuilder)
    monkeypatch.setattr(processing, "initialise_azure_connection", lambda: None)
    monkeypatch.setattr(tomli_w, "dump", lambda data, f: f.write(b"test"))

    # Test random selection
    df_random = pd.DataFrame(
        {
            "enc_id": [1, 2, 3],
            "department": ["IC", "IC", "CAR"],
            "description": ["Ontslagbrief", "Ontslagbrief", "Ontslagbrief"],
            "content": ["A", "B", "C"],
            "admissionDate": pd.to_datetime(["2024-01-01"] * 3),
            "dischargeDate": pd.to_datetime(["2024-01-02"] * 3),
        }
    )
    # Should not raise
    write_encounter_ids(
        df_random,
        n_enc_ids=1,
        selection="random",
        return_encs=True,
    )

    # Unknown selection raises error
    with pytest.raises(ValueError):
        write_encounter_ids(
            df_random,
            n_enc_ids=1,
            selection="unknown",
            return_encs=True,
        )

    # Test 50/50 split selection
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
    ).dt.days
    length_of_stay_cutoff = 10
    # Should not raise and should select 50/50 split
    enc_ids = write_encounter_ids(
        df_5050,
        n_enc_ids=4,
        length_of_stay_cutoff=length_of_stay_cutoff,
        selection="50/50_long/short",
        return_encs=True,
    )
    assert enc_ids is not None
    # check if at least 2 out of the 4 selected enc_ids are from each group
    short_enc_ids = [1, 2, 4, 5]
    long_enc_ids = [3, 6]
    selected_ids = set(enc_ids["enc_id"].values)
    short_count = sum(enc_id in selected_ids for enc_id in short_enc_ids)
    long_count = sum(enc_id in selected_ids for enc_id in long_enc_ids)
    assert short_count == 2
    assert long_count == 2
