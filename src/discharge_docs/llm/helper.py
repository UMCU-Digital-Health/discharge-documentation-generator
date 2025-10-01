import logging
from dataclasses import dataclass
from datetime import datetime

from dash import dcc, html

from discharge_docs.config_models import DepartmentConfig
from discharge_docs.llm.prompt import add_length_to_processing_prompt
from discharge_docs.llm.prompt_builder import (
    ContextLengthError,
    GeneralError,
    JSONError,
    PromptBuilder,
)

logger = logging.getLogger(__name__)


@dataclass
class DischargeLetter:
    generated_doc: dict
    generation_time: datetime | None
    success_indicator: bool
    error_type: str | None = None

    def format(
        self,
        format_type: str = "markdown",
        manual_filtering: bool = True,
        include_generation_time: bool = True,
    ):
        """Format the discharge letter to plain text or markdown with headers.

        Parameters
        ----------
        format_type : str, optional
            The desired format type of the generated document, by default "markdown".
        manual_filtering : bool, optional
            Whether to apply manual filtering to the generated document, by default True
        include_generation_time : bool, optional
            Whether to include the generation time in the plain text output, by
              default True
        Returns
        -------
        dict | str
            The structured version of the generated document (dict) if format
            is 'markdown'
            The plain text version of the generated document if format is 'plain'.
        """
        if format_type not in ["markdown", "plain"]:
            raise ValueError(
                "Invalid format type. Please choose 'markdown' or 'plain'."
            )

        output_structured = []
        output_plain = ""
        if include_generation_time and self.generation_time is not None:
            output_plain += f"Generatietijd: {self.generation_time}\n"
            output_structured.append(
                html.Div(
                    [
                        html.Strong("Generatietijd"),
                        dcc.Markdown(f"{self.generation_time}"),
                    ]
                )
            )
        for header in self.generated_doc.keys():
            if manual_filtering:
                content = manual_filtering_message(self.generated_doc[header])
            else:
                content = self.generated_doc[header]
            output_structured.append(
                html.Div(
                    [
                        html.Strong(header),
                        dcc.Markdown(content),
                    ]
                )
            )
            output_plain += f"{header}\n"
            output_plain += f"{content}\n\n"
        if format_type == "markdown":
            return output_structured
        else:
            return output_plain


def manual_filtering_message(message: str) -> str:
    """Manually filter out some placeholders from the message:
    1. [LEEFTIJD-1]-jarige is a DEDUCE-placeholder that should be removed.
    2. IC letters only have one heading (beloop) so filter it out, NICU has others.
    """
    message = message.replace(" [LEEFTIJD-1]-jarige", "")
    message = message.replace("Beloop\n", "")
    return message


def generate_single_doc(
    prompt_builder: PromptBuilder,
    patient_file_string: str,
    system_prompt: str | None,
    general_prompt: str | None,
    department: str,
    department_config: DepartmentConfig,
    length_of_stay: int | None,
    department_prompt: str | None = None,
    post_processing_prompt: str | None = None,
):
    """
    Generate a single discharge letter for a patient using the prompt builder.

    Parameters
    ----------
    prompt_builder : PromptBuilder
        The prompt builder instance for generating discharge docs.
    patient_file_string : str
        The patient file data as a string.
    system_prompt : str | None
        The system prompt to use (optional).
    general_prompt : str | None
        The general prompt to use (optional).
    department : str
        The department name.
    department_config : DepartmentConfig
        The department configuration object.
    length_of_stay : int | None
        The patient's length of stay.
    department_prompt : str | None, optional
        The department-specific prompt to use to override the department config.
    post_processing_prompt : str | None, optional
        The post-processing prompt to use to override the department config.

    Returns
    -------
    DischargeLetter
        The generated discharge letter object.
    """
    department_prompt_used = (
        department_prompt or department_config.department[department].department_prompt
    )
    post_processing_prompt_used = (
        post_processing_prompt
        or department_config.department[department].post_processing_prompt
    )

    try:
        discharge_letter = prompt_builder.generate_discharge_doc(
            patient_file=patient_file_string,
            system_prompt=system_prompt,
            general_prompt=general_prompt,
            department_prompt=department_prompt_used,
        )

        if (
            department_config.department[department].post_processing
            and length_of_stay is not None
        ):
            post_processing_prompt = add_length_to_processing_prompt(
                post_processing_prompt_used,
                department_config.department[department].length_range,
                length_of_stay,
            )
            discharge_letter_class = DischargeLetter(
                generated_doc=discharge_letter,
                success_indicator=True,
                generation_time=None,
            )

            narratief = prompt_builder.post_processing(
                discharge_letter_class.format(
                    format_type="plain",
                    manual_filtering=False,
                    include_generation_time=False,
                ),  # type: ignore
                post_processing_prompt,
            )

            discharge_letter = {**discharge_letter, **narratief}
            logger.info("Post-processing applied")
        success_indicator = True
    except (ContextLengthError, JSONError, GeneralError) as e:
        discharge_letter = {
            "Geen Vooraf Gegenereerde Ontslagbrief Beschikbaar": e.dutch_message
        }
        success_indicator = False
        error_type = e.type

    return DischargeLetter(
        discharge_letter,
        datetime.now(),
        success_indicator,
        error_type if not success_indicator else None,
    )
