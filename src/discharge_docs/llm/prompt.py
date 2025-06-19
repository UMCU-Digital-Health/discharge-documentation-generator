from pathlib import Path


def load_prompts():
    """Loads the user and system prompt.

    Returns
    -------
    user_prompt : str
        The content of the user prompt file.
    system_prompt : str
        The content of the system prompt file.
    """
    prompt_folder = Path(__file__).parent / "prompts"
    user_prompt_name = "user_prompt.txt"
    with open(prompt_folder / user_prompt_name, "r") as file:
        user_prompt = file.read()

    with open(prompt_folder / "system_prompt.txt", "r") as file:
        system_prompt = file.read()
    return user_prompt, system_prompt


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
    if department == "DEMO":
        department = "NICU"

    with open(
        Path(__file__).parent / "prompts" / (department + "_template_prompt.txt"),
        "r",
    ) as file:
        template_prompt = file.read()
    return template_prompt


def load_all_templates_prompts_into_dict(
    departments: list | None = None,
) -> dict:
    """Load all template prompts for the specified departments into a dictionary.

    Parameters
    ----------
    departments : list, optional
        The list of departments for which to load the template prompts.
        Defaults to ["NICU", "IC", "CAR"].

    Returns
    -------
    dict
        A dictionary containing the template prompts for each department.
    """
    if departments is None:
        departments = ["NICU", "IC", "CAR", "PICU"]
    output_dict = {x: load_template_prompt(x) for x in departments}
    output_dict["DEMO"] = load_template_prompt("NICU")
    return output_dict
