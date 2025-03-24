from dash import dcc, html


def manual_filtering_message(message: str) -> str:
    """Manually filter out some placeholders from the message:
    1. [LEEFTIJD-1]-jarige is a DEDUCE-placeholder that should be removed.
    2. IC letters only have one heading (beloop) so filter it out, NICU has others.
    """
    message = message.replace(" [LEEFTIJD-1]-jarige", "")
    message = message.replace("\n\nBeloop\n", "\n\n")
    return message


def format_generated_doc(
    generated_doc: dict, format_type: str, manual_filtering: bool = False
) -> str | list[html.Div]:
    """Convert the generated document to plain text or markdown with headers.

    Parameters
    ----------
    generated_doc : dict
        The generated document in a list of dict.
    format_type : str
        The desired format type of the generated document.
    manual_filtering : bool, optional
        Whether to apply manual filtering to the generated document, by default False.

    Returns
    -------
    dict | str
        The structured version of the generated document (dict) if format is 'markdown'.
        The plain text version of the generated document if format is 'plain'.
    """
    if format_type not in ["markdown", "plain"]:
        raise ValueError("Invalid format type. Please choose 'markdown' or 'plain'.")

    output_structured = []
    output_plain = ""
    for header in generated_doc.keys():
        if manual_filtering:
            content = manual_filtering_message(generated_doc[header])
        else:
            content = generated_doc[header]
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
