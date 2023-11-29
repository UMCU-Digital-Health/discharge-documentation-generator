import os
import re
from pathlib import Path

import dash
import openai
from dash import callback_context, dcc, html
from dash.dependencies import Input, Output, State
from dotenv import load_dotenv

from discharge_docs.dashboard_helper import highlight
from discharge_docs.prompt import get_chatgpt_output

load_dotenv()
deployment_name = "model-gpt35"

openai.api_key = os.getenv("AZURE_OPENAI_KEY")
openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
openai.api_type = "azure"
openai.api_version = "2023-05-15"  # this may change in the future

external_stylesheets = ["https://codepen.io/chriddyp/pen/bWLwgP.css"]

with open(
    Path(__file__).parents[1] / "data" / "raw" / "example_patient_file_gpt.txt", "r"
) as f:
    example_patient_file = f.read()

# sequences = re.split(re.escape("\n"), example_patient_file, flags=re.IGNORECASE)
# example_patient_file_list = [html.Br(), *sequences]


app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.layout = html.Div(
    [
        # This component is invisible, only used to store intermediate calculated df
        dcc.Store(id="reply_beloop"),
        dcc.Store(id="reply_status"),
        html.H1("Ontslag documentatie demo"),
        html.Div(
            [
                html.Div(
                    [
                        html.H2("Patientdossier"),
                        html.Div(
                            children=[html.Div(example_patient_file)],
                            id="text-placeholder",
                            style={
                                "max-height": "600px",
                                "overflow-y": "scroll",
                                "background-color": "#f0f0f0",
                                "border": "1px solid #ddd",
                                "border-radius": "5px",
                                "padding": "10px",
                                "width": "85%",
                            },
                        ),
                        html.Button("Stuur naar GPT", id="submit-button"),
                    ],
                    style={
                        "width": "30%",
                        "display": "inline-block",
                        "vertical-align": "top",
                    },
                ),
                html.Div(
                    [
                        html.H2("Ontslagbrief"),
                        dcc.Loading(
                            id="loading-output",
                            children=[
                                html.Div(
                                    [
                                        html.H3("Beloop tijdens opname"),
                                        html.Div(id="beloop-output", children=[""]),
                                        html.H3("Status bij ontslag"),
                                        html.Div(id="status-output", children=[""]),
                                    ]
                                )
                            ],
                            type="default",
                        ),
                    ],
                    style={
                        "width": "30%",
                        "display": "inline-block",
                        "vertical-align": "top",
                    },
                ),
                html.Div(
                    [
                        html.H2("Controleer ontslagbrief"),
                        dcc.Markdown("Zoek naar een woord in het patientdossier:"),
                        html.Div(
                            [
                                dcc.Input(
                                    id="selected-word",
                                    type="text",
                                    placeholder="Zoek een woord in het patientdossier",
                                ),
                                html.Button("Zoek", id="zoek-button"),
                            ]
                        ),
                        dcc.Markdown("Controleer de losse stukjes GPT bronnen:"),
                        dcc.Dropdown(
                            id="selected_section",
                            options=[
                                {
                                    "label": "Beloop tijdens opname",
                                    "value": "Beloop tijdens opname",
                                },
                                {"label": "Huidige status", "value": "Huidige status"},
                            ],
                            placeholder="Selecteer een kopje",
                        ),
                        dcc.Dropdown(
                            id="selected_category",
                            options=[
                                {"label": "Respiratie", "value": "Respiratie"},
                                {"label": "Cardiologie", "value": "Cardiologie"},
                                {"label": "Neurologie", "value": "Neurologie"},
                                {"label": "Infectie", "value": "Infectie"},
                            ],
                            placeholder="Selecteer een categorie",
                        ),
                        html.Button("Controleer", id="controleer-button"),
                        html.Br(),
                        html.Button("Reset alle markeringen", id="reset-button"),
                    ],
                    style={
                        "width": "30%",
                        "display": "inline-block",
                        "vertical-align": "top",
                    },
                ),
            ]
        ),
    ]
)


@app.callback(
    [
        Output("beloop-output", "children"),
        Output("status-output", "children"),
        Output("reply_beloop", "data"),
        Output("reply_status", "data"),
    ],
    Input("submit-button", "n_clicks"),
)
def generate_ontslagbrief(n_clicks):
    if n_clicks is not None:
        reply_beloop, reply_status = get_chatgpt_output(
            patient_file=example_patient_file,
            engine=deployment_name,
        )

        beloop_output = []
        for category_pair in reply_beloop:
            beloop_output.append(
                html.Div(
                    [
                        html.Strong(category_pair["Categorie"]),
                        dcc.Markdown(category_pair["Beloop tijdens opname"]),
                    ]
                )
            )

        status_output = []
        for category_pair in reply_status:
            status_output.append(
                html.Div(
                    [
                        html.Strong(category_pair["Categorie"]),
                        dcc.Markdown(category_pair["Huidige status"]),
                    ]
                )
            )
        return beloop_output, status_output, reply_beloop, reply_status
    else:
        return "", "", "", ""


# Combined callback for handling text-placeholder logic
@app.callback(
    Output("text-placeholder", "children", allow_duplicate=True),
    [
        Input("zoek-button", "n_clicks"),
        Input("controleer-button", "n_clicks"),
        Input("reset-button", "n_clicks"),
    ],
    [
        State("selected-word", "value"),
        State("selected_section", "value"),
        State("selected_category", "value"),
        State("reply_beloop", "data"),
        State("reply_status", "data"),
    ],
    prevent_initial_call=True,
)
def combined_callback(
    zoek_n_clicks,
    controleer_n_clicks,
    reset_n_clicks,
    selected_word,
    selected_section,
    selected_category,
    reply_beloop,
    reply_status,
):
    ctx = callback_context
    triggered_id = ctx.triggered_id

    # Logic for highlight_selected_word
    if triggered_id and "zoek-button" in triggered_id:
        if zoek_n_clicks is not None and selected_word:
            output = html.Div(example_patient_file)
            output.children = highlight(example_patient_file, selected_word)
            return output

    # Logic for highlight selected section and category sources
    if triggered_id and "controleer-button" in triggered_id:
        print("triggered")
        if controleer_n_clicks is not None and selected_section and selected_category:
            if selected_section == "Beloop tijdens opname":
                response = reply_beloop
            elif selected_section == "Huidige status":
                response = reply_status
            print(response)
            # find the right dictionary in response
            selected_dict = None
            for category_pair in response:
                if category_pair["Categorie"] == selected_category:
                    selected_dict = category_pair
                    break

            print(selected_dict)
            # use selected_dict as needed
            if selected_dict is not None:
                bron_text = selected_dict["Bron:"]
                bron_list = re.findall(r"'(.*?)'", bron_text)
            else:
                print(
                    "No matching category found so GPT output is in incorrect format."
                )
            print(bron_list)
            print(bron_text)
            output = html.Div(example_patient_file)
            highlighted_sources = example_patient_file
            for bron in bron_list:
                # if there is a dot at the end of a bron, remove it
                if bron[-1] == ".":
                    bron = bron[:-1]

                print(bron)

                highlighted_sources = highlight(highlighted_sources, bron)
            output.children = highlighted_sources
            return output

    # Logic for reset_highlights
    elif triggered_id and "reset-button" in triggered_id:
        if reset_n_clicks is not None:
            return html.Div(example_patient_file)

    # Default return
    return html.Div(example_patient_file)


if __name__ == "__main__":
    app.run_server(debug=True)
