from pathlib import Path


def load_prompts(iterative: bool = False):
    """Loads the user and system prompt.

    Parameters
    ----------
    iterative : bool, optional
        Specifies whether to load the iterative system prompt or the regular system
        prompt. Defaults to False.

    Returns
    -------
    user_prompt : str
        The content of the user prompt file.
    system_prompt : str
        The content of the system prompt file.
    """
    prompt_folder = Path(__file__).parents[1] / "prompts"
    user_prompt_name = "user_prompt_iterative.txt" if iterative else "user_prompt.txt"
    with open(prompt_folder / user_prompt_name, "r") as file:
        user_prompt = file.read()

    with open(prompt_folder / "system_prompt.txt", "r") as file:
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
    departments_dict = {
        "Neonatologie": "NICU",
        "Intensive Care Centrum": "IC",
        "High Care Kinderen": "PICU",
        "Intensive Care Kinderen": "PICU",
    }
    if department in departments_dict:
        department = departments_dict[department]

    with open(
        Path(__file__).parents[1] / "prompts" / (department + "_template_prompt.txt"),
        "r",
    ) as file:
        template_prompt = file.read()
    return template_prompt
