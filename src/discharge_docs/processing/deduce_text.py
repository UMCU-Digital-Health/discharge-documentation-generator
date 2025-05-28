import logging
from pathlib import Path

import pandas as pd
from deduce import Deduce
from tqdm import tqdm

logger = logging.getLogger(__name__)

tqdm.pandas()

deduce = Deduce(cache_path=Path(__file__).parents[3] / "run")


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
    logger.info(f"DEDUCE applied to column '{col_name}', for {len(df)} rows.")
    return df
