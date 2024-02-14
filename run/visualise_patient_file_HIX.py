from pathlib import Path

import dash
import numpy as np
import pandas as pd
from dash import ctx, dcc, html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

# Replace this with your actual data
df_HIX = pd.read_parquet(
    Path(__file__).parents[1] / "data" / "processed" / "HiX_data.parquet"
)

"""Requirements for df_HIX:
- df_HIX should be a pandas dataframe
- df_HIX should contain the following columns:
    - enc_id: the encounter id of the patient
    - date: the date of the input
    - description: the description of the input
    - department: the department of the input
    - value: the value of the input
    - length_of_stay: the length of stay of the patient
"""


app = dash.Dash(__name__)
application = app.server  # Neccessary for debugging in vscode, no further use
# Define the layout of the app
app.layout = html.Div(
    [
        html.H1("View a patient file from HIX"),
        html.H3("Select department:"),
        dcc.Checklist(
            id="department_checklist",
            options=["CAR", "Psychiatrie"],
            value=["CAR", "Psychiatrie"],
        ),
        html.H3("Select encouter:"),
        html.Div(
            [
                html.Button(
                    "Previous",
                    id="previous_enc_button",
                    style={"width": "30%"},
                ),
                dcc.Dropdown(
                    id="enc_id_dropdown",
                    options=[
                        {"label": str(enc_id), "value": enc_id}
                        for enc_id in df_HIX["enc_id"].unique()
                    ],
                    value=df_HIX["enc_id"].iloc[1],
                    style={"width": "100%"},
                ),
                html.Button("Next", id="next_enc_button", style={"width": "30%"}),
            ],
            style={"display": "flex", "width": "40%"},
        ),
        html.Div(id="Encounter_info_div"),
        html.H3("Select date:"),
        html.Div(
            [
                html.Button(
                    "Previous",
                    id="previous_date_button",
                    style={"width": "30%"},
                ),
                dcc.Dropdown(
                    id="date_dropdown",
                    style={"width": "100%"},
                ),
                html.Button("Next", id="next_date_button", style={"width": "30%"}),
            ],
            style={"display": "flex", "width": "40%"},
        ),
        dcc.Checklist(id="date_checklist", options=["View all dates"], value=[]),
        html.H3("Select which section of the patient file you want to see:"),
        dcc.Checklist(
            id="description_dropdown",
            options=np.sort(df_HIX.description.unique()),
        ),
        html.Div(
            [
                html.Button("Selecteer alle opties", id="select_all_button"),
                html.Button("Deselecteer alle opties", id="deselect_all_button"),
            ],
            style={"width": "40%"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.H2("Resulting Patient File:"),
                        dcc.Checklist(
                            id="sorting_checklist",
                            options=["Sort by code"],
                            value=[],
                        ),
                        html.Br(),
                        html.Div(
                            ["placeholder "],
                            id="output_value",
                        ),
                    ],
                    style={"width": "50%"},
                ),
                html.Div(
                    [
                        html.H2("Discharge Documentation:"),
                        dcc.Markdown(
                            ["Placeholder for discharge documentation"],
                            id="output_discharge_documentation",
                        ),
                    ],
                    style={"width": "50%"},
                ),
            ],
            style={"display": "flex", "flex-direction": "row"},
        ),
    ]
)


@app.callback(
    Output("enc_id_dropdown", "value"),
    [
        Input("previous_enc_button", "n_clicks"),
        Input("next_enc_button", "n_clicks"),
        Input("department_checklist", "value"),
    ],
    [State("enc_id_dropdown", "value")],
)
def update_enc_dropdown(
    previous_clicks: int,
    next_clicks: int,
    selected_departments: list,
    current_enc_id: str,
) -> str:
    """
    Update the value of the 'enc_id_dropdown' based on user interaction with
    previous and next buttons.

    Parameters
    ----------
    previous_clicks : int
        Number of clicks on the 'previous_enc_button'.
    next_clicks : int
        Number of clicks on the 'next_enc_button'.
    selected_departments : list
        List of selected departments from the 'department_checklist'.
    current_enc_id : str
        Current value of the 'enc_id_dropdown'.

    Returns
    -------
    str
        Updated value for the 'enc_id_dropdown'.

    Raises
    ------
    PreventUpdate
        If no button is clicked.

    """
    changed_id = ctx.triggered_id
    if changed_id == "previous_enc_button":
        return df_HIX[
            (df_HIX["enc_id"] < current_enc_id)
            & (df_HIX["department"].isin(selected_departments))
        ]["enc_id"].iloc[-1]
    elif changed_id == "next_enc_button":
        return df_HIX[
            (df_HIX["enc_id"] > current_enc_id)
            & (df_HIX["department"].isin(selected_departments))
        ]["enc_id"].iloc[0]
    else:
        raise PreventUpdate


@app.callback(
    Output("Encounter_info_div", "children"),
    [Input("enc_id_dropdown", "value")],
)
def get_encounter_info(selected_enc_id: int) -> list:
    """
    Retrieves encounter information for the selected encounter ID.

    Parameters
    ----------
    selected_enc_id : str
        The selected encounter ID.

    Returns
    -------
    list
        A list containing a string with info about the selected encounter.
    """
    patient_file = df_HIX[df_HIX["enc_id"] == selected_enc_id]
    return [
        f"The selected encounter {selected_enc_id} is from the department"
        + f" {patient_file.department.iloc[0]} and has a length of stay of"
        + f" {patient_file.length_of_stay.iloc[0]} days."
    ]


@app.callback(
    Output("date_dropdown", "options"),
    [Input("enc_id_dropdown", "value")],
)
def update_date_options(
    selected_enc_id: int,
) -> list:
    """
    Update the date options based on the selected encounter ID.

    This function generates a list of dictionaries,
    each representing a date option for a given encounter ID.
    These options are used to populate a dropdown menu in a web application.

    Parameters
    ----------
    selected_enc_id : int
        The selected encounter ID.

    Returns
    -------
    list of dict
        A list of dictionaries containing the date options.
        Each dictionary has two keys: 'label' and 'value'.
        'label' is a string representation of the date.
        'value' is the actual date object (datetime.date)
    """
    date_options = [
        {"label": str(date), "value": date}
        for date in df_HIX[df_HIX["enc_id"] == selected_enc_id]["date"].unique()
    ]
    return date_options


@app.callback(
    Output("date_dropdown", "value"),
    [
        Input("previous_date_button", "n_clicks"),
        Input("next_date_button", "n_clicks"),
    ],
    [State("date_dropdown", "value")],
)
def update_date_dropdown(
    previous_clicks: int, next_clicks: int, current_date: str
) -> str:
    """
    Update the value of the 'enc_id_dropdown' based on user interaction with
    previous and next buttons.

    Parameters
    ----------
    previous_clicks : int
        Number of clicks on the 'previous_date_button'.
    next_clicks : int
        Number of clicks on the 'next_date_button'.
    current_date : str
        Current value of the 'date_dropdown'.

    Returns
    -------
    str
        Updated value for the 'date_dropdown'.

    Raises
    ------
    PreventUpdate
        If no button is clicked.

    """
    changed_id = ctx.triggered_id
    if changed_id == "previous_date_button":
        return df_HIX[df_HIX["date"] < current_date]["date"].iloc[-1]
    elif changed_id == "next_date_button":
        return df_HIX[df_HIX["date"] > current_date]["date"].iloc[0]
    else:
        raise PreventUpdate


# Common callback function for both buttons select and deselect all
@app.callback(
    Output("description_dropdown", "value"),
    [
        Input("select_all_button", "n_clicks"),
        Input("deselect_all_button", "n_clicks"),
    ],
    [State("description_dropdown", "options")],
)
def handle_button_clicks(
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
    if button_id == "deselect_all_button":
        return []

    raise PreventUpdate


# show the value based on the selected date(s) and enc_id
@app.callback(
    Output("output_value", "children"),
    [
        Input("enc_id_dropdown", "value"),
        Input("date_dropdown", "value"),
        Input("date_checklist", "value"),
        Input("description_dropdown", "value"),
        Input("sorting_checklist", "value"),
    ],
)
def display_value(
    selected_enc_id: str,
    selected_date: str,
    selected_all_dates: bool,
    selected_description: list,
    sort_by_checklist: list,
) -> list:
    """
    Display the patient file information based on the selected filters.

    Parameters:
    - selected_enc_id (str): The selected encounter ID.
    - selected_date (str): The selected date.
    - selected_all_dates (bool): Flag indicating whether all dates considered.
    - selected_description (list): The selected descriptions.
    - sort_by_checklist (list): The selected sorting options.

    Returns:
    - list: The formatted patient file information to be displayed.
    """
    if selected_description is None or selected_date is None or selected_enc_id is None:
        return [""]
    if selected_all_dates:
        patient_file = df_HIX[
            (df_HIX["enc_id"] == selected_enc_id)
            & (df_HIX["description"].isin(selected_description))
        ].sort_values(by=["date", "description"])
    else:
        patient_file = df_HIX[
            (df_HIX["enc_id"] == selected_enc_id)
            & (df_HIX["date"] == selected_date)
            & (df_HIX["description"].isin(selected_description))
        ].sort_values(by=["date", "description"])

    if "Sort by code" in sort_by_checklist:
        patient_file = patient_file.sort_values(by=["description", "date"])

    if patient_file.empty:
        return ["This value is empty."]
    else:
        returnable = []
        for index in patient_file.index:
            returnable.append(
                html.B(
                    str(
                        patient_file.loc[index, "description"]
                        + "-"
                        + str(patient_file.loc[index, "date"])
                    )
                )
            )
            returnable.append(html.Br())
            returnable.append(str(patient_file.loc[index, "value"]))
            returnable.append(html.Br())
        return returnable


@app.callback(
    Output("output_discharge_documentation", "children"),
    [
        Input("enc_id_dropdown", "value"),
    ],
)
def display_discharge_documentation(selected_enc_id: str) -> list:
    """
    Display the discharge documentation for the selected encounter ID.

    Parameters:
    ----------
    selected_enc_id : str
        The selected encounter ID.

    Returns:
    -------
    list
        The discharge documentation for the selected encounter ID,
        or a message if no documentation is found.
    """
    if selected_enc_id is None:
        return [""]
    discharge_documentation = df_HIX[
        (df_HIX["enc_id"] == selected_enc_id)
        & (df_HIX["description"].isin(["Ontslagbrief"]))
    ].sort_values(by=["date", "description"])

    if discharge_documentation.empty:
        return ["No discharge documentation found."]
    else:
        return discharge_documentation.value


# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)
