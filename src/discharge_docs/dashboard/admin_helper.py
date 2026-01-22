import logging
import os
from datetime import date, datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from nltk.util import ngrams
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import URL

logger = logging.getLogger(__name__)


def create_department_selection(department_list: list[str]) -> str:
    """Creates a department selection dropdown for the admin dashboard

    Parameters
    ----------
    department_list : list[str]
        List of departments to select from

    Returns
    -------
    str
        Selected department from the dropdown
    """
    department_selection_col, _ = st.columns([1, 2])
    # List can contain None values, for example when request no longer links to a
    # discharge document, but this is not a viable option in the dropdown
    department_list_updated = ["Alle afdelingen"] + [
        dep for dep in department_list if dep is not None
    ]
    department_selection = department_selection_col.selectbox(
        "Kies een afdeling",
        department_list_updated,
        index=0,
    )
    return department_selection


def get_time_measurements() -> pd.DataFrame:
    """Retrieves all time measurements for the monitoring admin page

    Returns
    -------
    pd.DataFrame
        Dataframe containing time measurements for all discharges
    """

    data_path = (
        Path(__file__).parents[3] / "data" / "raw" / "metavision_time_measurements.csv"
    )

    time_measurements = pd.read_csv(
        data_path,
        parse_dates=[
            "AdmissionDate",
            "DischargeDate",
            "FormRelease",
            "SessieCreate",
            "StartSchrijven",
            "EindeSchrijven",
        ],
    )

    # map Neonatologie to NICU and Intensive Care Centum to IC in the Afdeling column
    time_measurements["Afdeling"] = time_measurements["Afdeling"].replace(
        {"Neonatologie": "NICU", "Intensive Care Centrum": "IC"}
    )

    time_measurements = time_measurements[
        time_measurements["AdmissionDate"] >= pd.Timestamp(2024, 10, 15)
    ]

    # remove outliers
    time_measurements = time_measurements[time_measurements["Schrijven_minuten"] >= 0]
    time_measurements = time_measurements[time_measurements["Schrijven_minuten"] < 180]

    return time_measurements


def _filter_time_measurements(
    time_measurements: pd.DataFrame, min_date: date, max_date: date
) -> pd.DataFrame:
    """Filter time measurements provided between min_date and max_date

    Parameters
    ----------
    time_measurements : pd.DataFrame
        Dataframe with time measurement columns including 'DischargeDate',
        'AdmissionDate' and 'Schrijven_minuten'.
    min_date : date
        Minimum discharge date (inclusive).
    max_date : date
        Maximum discharge date (inclusive).

    Returns
    -------
    pd.DataFrame
        Filtered dataframe with time measurements within the specified date range.
    """
    filtered_time_measurements = time_measurements.copy()
    filtered_time_measurements = filtered_time_measurements[
        (filtered_time_measurements["DischargeDate"] >= pd.to_datetime(min_date))
        & (filtered_time_measurements["DischargeDate"] <= pd.to_datetime(max_date))
    ]
    return filtered_time_measurements


def process_time_measurements_for_trend_analysis(
    time_measurements: pd.DataFrame,
) -> pd.DataFrame:
    """converts time measurements to a monthly min, max and average

    Parameters
    ----------
    time_measurements : pd.DataFrame
        dataframe containing time measurements

    Returns
    -------
    pd.DataFrame
        dataframe containing monthly min, max and average writing times
    """
    time_measurements_trend = _filter_time_measurements(
        time_measurements,
        time_measurements["DischargeDate"].min().date(),
        datetime.today().date(),
    )
    # Monthly average writing time per patient for trend (last year)
    time_measurements_trend["year_month"] = (
        pd.to_datetime(time_measurements_trend["DischargeDate"])
        .dt.to_period("M")
        .dt.to_timestamp()
    )
    # Sum writing time per patient per month
    per_month_patient = (
        time_measurements_trend.groupby(["year_month", "PatientID"], dropna=True)[
            "Schrijven_minuten"
        ]
        # .agg()
        .sum()
        .reset_index(name="Totaal_per_patient")
    )
    # Average, min and max writing time per patient for each month
    per_month_avg = (
        per_month_patient.groupby("year_month")["Totaal_per_patient"]
        .mean()
        .reset_index(name="Gemiddelde_per_patient")
    )
    per_month_min = (
        per_month_patient.groupby("year_month")["Totaal_per_patient"]
        .min()
        .reset_index(name="Kortste schrijftijd")
    )
    per_month_max = (
        per_month_patient.groupby("year_month")["Totaal_per_patient"]
        .max()
        .reset_index(name="Langste schrijftijd")
    )

    per_month_stats = per_month_avg.merge(per_month_min, on="year_month").merge(
        per_month_max, on="year_month"
    )

    # Melt for plotting multiple lines with a legend

    stats_long = per_month_stats.melt(
        id_vars="year_month",
        value_vars=[
            "Gemiddelde_per_patient",
            "Kortste schrijftijd",
            "Langste schrijftijd",
        ],
        var_name="Metric",
        value_name="Value",
    )
    return stats_long


def visualise_time_measurements_trend(data: pd.DataFrame) -> alt.LayerChart:
    """chart visualisation for the trend analysis of the time measurements

    Parameters
    ----------
    data : pd.DataFrame
        dataframe with monthy min, max and average writing times

    Returns
    -------
    alt.LayerChart
        altair chart visualising the trend analysis
    """
    base = alt.Chart(data).encode(
        x=alt.X(
            "year_month:T",
            axis=alt.Axis(title="Maand", labelAngle=-45, labelAlign="right"),
        ),
        y=alt.Y(
            "Value:Q",
            axis=alt.Axis(title="Schrijftijd per patiënt (min)"),
        ),
        color=alt.Color("Metric:N", legend=alt.Legend(title="Metriek")),
        strokeDash=alt.StrokeDash("Metric:N"),
    )

    line_chart = base.mark_line(point=False)

    points = base.transform_filter(
        alt.datum.Metric == "Gemiddelde_per_patient"
    ).mark_point(filled=True, size=60)

    return (line_chart + points).properties(height=600)


def process_time_measurements_for_detail_analysis(
    time_measurements: pd.DataFrame, date_input: tuple[date, date]
) -> tuple[pd.DataFrame, float, pd.DataFrame, float, pd.DataFrame, float]:
    """process time measurements for detailed analysis regarding writing time per
    patient, writing time per session and number of sessions per patient

    Parameters
    ----------
    time_measurements : pd.DataFrame
        dataframe containing time measurements
    date_input : tuple[date, date]
        tuple containing the start and end dates for filtering the time measurements

    Returns
    -------
    tuple[pd.DataFrame, float, pd.DataFrame, float, pd.DataFrame, float]
        tuple containing processed dataframes and mean values for detailed analysis
    """
    time_measurements_selected = _filter_time_measurements(
        time_measurements, date_input[0], date_input[1]
    )

    schrijven_minuten_per_patient = (
        time_measurements_selected.groupby("PatientID", dropna=True)[
            "Schrijven_minuten"
        ]
        .sum()
        .reset_index(name="Totaal_schrijven_minuten")
    )
    mean_schrijven_totaal = schrijven_minuten_per_patient[
        "Totaal_schrijven_minuten"
    ].mean()

    mean_schrijftijd_per_session = time_measurements_selected[
        "Schrijven_minuten"
    ].mean()

    sessions_per_patient = (
        time_measurements_selected.groupby("PatientID", dropna=True)
        .size()
        .reset_index(name="Aantal_sessies")
    )
    mean_number_of_sessions = sessions_per_patient["Aantal_sessies"].mean()

    return (
        schrijven_minuten_per_patient,
        mean_schrijven_totaal,
        time_measurements_selected,
        mean_schrijftijd_per_session,
        sessions_per_patient,
        mean_number_of_sessions,
    )


def visualise_time_measurements_detail(
    data: pd.DataFrame, variable: str, x_label: str, mean_val: float
) -> alt.LayerChart:
    """Visualise time measurements for detailed analysis

    Parameters
    ----------
    data : pd.DataFrame
        Dataframe containing time measurements for detailed analysis
    variable : str
        Variable to be visualized
    x_label : str
        Label for the x-axis
    mean_val : float
        Mean value to be indicated on the chart

    Returns
    -------
    alt.LayerChart
        _description_
    """
    hist_chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X(
                f"{variable}:Q",
                bin=alt.Bin(maxbins=20),
                axis=alt.Axis(title=x_label),
            ),
            y=alt.Y("count()", axis=alt.Axis(title="Aantal opnames")),
            tooltip=[alt.Tooltip("count()", title="Aantal opnames")],
        )
    )

    mean_df = pd.DataFrame(
        {
            "mean": [mean_val],
            "label": [f"Gemiddelde: {mean_val:.2f}"],
        }
    )
    mean_rule = (
        alt.Chart(mean_df)
        .mark_rule(color="#32CD32", strokeWidth=3)
        .encode(x=alt.X("mean:Q"))
    )
    mean_text = (
        alt.Chart(mean_df)
        .mark_text(align="left", dx=5, dy=-10, color="#32CD32")
        .encode(x=alt.X("mean:Q"), text=alt.Text("label:N"))
    )

    return (hist_chart + mean_rule + mean_text).properties(height=300)


def get_original_discharge_docs(min_date: date, max_date: date) -> pd.DataFrame:
    """Retrieve original discharge documents within a specified date range.

    Parameters
    ----------
    min_date : date
        The minimum discharge date.
    max_date : date
        The maximum discharge date.

    Returns
    -------
    pd.DataFrame
        DataFrame containing original discharge documents within the date range.
    """
    db_url = URL.create(
        drivername="mssql+pymssql",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWD"),
        host="dataplatform",
        port=1433,
        database="PUB",
    )
    engine = create_engine(db_url)

    sql_path = (
        Path(__file__).parents[3]
        / "data"
        / "sql"
        / "metavision_discharge_docs_retro.sql"
    )

    query = text(sql_path.read_text())

    discharge_docs = pd.read_sql(
        query,
        engine,
        params={"start_date": min_date, "end_date": max_date},
    )

    # for each enc_id return only the most recent document
    discharge_docs = discharge_docs.sort_values(
        by=["enc_id", "date"], ascending=[True, False]
    ).drop_duplicates(subset=["enc_id"], keep="first")

    return discharge_docs


def _jaccard_distance(generated_letter: str, original_letter: str, n: int) -> float:
    """Calculate the Jaccard distance between two strings using n-grams

    Score of 0 means identical texts, while a score of 1 means no common n-grams.

    Parameters
    ----------
    generated_letter : str
        generated discharge letter
    original_letter : str
        original discharge letter
    n : int
        n-gram size

    Returns
    -------
    float
        the calculated Jaccard distance
    """
    generated_letter_words = generated_letter.lower().split()
    original_letter_words = original_letter.lower().split()

    ngrams_generated = set(ngrams(generated_letter_words, n))
    ngrams_original = set(ngrams(original_letter_words, n))

    ngrams_union = ngrams_generated.union(ngrams_original)
    if len(ngrams_union) == 0:
        return 0
    ngrams_intersection = ngrams_generated.intersection(ngrams_original)
    return 1 - len(ngrams_intersection) / len(ngrams_union)


def process_comparison_with_jaccard(
    original_discharge_docs: pd.DataFrame, generated_discharge_docs: pd.DataFrame
) -> pd.DataFrame:
    """process the original discharge docs and generated discharge docs to calculate
    the ngram jaccard distance for n=1,2,3

    Parameters
    ----------
    original_discharge_docs : pd.DataFrame
        original discharge documents
    generated_discharge_docs : pd.DataFrame
        generated discharge documents

    Returns
    -------
    pd.DataFrame
        DataFrame containing the comparison with Jaccard distances
    """
    comparison_discharge_docs = generated_discharge_docs.merge(
        original_discharge_docs,
        left_on="enc_id",
        right_on="enc_id",
        suffixes=("_generated", "_original"),
    )

    comparison_discharge_docs = comparison_discharge_docs[
        [
            "enc_id",
            "department_generated",
            "date",
            "content",
            "discharge_letter",
        ]
    ]

    comparison_discharge_docs["ngram_1"] = comparison_discharge_docs.apply(
        lambda x: _jaccard_distance(x["discharge_letter"], x["content"], 1), axis=1
    )
    comparison_discharge_docs["ngram_2"] = comparison_discharge_docs.apply(
        lambda x: _jaccard_distance(x["discharge_letter"], x["content"], 2), axis=1
    )
    comparison_discharge_docs["ngram_3"] = comparison_discharge_docs.apply(
        lambda x: _jaccard_distance(x["discharge_letter"], x["content"], 3), axis=1
    )

    return comparison_discharge_docs


def visualise_jaccard_comparison(
    comparison_discharge_docs: pd.DataFrame, n: int
) -> tuple[alt.LayerChart, str, str]:
    """chart for visualisation of the jaccard distance comparison for an n-gram
    including text for the mean and median

    Parameters
    ----------
    comparison_discharge_docs : pd.DataFrame
        dataframe containing the jaccard distance comparison
    n : int
        n-gram size

    Returns
    -------
    tuple[alt.LayerChart, str, str]
        chart, mean text, median text
    """
    n_gram_df = comparison_discharge_docs[[f"ngram_{n}"]].dropna()
    hist = (
        alt.Chart(n_gram_df)
        .mark_bar()
        .encode(
            x=alt.X(
                f"ngram_{n}:Q",
                bin=alt.Bin(maxbins=30),
                axis=alt.Axis(title=f"Jaccard distance ({n}-gram)"),
            ),
            y=alt.Y("count()", axis=alt.Axis(title="Aantal documenten")),
            tooltip=[alt.Tooltip("count()", title="Aantal documenten")],
        )
        .properties(height=240)
    )
    mean = n_gram_df[f"ngram_{n}"].mean()
    median = n_gram_df[f"ngram_{n}"].median()
    mean_rule = (
        alt.Chart(pd.DataFrame({"value": [mean]}))
        .mark_rule(color="#32CD32", strokeWidth=3)
        .encode(x=alt.X("value:Q"))
    )
    median_rule = (
        alt.Chart(pd.DataFrame({"value": [median]}))
        .mark_rule(color="#FF0000", strokeWidth=3, strokeDash=[4, 2])
        .encode(x=alt.X("value:Q"))
    )
    return (
        (hist + mean_rule + median_rule),
        f"Gemiddelde:{mean:.2f}",
        f"Mediaan:{median:.2f}",
    )


def process_comparison_jaccard_for_trend(
    comparison_discharge_docs: pd.DataFrame,
) -> pd.DataFrame:
    """process the comparison data for monthly analysis

    Parameters
    ----------
    comparison_discharge_docs : pd.DataFrame
        comparison dataframe containing jaccard distances

    Returns
    -------
    pd.DataFrame
        processed dataframe for monthly analysis
    """
    comparison_discharge_docs["year_month"] = (
        pd.to_datetime(comparison_discharge_docs["date"])
        .dt.to_period("M")
        .dt.to_timestamp()
    )
    per_month = (
        comparison_discharge_docs.groupby("year_month")[
            ["ngram_1", "ngram_2", "ngram_3"]
        ]
        .mean()
        .reset_index()
    )
    per_month_long = per_month.melt(
        id_vars="year_month",
        value_vars=["ngram_1", "ngram_2", "ngram_3"],
        var_name="Ngram",
        value_name="Gemiddelde Jaccard",
    )
    per_month_long["Ngram"] = per_month_long["Ngram"].map(
        {"ngram_1": "1-gram", "ngram_2": "2-gram", "ngram_3": "3-gram"}
    )
    return per_month_long


def visualise_jaccard_trend(data: pd.DataFrame) -> alt.Chart:
    """chart for visualisation of the monthly jaccard distance trend

    Parameters
    ----------
    data : pd.DataFrame
        dataframe containing the monthly jaccard distances

    Returns
    -------
    alt.Chart
        chart for visualisation of the monthly jaccard distance trend
    """
    ngram_month_chart = (
        alt.Chart(data)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "year_month:T",
                axis=alt.Axis(title="Maand", labelAngle=-45, labelAlign="right"),
            ),
            y=alt.Y(
                "Gemiddelde Jaccard:Q",
                axis=alt.Axis(title="Gemiddelde Jaccard distance"),
            ),
            color=alt.Color("Ngram:N", legend=alt.Legend(title="Ngram")),
            tooltip=[
                alt.Tooltip("year_month:T", title="Maand"),
                alt.Tooltip("Ngram:N", title="Ngram"),
                alt.Tooltip(
                    "Gemiddelde Jaccard:Q", title="Gemiddelde Jaccard", format=".3f"
                ),
            ],
        )
    )
    return ngram_month_chart
