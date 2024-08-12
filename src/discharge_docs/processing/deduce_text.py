import os

import pandas as pd
from deduce import Deduce
from dotenv import load_dotenv
from tqdm import tqdm

tqdm.pandas()

load_dotenv()

if os.getenv("ENV", "") == "development":
    deduce = Deduce()
else:
    deduce = Deduce(cache_path=".")


def apply_deduce(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """
    Apply deduce function to deidentify text in a specific column of a DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame containing the text data.
    col_name : str
        The name of the column to apply deduce function on.

    Returns
    -------
    pd.DataFrame
        The DataFrame with deidentified text in the specified column.

    """
    df[col_name] = (
        df[col_name]
        .fillna("")  # some None values, which are not handled by deduce
        .progress_apply(
            lambda x: deduce.deidentify(x, disabled={"dates"}).deidentified_text
        )
    )
    return df
