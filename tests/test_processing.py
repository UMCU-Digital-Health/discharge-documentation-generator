import json
from pathlib import Path

import pandas as pd
import pytest

from discharge_docs.processing.deduce_text import apply_deduce
from discharge_docs.processing.processing import (
    get_patient_file,
    process_data_metavision_dp,
    replace_text,
)


def test_process_data_nifi_true():
    with open(Path(__file__).parent / "data" / "example_data.json", "r") as f:
        test_data = json.load(f)
        test_data = pd.DataFrame.from_records(test_data)

    try:
        processed_data = process_data_metavision_dp(test_data, nifi=True)
    except Exception as e:
        pytest.fail(f"Error processing data: {e}")

    # Test whether unnecessary columns are dropped and columns are correctly renamed
    expected_columns = [
        "enc_id",
        "admissionDate",
        "department",
        "time",
        "date",
        "description",
        "value",
        "patient_number",
    ]
    # assert if all expected columns are in processed data
    assert set(expected_columns).issubset(
        processed_data
    ), "Columns should be correctly renamed and unnecessary columns dropped"


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
            "value": ["Value 1", "Value 2", "Value 3", "Value 4"],
        }
    )

    # Call the function with a specific enc_id
    patient_file_string, patient_file = get_patient_file(test_data, enc_id=1)

    # Assert the expected output
    expected_patient_file_string = (
        "# Patienten dossier\n\n"
        "## Description 1\n"
        "### Datum: 2024-01-01 00:00:00\n\n"
        "Value 1\n\n"
        "## Description 2\n"
        "### Datum: 2024-01-02 00:00:00\n\n"
        "Value 2\n\n"
        "## Description 3\n"
        "### Datum: 2024-01-03 00:00:00\n\n"
        "Value 3"
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
            "value": ["Value 1", "Value 2", "Value 3"],
        }
    )
    assert patient_file_string == expected_patient_file_string
    print(patient_file)
    print(expected_patient_file)
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
