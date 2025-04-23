from datetime import datetime, timedelta

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker

from discharge_docs.api.api_helper import ApiEndpoint
from discharge_docs.database.connection import get_engine
from discharge_docs.database.helper import (
    get_feedback_merged_df,
    get_generated_doc_df,
    get_request_retrieve_df,
    get_request_table,
)

load_dotenv()

SESSIONMAKER = sessionmaker(bind=get_engine())


def kpi_page():
    """Page that contains basic KPIs for the discharge documentation project"""
    st.write("## KPIs")

    if not isinstance(date_input, tuple) or len(date_input) != 2:
        st.info("Selecteer een tijdsperiode")
        return

    generated_doc_merged = get_generated_doc_df(
        date_input[0], date_input[1], SESSIONMAKER
    )
    feedback_merged = get_feedback_merged_df(date_input[0], date_input[1], SESSIONMAKER)
    request_retrieve_merged = get_request_retrieve_df(
        date_input[0], date_input[1], SESSIONMAKER
    )
    department_selection_col, _ = st.columns([1, 2])
    department_selection = department_selection_col.selectbox(
        "Kies een afdeling",
        np.insert(generated_doc_merged["department"].unique(), 0, "Alle afdelingen"),
        index=0,
    )
    if department_selection != "Alle afdelingen":
        generated_doc_merged = generated_doc_merged[
            generated_doc_merged["department"] == department_selection
        ]
        feedback_merged = feedback_merged[
            feedback_merged["department"] == department_selection
        ]
        request_retrieve_merged = request_retrieve_merged[
            request_retrieve_merged["department"] == department_selection
        ]

    metric_cols = st.columns(4)

    metric_cols[0].metric(
        "Nr gen docs: totaal",
        generated_doc_merged["generated_doc_id"].count(),
    )

    metric_cols[1].metric(
        "Nr gen docs: gisteren",
        generated_doc_merged.loc[
            generated_doc_merged.timestamp.dt.date
            == (datetime.today() - timedelta(days=1)).date(),
            "enc_id",
        ].count(),
    )

    metric_cols[2].metric(
        "Nr opnames",
        generated_doc_merged["enc_id"].nunique(),
    )

    metric_cols[3].metric(
        "Aantal feedback ontvangen",
        feedback_merged["request_feedback_id"].count(),
    )

    perc_retrieved = (
        request_retrieve_merged["enc_id"].nunique()
        / generated_doc_merged["enc_id"].nunique()
        * 100
    )
    metric_cols[0].metric("% opnames A-brief opgehaald", f"{perc_retrieved:.2f}%")

    perc_enc_lengtherror = (
        generated_doc_merged.loc[
            (generated_doc_merged["success_ind"] == "LengthError"), "enc_id"
        ].nunique()
        / generated_doc_merged["enc_id"].nunique()
        * 100
    )

    metric_cols[1].metric("% opnames te lang dossier", f"{perc_enc_lengtherror:.2f}%")

    st.write("### Status van de gegenereerde documenten per dag")
    nr_docs_chart = (
        alt.Chart(generated_doc_merged)
        .mark_bar()
        .encode(
            x=alt.X("yearmonthdate(timestamp):T", axis=alt.Axis(title="Date")),
            y=alt.Y(
                "distinct(enc_id):Q",
                axis=alt.Axis(title="Aantal documenten"),
            ),
            color=alt.Color(
                "success_ind:N",
                legend=alt.Legend(title="Success Category"),
                scale=alt.Scale(
                    domain=["Success", "LengthError", "GeneralError"],
                    range=["#32CD32", "#FFA500", "#FF0000"],  # Green, Orange, Red
                ),
            ),
        )
    )
    st.altair_chart(nr_docs_chart, use_container_width=True)

    if department_selection == "Alle afdelingen":
        st.write("### Gegenereerde documenten per afdeling per dag")
        nr_docs_dep_chart = (
            alt.Chart(generated_doc_merged)
            .mark_bar()
            .encode(
                x=alt.X("yearmonthdate(timestamp):T", axis=alt.Axis(title="Date")),
                y=alt.Y(
                    "distinct(enc_id):Q",
                    axis=alt.Axis(title="Aantal documenten"),
                ),
                color=alt.Color(
                    "department:N",
                    legend=alt.Legend(title="Afdeling"),
                ),
            )
        )
        st.altair_chart(nr_docs_dep_chart, use_container_width=True)

    st.write("### Ingevulde feedback")
    piechart_columns = st.columns(2)
    data = pd.DataFrame(
        {
            "category": [
                "Ja, deze brief heeft mij geholpen",
                "Nee, deze brief heeft mij niet geholpen",
                "Opname zonder feedback ingevuld",
            ],
            "value": [
                feedback_merged.loc[
                    feedback_merged.feedback_answer == "ja", "enc_id"
                ].nunique(),
                feedback_merged.loc[
                    feedback_merged.feedback_answer == "nee", "enc_id"
                ].nunique(),
                generated_doc_merged["encounter_id"].nunique()
                - feedback_merged["enc_id"].nunique(),
            ],
        }
    )
    data["percentage"] = data["value"] / data["value"].sum() * 100

    custom_colors = ["#32CD32", "#FF6347", "#808080"]  # Green, Red, Grey

    pie_chart_feedback = (
        alt.Chart(data)
        .mark_arc()
        .encode(
            theta=alt.Theta(field="value", type="quantitative"),
            color=alt.Color(
                field="category", type="nominal", scale=alt.Scale(range=custom_colors)
            ),
            tooltip=["category", "value", "percentage"],
        )
        .properties(width=400, height=400)
    )
    piechart_columns[0].altair_chart(pie_chart_feedback)

    data_yes_no = data[:2]
    data_yes_no.loc[:, "percentage"] = (
        data_yes_no["value"] / data_yes_no["value"].sum() * 100
    )

    pie_chart_yes_no = (
        alt.Chart(data_yes_no[:2])
        .mark_arc()
        .encode(
            theta=alt.Theta(field="value", type="quantitative"),
            color=alt.Color(
                field="category", type="nominal", scale=alt.Scale(range=custom_colors)
            ),
            tooltip=["category", "value", "percentage"],
        )
        .properties(width=400, height=400)
    )
    piechart_columns[1].altair_chart(pie_chart_yes_no)


def monitoring_page():
    """Page that contains monitoring information for the Discharge documentation
    project"""
    st.write("## Monitoring")

    if not isinstance(date_input, tuple) or len(date_input) != 2:
        st.info("Selecteer een tijdsperiode")
        return

    request = get_request_table(date_input[0], date_input[1], SESSIONMAKER)

    metric_columns = st.columns(5)
    metric_columns[0].metric("Laatste api versie", max(request["api_version"]))
    metric_columns[1].metric(
        "Laatste generatie tijd",
        request.loc[
            request["endpoint"] == ApiEndpoint.PROCESS_GENERATE_DOC.value,
            "timestamp",
        ]
        .dt.strftime("%Y-%m-%d %H:%M")
        .max(),
    )

    metric_columns[2].metric(
        "Laatste ophaal tijd",
        request.loc[
            request["endpoint"] == ApiEndpoint.RETRIEVE_DISCHARGE_DOC.value, "timestamp"
        ]
        .dt.strftime("%Y-%m-%d %H:%M")
        .max(),
    )

    metric_columns[3].metric(
        "Aantal retrieve requests",
        request.loc[
            request["endpoint"] == ApiEndpoint.RETRIEVE_DISCHARGE_DOC.value,
            "request_id",
        ].count(),
    )
    metric_columns[4].metric(
        "Aantal process requests",
        request.loc[
            request["endpoint"] == ApiEndpoint.PROCESS_GENERATE_DOC.value, "request_id"
        ].count(),
    )

    st.write("### Response codes per dag")
    response_chart = (
        alt.Chart(request)
        .mark_bar()
        .encode(
            x="yearmonthdate(timestamp):T",
            y="count()",
            color="response_code:N",
        )
    )
    st.altair_chart(response_chart, use_container_width=True)

    st.write("### Runtime van de generate API")
    runtime_chart = (
        alt.Chart(
            request[request["endpoint"] == ApiEndpoint.PROCESS_GENERATE_DOC.value]
        )
        .mark_line()
        .encode(
            x=alt.X("timestamp:T", axis=alt.Axis(title="Timestamp")),
            y=alt.Y("runtime:Q", axis=alt.Axis(title="Runtime (seconds)")),
        )
    )
    st.altair_chart(runtime_chart, use_container_width=True)

    st.write("### Runtime van de retrieve API")
    runtime_chart = (
        alt.Chart(
            request[request["endpoint"] == ApiEndpoint.RETRIEVE_DISCHARGE_DOC.value]
        )
        .mark_line()
        .encode(
            x=alt.X("timestamp:T", axis=alt.Axis(title="Timestamp")),
            y=alt.Y("runtime:Q", axis=alt.Axis(title="Runtime (seconds)")),
        )
    )
    st.altair_chart(runtime_chart, use_container_width=True)

    st.write("### Aantal Retrieve requests per dag")
    runtime_chart = (
        alt.Chart(
            request[request["endpoint"] == ApiEndpoint.RETRIEVE_DISCHARGE_DOC.value]
        )
        .mark_bar()
        .encode(
            x="yearmonthdate(timestamp):T",
            y="count()",
        )
    )
    st.altair_chart(runtime_chart, use_container_width=True)

    st.write("### Tijdstippen van retrieve API requests")
    request["hour"] = request["timestamp"].dt.hour
    frequency_chart = (
        alt.Chart(
            request[request["endpoint"] == ApiEndpoint.RETRIEVE_DISCHARGE_DOC.value]
        )
        .mark_bar()
        .encode(
            x=alt.X("hour:O", title="Uur van de dag"),
            y=alt.Y("count()", title="Aantal requests"),
        )
    )
    st.altair_chart(frequency_chart, use_container_width=True)


if __name__ == "__main__":
    st.set_page_config(
        "AIvA Discharge Documentation Generator - Admin Dashboard",
        page_icon="📈",
        layout="wide",
    )
    st.title("AIvA Discharge Documentation Generator - Admin Dashboard")

    with st.sidebar:
        default_start_date = datetime.now() - timedelta(days=14)
        default_end_date = datetime.now()
        date_input = st.date_input(
            "Selecteer een tijdsperiode",
            (default_start_date, default_end_date),
        )

    nav = st.navigation(
        [st.Page(kpi_page, title="KPIs"), st.Page(monitoring_page, title="Monitoring")]
    )
    nav.run()
