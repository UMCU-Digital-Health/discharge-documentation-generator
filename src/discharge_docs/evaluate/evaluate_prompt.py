import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from dvclive import Live
from openai import AzureOpenAI
from rouge_score import rouge_scorer

from discharge_docs.evaluate.evaluate_prompt_helper import (
    compare_GPT_output_with_EPD_output,
    compare_two_lists,
    information_delta,
    split_letter_into_segments,
)
from discharge_docs.processing.processing import get_patient_file
from discharge_docs.processing.processing_dev import get_patient_discharge_docs
from discharge_docs.prompts.prompt import (
    load_evaluation_prompt,
    load_information_correction_prompt,
    load_information_intersection_prompt,
    load_information_union_prompt,
    load_prompts,
    load_template_prompt,
)
from discharge_docs.prompts.prompt_builder import PromptBuilder

load_dotenv()


def evaluate_prompt_rouge_and_OG_GPT(  # TODO not working
    department: str,
    remark: str,
    multiple_patient_data: pd.DataFrame,
    system_prompt: str,
    user_prompt: str,
    template_prompt: str,
    client: AzureOpenAI,
    deployment_name: str,
    prompt_builder: PromptBuilder,
    dvclive_dir: Path,
    temperature: float,
    save_exp: bool = True,
    **kwargs: dict,
) -> None:
    """
    Evaluate the prompt to generate discharge documentation and
    log the results using dvclive.

    Parameters
    ----------
    department : str
        The department for the patient data.
    remark : str
        The remark for what changed (can be left empty).
    multiple_patient_data : pd.DataFrame
        The dataframe with patient data for multiple patients.
    system_prompt : str
        The system prompt for the AI model.
    user_prompt : str
        The user prompt for the AI model.
    template_prompt : str
        The template prompt for the AI model.
    client : AzureOpenAI
        The Azure OpenAI client for generating AI model responses.
    deployment_name : str
        The name of the deployment resource.
    dvclive_dir : Path
        The directory to save dvclive logs.
    temperature : float, optional
        The temperature parameter for AI model's response generation,
            by default 0.8.
    save_exp : bool, optional
        Flag indicating whether to save the experiment, by default True.
    **kwargs : dict
        Additional keyword arguments for dvclive.

    Returns
    -------
    None
    """
    with Live(save_dvc_exp=save_exp, dir=str(dvclive_dir), **kwargs) as live:
        metrics_dict = {
            "nr_attempts": [],
            "rouge1_precision": [],
            "rouge1_recall": [],
            "rouge1_fmeasure": [],
            "semantic_similarity": [],
            "completeness_percentage_epd": [],
            "completeness_percentage_gpt": [],
            "overlap_percentage": [],
        }
        live.log_param("department", department)
        live.log_param("remark", remark)
        live.log_param("temperature", temperature)
        print("Evaluating for department: ", department)

        for enc_id in multiple_patient_data["enc_id"].unique():
            print(f"Processing enc_id: {enc_id}")
            patient_data = multiple_patient_data[
                multiple_patient_data["enc_id"] == enc_id
            ]
            patient_file_string, _ = get_patient_file(df=patient_data)
            OG_letter = get_patient_discharge_docs(df=patient_data).values[0]

            # gather GPT discharge letter
            max_attempts = 3
            attempt = 0
            success = False

            while attempt < max_attempts and not success:
                try:
                    generated_doc = prompt_builder.iterative_simulation(
                        patient_data=patient_data,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        template_prompt=template_prompt,
                    )

                    success = True
                except Exception:
                    attempt += 1

            if success:
                metrics_dict["nr_attempts"].append(attempt + 1)

                GPT_letter = [
                    f"{x['Categorie']}: {x['Beloop tijdens opname']}"
                    for x in generated_doc
                ]
                GPT_letter = "\n\n".join(GPT_letter)

                # Score using ROUGE metric
                scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=True)
                scores = scorer.score(target=OG_letter, prediction=GPT_letter)

                metrics_dict["rouge1_precision"].append(scores["rouge1"].precision)
                metrics_dict["rouge1_recall"].append(scores["rouge1"].recall)
                metrics_dict["rouge1_fmeasure"].append(scores["rouge1"].fmeasure)

                # Score using GPT automatic evaluation
                eval_output = {
                    "Semantische Similariteit Score": [],
                    "Volledigheid Percentage van EPD brief": [],
                    "Volledigheid Percentage van GPT brief": [],
                    "Overlap Percentage": [],
                }
                evaluation_prompt = load_evaluation_prompt()

                n_runs = 10
                for _i in range(n_runs):
                    eval = compare_GPT_output_with_EPD_output(
                        GPT_letter,
                        OG_letter,
                        evaluation_prompt,
                        engine=deployment_name,
                        client=client,
                        temperature=0,
                    )
                    eval_output["Semantische Similariteit Score"].append(
                        eval["Semantische Similariteit Score"]
                    )
                    eval_output["Volledigheid Percentage van EPD brief"].append(
                        eval["Volledigheid Percentage van A"]
                    )
                    eval_output["Volledigheid Percentage van GPT brief"].append(
                        eval["Volledigheid Percentage van B"]
                    )
                    eval_output["Overlap Percentage"].append(eval["Overlap Percentage"])

                average_eval_output = {
                    key: np.mean(value) for key, value in eval_output.items()
                }

                metrics_dict["semantic_similarity"].append(
                    average_eval_output["Semantische Similariteit Score"]
                )
                metrics_dict["completeness_percentage_epd"].append(
                    average_eval_output["Volledigheid Percentage van EPD brief"]
                )
                metrics_dict["completeness_percentage_gpt"].append(
                    average_eval_output["Volledigheid Percentage van GPT brief"]
                )
                metrics_dict["overlap_percentage"].append(
                    average_eval_output["Overlap Percentage"]
                )
            else:  # if failed, set all metrics to 0
                print(
                    "IMPORTANT: GPT failed to generate a response. "
                    + "Setting all metrics for this encounter to 0."
                )
                for key in metrics_dict:
                    metrics_dict[key].append(
                        max_attempts if key == "nr_attempts" else 0
                    )

        # save the averages and stds of the metrics
        for metric, values in metrics_dict.items():
            live.log_metric(f"{metric}_mean", f"{np.mean(values):.2f}")
            live.log_metric(f"{metric}_std", f"{np.std(values):.2f}")


def evaluate_prompt_alternative(  # noqa: C901
    department: str,
    remark: str,
    multiple_patient_data: pd.DataFrame,
    system_prompt: str,
    user_prompt: str,
    template_prompt: str,
    client: AzureOpenAI,
    deployment_name: str,
    prompt_builder: PromptBuilder,
    dvclive_dir: Path,
    temperature: float,
    save_exp: bool = True,
    verbose=False,
    **kwargs: dict,
) -> None:
    """
    Evaluate the prompt to generate discharge documentation and
    log the results using dvclive.

    Parameters
    ----------
    department : str
        The department for the patient data.
    remark : str
        The remark for what changed (can be left empty).
    multiple_patient_data : pd.DataFrame
        The dataframe with patient data for multiple patients.
    system_prompt : str
        The system prompt for the AI model.
    user_prompt : str
        The user prompt for the AI model.
    template_prompt : str
        The template prompt for the AI model.
    client : AzureOpenAI
        The Azure OpenAI client for generating AI model responses.
    deployment_name : str
        The name of the deployment resource.
    dvclive_dir : Path
        The directory to save dvclive logs.
    temperature : float, optional
        The temperature parameter for AI model's response generation,
            by default 0.8.
    save_exp : bool, optional
        Flag indicating whether to save the experiment, by default True.
    **kwargs : dict
        Additional keyword arguments for dvclive.

    Returns
    -------
    None
    """
    with Live(save_dvc_exp=save_exp, dir=str(dvclive_dir), **kwargs) as live:
        metrics_dict = {
            "nr_attempts": [],
            "segments_OG": [],
            "segments_GPT": [],
            "hallucination_union": [],
            "hallucination_intersection": [],
            "corrections_union": [],
            "corrections_intersection": [],
            "omissions_union": [],
            "omissions_intersection": [],
            "omissions_union_corrected": [],
            "omissions_intersection_corrected": [],
            "additions_union": [],
            "additions_intersection": [],
            "additions_union_corrected": [],
            "additions_intersection_corrected": [],
        }
        live.log_param("department", department)
        live.log_param("remark", remark)
        live.log_param("temperature", temperature)
        print("Evaluating for department: ", department)

        for enc_id in multiple_patient_data["enc_id"].unique():
            print(f"Processing enc_id: {enc_id}")
            patient_data = multiple_patient_data[
                multiple_patient_data["enc_id"] == enc_id
            ]
            patient_file_string, _ = get_patient_file(df=patient_data)
            OG_letter = get_patient_discharge_docs(df=patient_data).values[0]

            # gather GPT discharge letter
            max_attempts = 3
            attempt = 0
            success = False

            while attempt < max_attempts and not success:
                try:
                    generated_doc = prompt_builder.generate_discharge_doc(
                        patient_file=patient_file_string,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        template_prompt=template_prompt,
                    )
                    success = True
                except Exception:
                    attempt += 1

            if success:
                metrics_dict["nr_attempts"].append(attempt + 1)

                GPT_letter = [
                    f"{x['Categorie']}: {x['Beloop tijdens opname']}"
                    for x in generated_doc
                ]
                GPT_letter = "\n\n".join(GPT_letter)

                segments_OG = split_letter_into_segments(
                    letter=OG_letter, engine=deployment_name, client=client
                )
                segments_GPT = split_letter_into_segments(
                    letter=GPT_letter, engine=deployment_name, client=client
                )
                if verbose:
                    print(segments_OG)
                    print(segments_GPT)

                metrics_dict["segments_OG"].append(segments_OG)
                metrics_dict["segments_GPT"].append(segments_GPT)

                # Score using information overlap

                # letters: OG_letter, GPT_letter, patient_file_string

                # Hallucinations w.r.t. EPD
                extra_GPT_EPD = information_delta(
                    GPT_letter,
                    patient_file_string,
                    deployment_name,
                    client=client,
                    delta_type="additional",
                )
                missing_EPD_GPT = information_delta(
                    patient_file_string,
                    GPT_letter,
                    deployment_name,
                    client=client,
                    delta_type="missing",
                )

                # Information GPT cannot capture, used for correction
                extra_OG_EPD = information_delta(
                    OG_letter,
                    patient_file_string,
                    deployment_name,
                    client=client,
                    delta_type="additional",
                )
                missing_EPD_OG = information_delta(
                    patient_file_string,
                    OG_letter,
                    deployment_name,
                    client=client,
                    delta_type="missing",
                )

                # Information in GPT, not in OG letter
                # could be relevant, trivial, or hallucination
                # extra_GPT_OG = information_delta(
                #     GPT_letter, OG_letter, deployment_name, delta_type="additional"
                # )
                # missing_OG_GPT = information_delta(
                #     OG_letter, GPT_letter, deployment_name, delta_type="missing"
                # )

                # Information in OG letter, not in GPT
                # likely relevant missing information
                extra_OG_GPT = information_delta(
                    OG_letter,
                    GPT_letter,
                    deployment_name,
                    client=client,
                    delta_type="additional",
                )
                missing_GPT_OG = information_delta(
                    GPT_letter,
                    OG_letter,
                    deployment_name,
                    client=client,
                    delta_type="missing",
                )

                # Information union and intersect prompts
                information_union_prompt = load_information_union_prompt()
                information_intersection_prompt = load_information_intersection_prompt()
                information_correction_prompt = load_information_correction_prompt()

                # This gives us insight into hallucinations
                union_hallucinations = compare_two_lists(
                    extra_GPT_EPD,
                    missing_EPD_GPT,
                    information_union_prompt,
                    deployment_name,
                    client,
                    temperature,
                )
                intersection_hallucinations = compare_two_lists(
                    extra_GPT_EPD,
                    missing_EPD_GPT,
                    information_intersection_prompt,
                    deployment_name,
                    client,
                    temperature,
                )

                metrics_dict["hallucination_union"].append(union_hallucinations)
                metrics_dict["hallucination_intersection"].append(
                    intersection_hallucinations
                )

                # Data not in EPD, so used for correction
                union_corrections = compare_two_lists(
                    extra_OG_EPD,
                    missing_EPD_OG,
                    information_union_prompt,
                    deployment_name,
                    client,
                    temperature,
                )
                intersection_corrections = compare_two_lists(
                    extra_OG_EPD,
                    missing_EPD_OG,
                    information_intersection_prompt,
                    deployment_name,
                    client,
                    temperature,
                )

                metrics_dict["corrections_union"].append(union_corrections)
                metrics_dict["corrections_intersection"].append(
                    intersection_corrections
                )

                # This gives us insight into omissions
                union_omissions = compare_two_lists(
                    extra_OG_GPT,
                    missing_GPT_OG,
                    information_union_prompt,
                    deployment_name,
                    client,
                    temperature,
                )
                intersection_omissions = compare_two_lists(
                    extra_OG_GPT,
                    missing_GPT_OG,
                    information_intersection_prompt,
                    deployment_name,
                    client,
                    temperature,
                )

                metrics_dict["omissions_union"].append(union_omissions)
                metrics_dict["omissions_intersection"].append(intersection_omissions)

                # Omissions corrected
                # union
                union_corrections_omissions = compare_two_lists(
                    union_omissions,
                    union_corrections,
                    information_correction_prompt,
                    deployment_name,
                    client,
                    temperature,
                )

                # intersection
                intersection_corrections_omissions = compare_two_lists(
                    intersection_omissions,
                    intersection_corrections,
                    information_correction_prompt,
                    deployment_name,
                    client,
                    temperature,
                )

                metrics_dict["omissions_union_corrected"].append(
                    union_corrections_omissions
                )
                metrics_dict["omissions_intersection_corrected"].append(
                    intersection_corrections_omissions
                )

                # This gives us insight into additions
                union_additions = compare_two_lists(
                    extra_OG_GPT,
                    missing_GPT_OG,
                    information_union_prompt,
                    deployment_name,
                    client,
                    temperature,
                )
                intersection_additions = compare_two_lists(
                    extra_OG_GPT,
                    missing_GPT_OG,
                    information_intersection_prompt,
                    deployment_name,
                    client,
                    temperature,
                )

                metrics_dict["additions_union"].append(union_additions)
                metrics_dict["additions_intersection"].append(intersection_additions)

                # addition corrected
                # union
                union_corrections_additions = compare_two_lists(
                    union_additions,
                    union_hallucinations,
                    information_correction_prompt,
                    deployment_name,
                    client,
                    temperature,
                )

                # intersection
                intersection_corrections_additions = compare_two_lists(
                    intersection_additions,
                    union_hallucinations,
                    information_correction_prompt,
                    deployment_name,
                    client,
                    temperature,
                )

                metrics_dict["additions_union_corrected"].append(
                    union_corrections_additions
                )
                metrics_dict["additions_intersection_corrected"].append(
                    intersection_corrections_additions
                )

            else:  # if failed, set all metrics to 0
                print(
                    "IMPORTANT: GPT failed to generate a response. "
                    + "Setting all metrics for this encounter to 0."
                )
                for key in metrics_dict:
                    metrics_dict[key].append(
                        max_attempts if key == "nr_attempts" else 0
                    )

        # test, TODO remove
        if verbose:
            for metric, values in metrics_dict.items():
                print(f"{metric}", f"{values}")
                if metric != "nr_attempts":
                    print(f"{metric}", f"{[len(x) for x in values]}")

        # save the averages and stds of the metrics
        for metric, values in metrics_dict.items():
            if metric != "nr_attempts":
                live.log_metric(f"{metric}", f"{[len(x) for x in values]}")


if __name__ == "__main__":
    project_dir = Path(__file__).parents[3]
    temperature = 0.2

    client = AzureOpenAI(
        api_version="2024-02-01",
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    )

    # load prompts and data
    user_prompt, system_prompt = load_prompts()
    df_metavision = pd.read_parquet(
        Path(__file__).parents[3] / "data" / "processed" / "metavision_new_data.parquet"
    )
    df_HiX = pd.read_parquet(
        Path(__file__).parents[3] / "data" / "processed" / "HiX_data.parquet"
    )

    prompt_builder = PromptBuilder(
        temperature=temperature, deployment_name="aiva-gpt", client=client
    )

    departments_to_evaluate = []
    while not departments_to_evaluate:
        department_input = input(
            "Which department would you like to evaluate? (IC, NICU, CAR, PSY, ALL): "
        )
        departments_to_evaluate = [
            department.strip().upper() for department in department_input.split(",")
        ]
        if not any(
            department in ["IC", "NICU", "CAR", "PSY", "ALL"]
            for department in departments_to_evaluate
        ):
            print("Invalid department(s) entered. Please try again.")
    if departments_to_evaluate == ["ALL"]:
        departments_to_evaluate = ["IC", "NICU", "CAR", "PSY"]
    remark = input("Remark for what you changed in the code/prompts: ")

    # for department in ["IC", "NICU", "CAR", "PSY"]:
    for department in departments_to_evaluate:
        if department == "IC":
            template_prompt = load_template_prompt("IC")
            multiple_patient_data = df_metavision[
                df_metavision["enc_id"].isin([48, 55, 63])
            ]
        elif department == "NICU":
            template_prompt = load_template_prompt("NICU")
            multiple_patient_data = df_metavision[
                df_metavision["enc_id"].isin([107, 20, 150])
            ]
        elif department == "CAR":
            template_prompt = load_template_prompt("CAR")
            multiple_patient_data = df_HiX[df_HiX["enc_id"].isin([1012, 1010, 1062])]
        elif department == "PSY":
            template_prompt = load_template_prompt("PSY")
            multiple_patient_data = df_HiX[df_HiX["enc_id"].isin([1142])]
        else:
            template_prompt = None
            multiple_patient_data = pd.DataFrame()

        evaluate_prompt_alternative(
            department=department,
            remark=remark,
            multiple_patient_data=multiple_patient_data,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            template_prompt=template_prompt,
            client=client,
            deployment_name="aiva-gpt",
            prompt_builder=prompt_builder,
            dvclive_dir=project_dir / "output" / "dvclive",
            temperature=temperature,
            save_exp=False,
            verbose=False,
        )
