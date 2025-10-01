from pathlib import Path
from string import Template

from discharge_docs.config_models import LengthRange


def load_prompts():
    """Loads the user and system prompt.

    Returns
    -------
    general_prompt : str
        The content of the user prompt file.
    system_prompt : str
        The content of the system prompt file.
    """
    prompt_folder = Path(__file__).parent / "prompts"
    with open(prompt_folder / "general_prompt.txt", "r") as file:
        general_prompt = file.read()

    with open(prompt_folder / "system_prompt.txt", "r") as file:
        system_prompt = file.read()
    return general_prompt, system_prompt


def load_department_prompt(department: str) -> str:
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
        Path(__file__).parent
        / "prompts"
        / "department_prompts"
        / (department + "_prompt.txt"),
        "r",
    ) as file:
        template_prompt = file.read()
    return template_prompt


def load_department_examples(department: str) -> str:
    """
    Load the examples for a given department.

    Parameters
    ----------
    department : str
        The name of the department for which to load the examples.

    Returns
    -------
    str
        The examples for the specified department.
    """
    if department == "DEMO":
        department = "NICU"

    with open(
        Path(__file__).parent
        / "prompts"
        / "department_prompts"
        / (department + "_examples.txt"),
        "r",
    ) as file:
        examples = file.read()
    return examples


def load_post_processing_prompt(department: str) -> str:
    prompt_folder = Path(__file__).parent / "prompts"
    with open(prompt_folder / "post_processing_prompt.txt", "r") as file:
        post_processing_prompt = file.read()
    with open(
        prompt_folder / "department_prompts" / f"{department}_examples.txt", "r"
    ) as file:
        department_examples = file.read()

    return Template(post_processing_prompt).safe_substitute(
        {"DEPARTMENT_EXAMPLES": department_examples}
    )


def add_length_to_processing_prompt(
    post_processing_prompt: str | None,
    length_range: LengthRange | None,
    length_of_stay: int,
) -> str:
    """Adds a length requirement to the post-processing prompt based on the patient's
    length of stay.
    Example usage:
        prompt = add_length_to_processing_prompt(
            dep_config.department["IC"].post_processing_prompt,
            dep_config.department["IC"].length_range,
            100 )

    Parameters
    ----------
    post_processing_prompt : str | None
        The post-processing prompt template.
    length_range : LengthRange | None
        An object specifying the mapping between ranges of length of stay (in days) and
        the desired length value to use in the prompt.
    length_of_stay : int
        The patient's length of stay in days.

    Returns
    -------
    str
        The post-processing prompt with the "LENGTH" placeholder replaced by the
        appropriate value based on the length of stay.

    Raises
    ------
    ValueError
        If the length range configuration or prompt is None.
    ValueError
        If the length of stay does not fit in any defined ranges.
    """
    if post_processing_prompt is None or length_range is None:
        raise ValueError("Length range configuration or prompt is None.")

    desired_length = None
    for rule in length_range.model_dump().values():
        if rule is None:
            continue
        lower_bound_satisfied = (rule["min_days"] is None) or (
            length_of_stay >= rule["min_days"]
        )
        upper_bound_satisfied = (rule["max_days"] is None) or (
            length_of_stay <= rule["max_days"]
        )
        if lower_bound_satisfied and upper_bound_satisfied:
            desired_length = rule["length"]
            break
    if desired_length is None:
        raise ValueError(
            f"Length of stay {length_of_stay} does not fit in any defined ranges."
        )

    return Template(post_processing_prompt).substitute({"LENGTH": desired_length})
