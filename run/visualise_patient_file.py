from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
from dash import ctx, dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from discharge_docs.dashboard.helper import (
    highlight,
)
from discharge_docs.processing.processing import (
    get_patient_discharge_docs,
    get_patient_file,
)

# load data from parquet
df = pd.read_parquet(
    Path(__file__).parents[1]
    / "data"
    / "processed"
    / "combined_data_for_visualisation.parquet"
)

# define the app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
application = app.server  # Neccessary for debugging in vscode, no further use

# degine UMCU colors
colors = {
    "white": "#FFFFFF",
    "umcu_blue": "#1191fa",
    "umcu_dark_blue": "#004285",
    "umcu_light_blue": "#e0f2ff",
    "umcu_orange": "#fc6039",
    "umcu_light_orange": "#fdbfaf",
    "black": "#000000",
}
# Define the layout of the app
app.layout = html.Div(
    children=[
        html.H1(
            "Bekijk een patiëntendossier",
            style={
                "color": colors["white"],
                "backgroundColor": colors["umcu_blue"],
                "borderRadius": "15px",
                "text-indent": "20px",
                "padding": "20px",
                "text-align": "center",
            },
        ),
        html.H3("Selecteer afdeling:"),
        dcc.Dropdown(
            id="department_dropdown",
            options=df.department.unique(),
            value=df.department.unique(),
            style={"width": "100%"},
            multi=True,
        ),
        html.H3("Selecteer patiënt opname:"),
        dcc.Dropdown(
            id="patient_admission_dropdown",
            options=[],
            value=[],
            style={"width": "100%"},
        ),
        html.H3("Selecteer deel van het patiëntendossier"),
        html.Label(html.B("Welke datum wil je bekijken?")),
        html.Div(
            [
                html.Button(
                    "Vorige",
                    id="previous_date_button",
                    style={
                        "width": "30%",
                        "margin-right": "10px",
                        "border-radius": "10px",
                    },
                ),
                dcc.Dropdown(
                    id="date_dropdown",
                    options=[],
                    style={"width": "100%"},
                ),
                html.Button(
                    "Volgende",
                    id="next_date_button",
                    style={
                        "width": "30%",
                        "margin-left": "10px",
                        "border-radius": "10px",
                    },
                ),
            ],
            style={
                "display": "flex",
            },
        ),
        dcc.Checklist(
            id="date_checklist",
            options=["Bekijk de data van de gehele opname (alle datums)"],
            value=[],
        ),
        html.Br(),
        html.Label(
            html.B("Selecteer welke delen van het patiëntendossier je wilt bekijken:")
        ),
        dcc.Dropdown(
            id="description_dropdown",
            options=[],
            value=[],
            multi=True,
            style={"width": "100%"},
        ),
        html.Div(
            [
                html.Button(
                    "Selecteer alle opties",
                    id="select_all_button",
                    style={
                        "margin-right": "5px",
                        "border-radius": "10px",
                    },
                ),
                html.Button(
                    "Deselecteer alle opties",
                    id="deselect_all_button",
                    style={
                        "margin-left": "5px",
                        "border-radius": "10px",
                    },
                ),
            ],
            style={"flex-direction": "row", "display": "flex"},
        ),
        html.Br(),
        html.Div(
            [
                html.Div(
                    [
                        html.H2("Patiëntendossier:"),
                        dcc.Input(
                            id="search_bar",
                            type="text",
                            placeholder="Zoek naar een woord in het patiëntendossier",
                            style={"width": "100%", "margin-bottom": "10px"},
                        ),
                        dcc.Dropdown(
                            id="sorting_dropdown",
                            options=[
                                {
                                    "label": "Sort by date",
                                    "value": "sort_by_date",
                                },
                                {
                                    "label": "Sort by code",
                                    "value": "sort_by_code",
                                },
                            ],
                            value="sort_by_code",
                            style={
                                "width": "50%",
                                "float": "right",
                            },
                        ),
                        html.Br(),
                        html.Div(
                            ["Placeholder for patient file"],
                            id="output_value",
                            style={
                                "width": "100%",
                                "padding": "10px",
                                "border-radius": "10px",
                                "background-color": "whitesmoke",
                            },
                        ),
                    ],
                    style={
                        "width": "50%",
                        "padding-right": "10px",
                    },
                ),
                html.Div(
                    [
                        html.H2(
                            "Originele ontslagbrief:",
                            style={
                                "width": "100%",
                            },
                        ),
                        dcc.Markdown(
                            ["Placeholder for original discharge letter"],
                            id="output_original_discharge_documentation",
                            style={
                                "width": "100%",
                                "padding": "10px",
                                "border-radius": "10px",
                                "background-color": "whitesmoke",
                            },
                        ),
                    ],
                    style={
                        "width": "50%",
                        "padding-left": "10px",
                    },
                ),
            ],
            style={
                "display": "flex",
                "flex-direction": "row",
            },
        ),
    ],
)


@app.callback(
    [
        Output("patient_admission_dropdown", "options"),
        Output("patient_admission_dropdown", "value"),
    ],
    [Input("department_dropdown", "value")],
)
def update_patient_admission_dropdown(selected_department: str) -> tuple:
    """
    Update the options for the patient admission dropdown based on the selected
    department.

    Parameters
    ----------
    selected_department : str
        The selected department.

    Returns
    -------
    list
        The updated list of options for the patient admission dropdown.
    list
        The selected value for the patient admission dropdown.
    """
    if selected_department is None:
        return [], []
    else:
        df_filtered = df[df["department"].isin(selected_department)]
        df_filtered = df_filtered.drop_duplicates(subset="enc_id", keep="first")
        patient_admission_options = [
            {"label": row.label, "value": row.enc_id}
            for row in df_filtered.itertuples(index=False)
        ]
        return patient_admission_options, patient_admission_options[0]["value"]


@app.callback(
    [Output("date_dropdown", "options"), Output("date_dropdown", "value")],
    [
        Input("patient_admission_dropdown", "value"),
        Input("previous_date_button", "n_clicks"),
        Input("next_date_button", "n_clicks"),
    ],
    [State("date_dropdown", "value")],
)
def update_date_dropdown_combined(
    selected_patient_admission: str,
    previous_clicks: int,
    next_clicks: int,
    current_date: str,
):
    """
    Update the options and value for the date dropdown based on the selected patient
    admission and interaction with previous and next buttons.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.
    previous_clicks : int
        Number of clicks on the 'previous_date_button'.
    next_clicks : int
        Number of clicks on the 'next_date_button'.
    current_date : str
        Current value of the 'date_dropdown'.

    Returns
    -------
    tuple
        First element is the list of options for the date dropdown.
        Second element is the selected (or updated) value for the date dropdown.
    """
    data = df[df["enc_id"] == selected_patient_admission]
    date_options = [
        {"label": date.date(), "value": date} for date in data["date"].unique()
    ]

    changed_id = ctx.triggered_id

    updated_date = date_options[0]["value"] if date_options else None

    if changed_id == "previous_date_button":
        prev_dates = data[data["date"] < current_date]["date"]
        if not prev_dates.empty:
            updated_date = prev_dates.iloc[-1]
    elif changed_id == "next_date_button":
        next_dates = data[data["date"] > current_date]["date"]
        if not next_dates.empty:
            updated_date = next_dates.iloc[0]
    elif changed_id == "patient_admission_dropdown":
        updated_date = date_options[0]["value"] if date_options else None

    if not date_options:
        raise PreventUpdate

    return date_options, updated_date


@app.callback(
    Output("description_dropdown", "options"),
    [Input("patient_admission_dropdown", "value")],
)
def update_description_dropdown(selected_patient_admission: str) -> list:
    """
    Update the options for the description dropdown based on the selected patient
    admission.

    Parameters
    ----------
    selected_patient_admission : str
        The selected patient admission.

    Returns
    -------
    list
        The updated list of options for the description dropdown.
    """
    data = df[df["enc_id"] == selected_patient_admission]
    patient_file_df = get_patient_file(df=data)[1]
    description_options = np.sort(patient_file_df["description"].unique())
    return description_options


@app.callback(
    Output("description_dropdown", "value"),
    [
        Input("select_all_button", "n_clicks"),
        Input("deselect_all_button", "n_clicks"),
    ],
    [State("description_dropdown", "options")],
)
def handle_select_button_clicks(
    select_all_clicks: int, deselect_all_clicks: int, options: list[str]
) -> list:
    """
    Handle action for select all and deselect all buttons for selecting the
    sections shown.

    Args:
        select_all_clicks (int): nr of times the select all button is clicked.
        deselect_all_clicks (int): nr of times deselect all button is clicked.
        options (list): List of options for the description dropdown.

    Returns:
        list: Updated value for the description dropdown.
    """
    button_id = ctx.triggered_id

    if button_id == "select_all_button":
        return options
    elif button_id == "deselect_all_button":
        return []
    else:
        raise PreventUpdate


@app.callback(
    Output("output_value", "children"),
    [
        Input("patient_admission_dropdown", "value"),
        Input("date_dropdown", "value"),
        Input("date_checklist", "value"),
        Input("description_dropdown", "value"),
        Input("sorting_dropdown", "value"),
        Input("search_bar", "value"),
    ],
)
def display_value(
    selected_patient_admission: str,
    selected_date: str,
    selected_all_dates: bool,
    selected_description: list,
    sort_dropdown_choice: str,
    search_bar_input: str,
) -> list:
    """_summary_

    Parameters
    ----------
    selected_patient_admission : str
        _description_
    selected_date : str
        _description_
    selected_all_dates : bool
        _description_
    selected_description : list
        _description_
    sort_dropdown_choice: str
        _description_

    Returns
    -------
    list
        _description_
    """
    if (
        selected_description is None
        or selected_date is None
        or selected_patient_admission is None
    ):
        return [""]
    data = df[df["enc_id"] == selected_patient_admission]
    if selected_all_dates:
        patient_file = data[data["description"].isin(selected_description)].sort_values(
            by=["date", "description"]
        )
    else:
        patient_file = data[
            (data["date"] == selected_date)
            & (data["description"].isin(selected_description))
        ].sort_values(by=["date", "description"])

    if sort_dropdown_choice == "sort_by_date":
        patient_file = patient_file.sort_values(by=["date", "description"])
    elif sort_dropdown_choice == "sort_by_code":
        patient_file = patient_file.sort_values(by=["description", "date"])

    if patient_file.empty:
        return ["De geselecteerde data is niet ingevuld voor deze patient."]
    else:
        returnable = []
        for index in patient_file.index:
            returnable.append(
                html.B(
                    str(
                        patient_file.loc[index, "description"]
                        + " - "
                        + str(patient_file.loc[index, "date"].date())
                    )
                )
            )
            returnable.append(html.Br())
            returnable.append(patient_file.loc[index, "value"])
            returnable.append(html.Br())

        if search_bar_input is not None:
            returnable = highlight(returnable, search_bar_input)

        return returnable


@app.callback(
    Output("output_original_discharge_documentation", "children"),
    [
        Input("patient_admission_dropdown", "value"),
    ],
)
def display_discharge_documentation(selected_patient_admission: str) -> list:
    """
    Display the discharge documentation for the selected patient admission.

    Parameters:
    ----------
     selected_patient_admission : str
        The selected patient admission.

    Returns:
    -------
    list
        The discharge documentation for the selected patient admission.
    """
    if selected_patient_admission is None:
        return [""]

    data = df[df["enc_id"] == selected_patient_admission]
    discharge_documentation = get_patient_discharge_docs(df=data)
    return discharge_documentation


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True, port=8051)
