import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from dvclive import Live
from openai import AzureOpenAI
from rouge_score import rouge_scorer

load_dotenv()


def evaluate_prompt(
    patient_file: str,
    patient_discharge: str,
    system_prompt: str,
    user_prompt: str,
    client: AzureOpenAI,
    dvclive_dir: Path,
    temperature: float = 0.8,
    save_exp: bool = True,
    **kwargs: dict,
) -> None:
    """
    Evaluate the prompt to generate discharge documentation and
    log the results using dvclive.

    Parameters
    ----------
    patient_file : str
        The path to the patient file.
    patient_discharge : str
        The patient's discharge documentation.
    system_prompt : str
        The system prompt for the AI model.
    user_prompt : str
        The user prompt for the AI model.
    client : AzureOpenAI
        The Azure OpenAI client for generating AI model responses.
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
        response = client.chat.completions.create(
            model="aiva-gpt",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "user", "content": patient_file},
            ],
        )
        live.log_param("temperature", temperature)

        # Load and transform GPT output
        reply_beloop = json.loads(
            re.sub(
                "```(json)?",
                "",
                response.model_dump()["choices"][0]["message"]["content"],
            )
        )
        reply_beloop = [
            f"# {x['Categorie']}\n{x['Beloop tijdens opname']}" for x in reply_beloop
        ]
        reply_beloop = "\n\n".join(reply_beloop)

        # Score using ROUGE metric
        scorer = rouge_scorer.RougeScorer(["rouge1"], use_stemmer=True)
        scores = scorer.score(target=patient_discharge, prediction=reply_beloop)

        live.log_metric("rouge1_precision", scores["rouge1"].precision)
        live.log_metric("rouge1_recall", scores["rouge1"].recall)
        live.log_metric("rouge1_fmeasure", scores["rouge1"].fmeasure)


if __name__ == "__main__":
    project_dir = Path(__file__).parents[3]
    temperature = 0.8

    client = AzureOpenAI(
        api_version="2024-02-01",
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
    )

    with open(project_dir / "data" / "prompts" / "system_prompt.txt", "r") as f:
        system_prompt = f.read().replace("\n", "")

    with open(project_dir / "data" / "prompts" / "user_prompt1.txt", "r") as f:
        user_prompt = f.read().replace("\n", "")

    with open(project_dir / "data" / "raw" / "example_patient_file_gpt.txt") as f:
        patient_file = f.read().replace("\n", "")

    with open(project_dir / "data" / "raw" / "example_patient_discharge.txt") as f:
        patient_discharge = f.read().replace("\n", "")

    evaluate_prompt(
        patient_file,
        patient_discharge,
        system_prompt,
        user_prompt,
        client,
        project_dir / "output" / "dvclive",
        temperature,
        True,
    )
