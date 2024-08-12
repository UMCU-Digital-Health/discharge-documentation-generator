from pathlib import Path

import pandas as pd
from striprtf.striprtf import rtf_to_text

# apply rtf decoding to TEXT column as in staging dataplatform this is rtf

if __name__ == "__main__":
    data_folder = Path(
        "/mapr/administratielast/administratielast_datamanager/ontslagdocumentatie/"
    )

    file_name = "pre-pilot IC NICU CAR/HiX_patient_files_CAR_april"

    # read file
    df = pd.read_json(Path(data_folder / file_name).with_suffix(".json"))

    # apply rtf decoding to TEXT column
    df["TEXT"] = df["TEXT"].apply(rtf_to_text)

    # save as json
    df.to_json(Path(data_folder / (file_name + "_rtf_decoded")).with_suffix(".json"))
