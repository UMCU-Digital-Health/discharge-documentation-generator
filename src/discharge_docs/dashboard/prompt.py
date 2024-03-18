import json
import re
from pathlib import Path


def load_pompts():
    """loads the user and system prompt

    Returns
    -------
    user_prompt, system_prompt : str, str
    """
    with open(Path(__file__).parents[1] / "prompts" / "user_prompt.txt", "r") as file:
        user_prompt = file.read()
    with open(Path(__file__).parents[1] / "prompts" / "system_prompt.txt", "r") as file:
        system_prompt = file.read()
    return user_prompt, system_prompt


def load_evaluatie_prompt():
    """loads the evaluatie prompt from the prompts folder"""
    with open(
        Path(__file__).parents[1] / "prompts" / "evaluatie_prompt.txt", "r"
    ) as file:
        evaluatie_prompt = file.read()
    return evaluatie_prompt


def load_template_prompt(department: str) -> str:
    """
    Load the template prompt for a given department.

    Parameters
    ----------
    department : str
        The name of the department for which to load the template prompt.

    Returns
    -------
    str
        The template prompt for the specified department.
    """
    with open(
        Path(__file__).parents[1] / "prompts" / (department + "_template_prompt.txt"),
        "r",
    ) as file:
        template_prompt = file.read()
    return template_prompt


def get_GPT_discharge_docs(
    patient_file,
    system_prompt,
    user_prompt,
    template_prompt,
    temperature,
    engine,
    client,
    addition_prompt=None,
):
    """
    Generate discharge documentation using GPT model.

    Parameters
    ----------
    patient_file : str
        The path to the patient file.
    system_prompt : str
        The system prompt for the GPT model.
    user_prompt : str
        The user prompt for the GPT model.
    template_prompt : str
        The template prompt for the GPT model.
    temperature : float
        The temperature parameter for GPT model generation.
    engine : str
        The GPT model engine to use.
    client : object
        The client object for interacting with the GPT model.
    addition_prompt : str, optional
        Additional prompt for the GPT model, by default None.

    Returns
    -------
    dict
        The generated discharge documentation as a dictionary.
    """
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
        {
            "role": "user",
            "content": template_prompt,
        },
        {"role": "user", "content": patient_file},
    ]
    if addition_prompt is not None:
        messages.append(
            {
                "role": "user",
                "content": addition_prompt,
            }
        )
    response = client.chat.completions.create(
        model=engine,
        messages=messages,
        temperature=temperature,
    )
    reply = json.loads(
        re.sub(
            "```(json)?",
            "",
            response.model_dump()["choices"][0]["message"]["content"],
        )
    )
    return reply
