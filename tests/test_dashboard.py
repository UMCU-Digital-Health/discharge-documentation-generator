import dash_bootstrap_components as dbc
import pandas as pd
import pytest
from dash import html
from pandas.testing import assert_frame_equal

from discharge_docs.config import load_department_config
from discharge_docs.dashboard.helper import (
    get_authorized_patients,
    get_data_from_patient_admission,
    get_department_prompt,
    get_patients_values,
    highlight,
    load_stored_discharge_letters,
    replace_newlines,
)
from discharge_docs.dashboard.layout import (
    get_demo_layout,
    get_discharge_doc_card,
    get_GPT_card,
    get_layout_development_dashboard,
    get_navbar,
    get_patient_data_card,
    get_patient_selection_div,
)


def test_layout_functions():
    """Tests to see if the layout functions return the correct type of object"""
    assert isinstance(get_navbar(True, "test"), dbc.NavbarSimple)
    assert isinstance(get_patient_selection_div(True), dbc.Row)
    assert isinstance(get_patient_data_card("order and searchable"), dbc.Card)
    assert isinstance(get_patient_data_card("markings"), dbc.Card)
    assert isinstance(get_discharge_doc_card("placeholder", "1", "div"), dbc.Card)
    assert isinstance(get_discharge_doc_card("placeholder", "1", "markdown"), dbc.Card)
    assert isinstance(get_GPT_card(), dbc.Card)
    assert isinstance(
        get_layout_development_dashboard("system prompt", "user prompt"), html.Div
    )
    assert isinstance(get_demo_layout(), html.Div)


def test_highlight():
    """Tests the highlight function"""
    # Test highlight on str type
    highlighted_text = highlight("dit is een test string", "test")
    assert highlighted_text[0] == "dit is een "
    assert isinstance(highlighted_text[1], html.Mark)
    assert highlighted_text[2] == " string"

    # Test highlight on list type
    highlighted_text = highlight(["dit is een ", "test string"], "test")
    assert highlighted_text[0] == "dit is een "
    assert isinstance(highlighted_text[1], html.Mark)
    assert highlighted_text[2] == " string"


def test_replace_newlines():
    """Tests the replace_newlines function"""
    # Test replace_newlines on str type
    replaced_text = replace_newlines("dit is een\ntest string")
    assert replaced_text[0] == "dit is een"
    assert isinstance(replaced_text[1], html.Br)
    assert replaced_text[2] == "test string"
    assert isinstance(replaced_text[3], html.Br)

    # Test replace_newlines on list type
    replaced_text = replace_newlines(["dit is een", html.P("test string")])
    assert replaced_text[0] == "dit is een"
    assert isinstance(replaced_text[1], html.Br)
    assert isinstance(replaced_text[2], html.P)


def test_get_authorized_patients():
    """Tests if the correct patients are returned"""
    authorization_group = ["test", "test2"]
    patients_dict = {
        "test": [{"value": 1}, {"value": 2}],
        "test2": [{"value": 3}],
        "test3": [{"value": 4}],
    }
    authorized_patients, first_patient = get_authorized_patients(
        authorization_group, patients_dict
    )
    assert authorized_patients == [{"value": 1}, {"value": 2}, {"value": 3}]
    assert first_patient == "1"


def test_get_data_from_patient_admissions():
    """Tests the get_data_from_patient_admissions function"""
    admission_df = pd.DataFrame(
        {"enc_id": [1, 2, 3]},
    )
    patient_row = get_data_from_patient_admission("1", admission_df)
    assert_frame_equal(patient_row, admission_df[admission_df["enc_id"] == 1])


def test_get_department_prompt():
    """Tests the get_department_prompt function"""
    enc_ids_dict = {
        "IC": [1, 2, 3],
        "NICU": [4, 5, 6],
    }

    department_config = load_department_config()

    department_prompt, department = get_department_prompt(
        "1", enc_ids_dict, department_config
    )
    # Check that department is correct and prompt matches config
    assert department == "IC"
    assert (
        department_prompt == department_config.department[department].department_prompt
    )

    department_prompt, department = get_department_prompt(
        "4", enc_ids_dict, department_config
    )
    assert department == "NICU"
    assert (
        department_prompt == department_config.department[department].department_prompt
    )

    with pytest.raises(ValueError):
        get_department_prompt("7", enc_ids_dict, department_config)


def test_get_patients_values():
    """Tests the get_patients_values function"""
    enc_ids_dict = {
        "test": [1, 2],
        "test2": [3],
    }
    df = pd.DataFrame(
        {"enc_id": [1, 2, 3], "length_of_stay": [1, 2, 3]},
    )
    patients_values = get_patients_values(df, enc_ids_dict)
    assert patients_values["test"] == [
        {"label": "Patiënt 1 (test 1 dagen) [opname 1]", "value": 1},
        {"label": "Patiënt 2 (test 2 dagen) [opname 2]", "value": 2},
    ]
    assert patients_values["test2"] == [
        {"label": "Patiënt 1 (test2 3 dagen) [opname 3]", "value": 3},
    ]


def test_load_stored_discharge_letters():
    """Tests the load_stored_discharge_letters function"""
    df = pd.DataFrame(
        {
            "enc_id": [1, 2, 3],
            "generated_doc": [
                '{"beloop": "letter 1"}',
                '{"beloop": "letter 2"}',
                '{"beloop": "letter 3"}',
            ],
            "generation_time": ["2025-01-01", "2025-01-02", "2025-01-03"],
        }
    )
    discharge_letter = load_stored_discharge_letters(df, "1")
    assert discharge_letter.generated_doc == {"beloop": "letter 1"}
    discharge_letter = load_stored_discharge_letters(df, "5")
    assert discharge_letter.generated_doc == {
        "Geen Vooraf Gegenereerde Ontslagbrief Beschikbaar": "Er is geen opgeslagen"
        " documentatie voor deze patiënt."
    }
