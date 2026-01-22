import logging
from datetime import datetime, timedelta
from typing import Literal, cast

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker
from umcu_ai_utils.database_connection import get_engine

from discharge_docs.config import setup_root_logger
from discharge_docs.dashboard.admin_helper import (
    create_department_selection,
    get_original_discharge_docs,
    get_time_measurements,
    process_comparison_jaccard_for_trend,
    process_comparison_with_jaccard,
    process_time_measurements_for_detail_analysis,
    process_time_measurements_for_trend_analysis,
    visualise_jaccard_comparison,
    visualise_jaccard_trend,
    visualise_time_measurements_detail,
    visualise_time_measurements_trend,
)
from discharge_docs.database.helper import (
    get_feedback_table,
    get_generated_doc_table,
    get_request_generate_table,
    get_request_retrieve_table,
)
from discharge_docs.database.models import Request

load_dotenv()

logger = logging.getLogger(__name__)
setup_root_logger()


def kpi_page():
    """Page that contains basic KPIs for the discharge documentation project"""
    st.write("## KPIs")

    if not isinstance(date_input, tuple) or len(date_input) != 2:
        st.info("Selecteer een tijdsperiode")
        return

    generated_doc_table = get_generated_doc_table(
        date_input[0], date_input[1], SESSIONMAKER
    )

    if generated_doc_table.empty:
        st.warning(
            "Geen gegenereerde documenten gevonden voor de geselecteerde periode."
        )
        logger.warning("No generated docs found for the selected period.")
        return

    feedback_table = get_feedback_table(date_input[0], date_input[1], SESSIONMAKER)
    request_retrieve_table = get_request_retrieve_table(
        date_input[0], date_input[1], SESSIONMAKER
    )
    department_selection = create_department_selection(
        generated_doc_table["department"].unique().tolist()
    )
    if department_selection != "Alle afdelingen":
        generated_doc_table = generated_doc_table[
            generated_doc_table["department"] == department_selection
        ]
        feedback_table = feedback_table[
            feedback_table["department"] == department_selection
        ]
        request_retrieve_table = request_retrieve_table[
            request_retrieve_table["department"] == department_selection
        ]

    metric_cols = st.columns(4)

    metric_cols[0].metric(
        "Nr gen docs: totaal",
        generated_doc_table["generated_doc_id"].count(),
    )

    metric_cols[1].metric(
        "Nr gen docs: gisteren",
        generated_doc_table.loc[
            pd.to_datetime(generated_doc_table["timestamp"]).dt.date
            == (datetime.today() - timedelta(days=1)).date(),
            "enc_id",
        ].count(),
    )

    metric_cols[2].metric(
        "Nr opnames",
        generated_doc_table["enc_id"].nunique(),
    )

    metric_cols[3].metric(
        "Aantal feedback ontvangen",
        feedback_table["request_feedback_id"].count(),
    )

    retrieved_enc_ids = set(request_retrieve_table["enc_id"])
    generated_enc_ids = set(generated_doc_table["enc_id"])

    # Remove enc_ids from retrieve requests that were not generated in the same period
    retrieved_enc_ids = retrieved_enc_ids & generated_enc_ids
    perc_retrieved = len(retrieved_enc_ids) / len(generated_enc_ids) * 100
    metric_cols[0].metric("% opnames AI-brief opgehaald", f"{perc_retrieved:.2f}%")

    perc_enc_lengtherror = (
        generated_doc_table.loc[
            (generated_doc_table["success_ind"] == "LengthError"), "enc_id"
        ].nunique()
        / generated_doc_table["enc_id"].nunique()
        * 100
    )

    metric_cols[1].metric("% opnames te lang dossier", f"{perc_enc_lengtherror:.2f}%")

    st.write("### Status van de gegenereerde documenten per dag")
    nr_docs_chart = (
        alt.Chart(generated_doc_table)
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
    st.altair_chart(nr_docs_chart)

    if department_selection == "Alle afdelingen":
        st.write("### Gegenereerde documenten per afdeling per dag")
        nr_docs_dep_chart = (
            alt.Chart(generated_doc_table)
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
        st.altair_chart(nr_docs_dep_chart)

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
                feedback_table.loc[
                    feedback_table.feedback_answer == "ja", "enc_id"
                ].nunique(),
                feedback_table.loc[
                    feedback_table.feedback_answer == "nee", "enc_id"
                ].nunique(),
                generated_doc_table["encounter_id"].nunique()
                - feedback_table["enc_id"].nunique(),
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

    request_retrieve = get_request_retrieve_table(
        date_input[0], date_input[1], SESSIONMAKER
    ).drop_duplicates()
    request_generate = get_request_generate_table(
        date_input[0], date_input[1], SESSIONMAKER
    ).drop_duplicates()

    if request_generate.empty:
        st.warning("Geen gegenereerde requests gevonden voor de geselecteerde periode.")
        logger.warning("No generated requests found for the selected period.")
        return

    if request_retrieve.empty:
        st.warning("Geen retrieve requests gevonden voor de geselecteerde periode.")
        logger.warning("No retrieve requests found for the selected period.")
        return

    department_selection = create_department_selection(
        request_generate["department"].unique().tolist()
    )
    if department_selection != "Alle afdelingen":
        request_retrieve = request_retrieve[
            request_retrieve["department"] == department_selection
        ]
        request_generate = request_generate[
            request_generate["department"] == department_selection
        ]

    metric_columns = st.columns(5)
    metric_columns[0].metric("Laatste api versie", max(request_generate["api_version"]))
    metric_columns[1].metric(
        "Laatste generatie tijd",
        pd.to_datetime(request_generate["timestamp"])
        .dt.strftime("%Y-%m-%d %H:%M")
        .max(),
    )

    metric_columns[2].metric(
        "Laatste ophaal tijd",
        pd.to_datetime(request_retrieve["timestamp"])
        .dt.strftime("%Y-%m-%d %H:%M")
        .max(),
    )

    metric_columns[3].metric(
        "Aantal retrieve requests",
        request_retrieve["request_id"].nunique(),
    )
    metric_columns[4].metric(
        "Aantal process requests",
        request_generate["request_id"].nunique(),
    )

    st.write("### Runtime van de generate API")
    runtime_chart = (
        alt.Chart(request_generate)
        .mark_line()
        .encode(
            x=alt.X("timestamp:T", axis=alt.Axis(title="Timestamp")),
            y=alt.Y("runtime:Q", axis=alt.Axis(title="Runtime (seconds)")),
        )
    )
    st.altair_chart(runtime_chart)

    st.write("### Runtime van de retrieve API")
    runtime_chart = (
        alt.Chart(request_retrieve)
        .mark_line()
        .encode(
            x=alt.X("timestamp:T", axis=alt.Axis(title="Timestamp")),
            y=alt.Y("runtime:Q", axis=alt.Axis(title="Runtime (seconds)")),
        )
    )
    st.altair_chart(runtime_chart)

    st.write("### Aantal Retrieve requests per dag")
    request_retrieve["success"] = request_retrieve["enc_id"].notnull()
    runtime_chart = (
        alt.Chart(request_retrieve)
        .mark_bar()
        .encode(
            x="yearmonthdate(timestamp):T",
            y="count()",
            color=alt.Color(
                "success:N",
                legend=alt.Legend(title="Success Indicator"),
            ),
        )
    )
    st.altair_chart(runtime_chart)

    st.write("### Tijdstippen van retrieve API requests")
    request_retrieve["hour"] = pd.to_datetime(request_retrieve["timestamp"]).dt.hour
    frequency_chart = (
        alt.Chart(request_retrieve)
        .mark_bar()
        .encode(
            x=alt.X("hour:O", title="Uur van de dag"),
            y=alt.Y("count()", title="Aantal requests"),
        )
    )
    st.altair_chart(frequency_chart)


def pms_page():
    """Page that contains PMS analysis"""
    st.write("## Post Market Surveillance (PMS) Analysis")

    if not isinstance(date_input, tuple) or len(date_input) != 2:
        st.info("Selecteer een tijdsperiode")
        return

    generated_discharge_docs = get_generated_doc_table(
        date_input[0], date_input[1], SESSIONMAKER
    )

    if generated_discharge_docs.empty:
        st.warning(
            "Geen gegenereerde documenten gevonden voor de geselecteerde periode."
        )
        logger.warning("No generated docs found for the selected period.")
        return

    department_selection = create_department_selection(
        generated_discharge_docs["department"].unique().tolist()
    )
    time_measurements = get_time_measurements()

    if department_selection != "Alle afdelingen":
        generated_discharge_docs = generated_discharge_docs[
            generated_discharge_docs["department"] == department_selection
        ]
        time_measurements = time_measurements[
            time_measurements["Afdeling"] == department_selection
        ]

    st.write("### Tijdsanalyse")

    st.write("#### Trendanalyse afgelopen jaar")

    trend_stats = process_time_measurements_for_trend_analysis(time_measurements)

    chart = visualise_time_measurements_trend(trend_stats)
    st.altair_chart(chart)

    st.write("#### Analyse voor geselecteerde tijdsperiode")

    (
        writing_minutes_per_patient,
        mean_writing_total,
        time_measurements_selected,
        mean_writing_time_per_session,
        sessions_per_patient,
        mean_number_of_sessions,
    ) = process_time_measurements_for_detail_analysis(time_measurements, date_input)

    col1, col2, col3 = st.columns(3)

    col1.write("##### Schrijfduur per opname")
    chart = visualise_time_measurements_detail(
        writing_minutes_per_patient,
        "Totaal_schrijven_minuten",
        "Totale schrijftijd per opname (min)",
        mean_writing_total,
    )
    col1.altair_chart(chart)

    col2.write("##### Schrijfduur per sessie")
    chart = visualise_time_measurements_detail(
        time_measurements_selected,
        "Schrijven_minuten",
        "Schrijftijd per sessie (min)",
        mean_writing_time_per_session,
    )
    col2.altair_chart(chart)

    col3.write("##### Aantal schrijfsessies per opname")
    chart = visualise_time_measurements_detail(
        sessions_per_patient,
        "Aantal_sessies",
        "Aantal schrijfsessies per opname",
        mean_number_of_sessions,
    )
    col3.altair_chart(chart)

    st.write("### Verschillen AI-gegenereerde brief vs. verstuurde brief")

    generated_discharge_docs = (
        generated_discharge_docs[generated_discharge_docs["success_ind"] == "Success"]
        .sort_values(by=["enc_id", "timestamp"], ascending=[True, False])
        .drop_duplicates(subset=["enc_id"], keep="first")
    )

    original_discharge_docs = get_original_discharge_docs(date_input[0], date_input[1])

    comparison_discharge_docs = process_comparison_with_jaccard(
        original_discharge_docs, generated_discharge_docs
    )

    ngram_cols = st.columns(3)
    chart, mean_text, median_text = visualise_jaccard_comparison(
        comparison_discharge_docs, n=1
    )

    ngram_cols[0].altair_chart(chart)
    ngram_cols[0].write(mean_text)
    ngram_cols[0].write(median_text)

    chart, mean_text, median_text = visualise_jaccard_comparison(
        comparison_discharge_docs, n=2
    )

    ngram_cols[1].altair_chart(chart)
    ngram_cols[1].write(mean_text)
    ngram_cols[1].write(median_text)

    chart, mean_text, median_text = visualise_jaccard_comparison(
        comparison_discharge_docs, n=3
    )

    ngram_cols[2].altair_chart(chart)
    ngram_cols[2].write(mean_text)
    ngram_cols[2].write(median_text)

    if (
        date_input[0].month != date_input[1].month
        or date_input[0].year != date_input[1].year
    ):
        st.write("#### Jaccard distance per maand")

        per_month_long = process_comparison_jaccard_for_trend(comparison_discharge_docs)
        chart = visualise_jaccard_trend(per_month_long)

        st.altair_chart(chart)


if __name__ == "__main__":
    st.set_page_config(
        "AIvA Discharge Documentation Generator - Admin Dashboard",
        page_icon="📈",
        layout="wide",
    )
    st.title("AIvA Discharge Documentation Generator - Admin Dashboard")

    with st.sidebar:
        db_env = st.radio("Database omgeving", ["PROD", "ACC"], index=0)
        default_start_date = datetime.now() - timedelta(days=14)
        default_end_date = datetime.now()
        date_input = st.date_input(
            "Selecteer een tijdsperiode",
            (default_start_date, default_end_date),
        )

    db_env = cast(Literal["PROD", "ACC", "DEBUG"], db_env)
    engine = get_engine(db_env=db_env, schema_name=Request.__table__.schema)
    SESSIONMAKER = sessionmaker(bind=engine)

    nav = st.navigation(
        [
            st.Page(kpi_page, title="KPIs"),
            st.Page(monitoring_page, title="Monitoring"),
            st.Page(pms_page, title="PMS Analyse"),
        ]
    )

    nav.run()
