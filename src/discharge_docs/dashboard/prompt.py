import json
import re
from pathlib import Path


def get_chatgpt_output(patient_file, engine, client):
    response_beloop = client.chat.completions.create(
        model=engine,
        messages=[
            {
                "role": "system",
                "content": """Retourneer alle delen van het paragraaf tekst in het
                format van JSON, met een entry per categorie.
                Geef daarnaast ook de bron zinnen waaruit
                het beloop is gehaald weer.
                Schrijf het alsof je een arts bent die communiceert met een
                huisarts.""",
            },
            {
                "role": "user",
                "content": """
                Hieronder volgt het dossier van een patiënt met dagstatussen voor de
                opname van een patiënt in het ziekenhuis.
                Je taak is om een samenvattings paragraaf van een paar zinnen over het
                beloop de opname op het gebied van de categorieen voor de volgende
                behandelende arts te schrijven op basis van deze informatie.
                De categorieen zijn: Respiratie, Cardiologie, Neurologie en Infectie.
                De laatste dagstatus die in het dossier staat is de dag van vandaag
                wanneer de patient ontslagen wordt.
                Het is belangrijk om lopende zinnen te schrijven. Benoem de volgende
                zaken:
                    - Wanneer er een complicatie optrad in verhouding tot de opname op
                    dag 1
                    - Wat deze complicatie was
                    - Hoe deze complicatie behandeld is
                    - Hoe lang er nog last van heeft gehad
                    - De huidige status van de complicatie
                Mochten er geen klachten zijn, dan kun je dit ook aangeven.
                Geef ook de bron zinnen waaruit het beloop is gehaald weer, CITEER de
                bron woord voor woord.
                Antwoord in JSON formaat per categorie van de vorm:
                [{"Categorie": *Categorie*, "Beloop tijdens opname":
                *Beloop tijdens opname*,  "Bron:", *Bron zinnen waaruit het beloop is
                gehaald*}, {"Categorie": *Categorie2*, ...}]
                Geen alleen dit JSON-object terug!
                """,
            },
            {"role": "user", "content": patient_file},
        ],
        temperature=0,
    )

    response_status = client.chat.completions.create(
        model=engine,
        messages=[
            {
                "role": "system",
                "content": """Retourneer alle delen van het paragraaf tekst in
                JSON format. Schrijf het alsof je een arts bent die communiceert met een
                huisarts.""",
            },
            {
                "role": "user",
                "content": """
                Hieronder volgt het dossier van een patiënt met dagstatussen voor de
                opname van een patiënt in het ziekenhuis.
                Je taak is om een samenvattings paragraaf van een paar zinnen over de
                huidige status van de patient op het gebied van de categorieen voor de
                volgende behandelende arts te schrijven op basis van deze informatie.
                De categorieen zijn: Respiratie, Cardiologie, Neurologie en Infectie.
                De laatste dagstatus die in het dossier staat is de dag van vandaag
                wanneer de patient ontslagen wordt.
                Het is belangrijk om lopende zinnen te schrijven.
                Voor de huidige status is het belangrijk dat je, voor elke categorie,
                ook aangeeft wat er op dit moment nog aan actieve behandeling moet
                worden gedaan door de volgende arts, bijvoorbeeld als een kuur van
                antibiotica nog moet worden voortgezet. Geef dan ook aan wat precies
                nodig is, dus in het geval van medicatie, hoe lang moet deze nog
                gegeven worden?
                Geef enkel de categorien terug die nog niet stabiel zijn en waar een
                volgende behandelende arts van op de hoogte moet zijn.
                Geef ook de bron zinnen waaruit de huidige status is gehaald weer,
                CITEER de bron woord voor woord.
                Antwoord in JSON formaat per categorie van de vorm:
                [{"Categorie": *Categorie*, "Huidige status": *Huidige status*,
                "Bron:", *Bron zinnen waaruit de huidige status is gehaald*},
                {"Categorie": *Categorie2*, ...}]
                Geen alleen dit JSON-object terug!
                """,
            },
            {"role": "user", "content": patient_file},
        ],
    )
    reply_beloop = json.loads(
        re.sub(
            "```(json)?",
            "",
            response_beloop.model_dump()["choices"][0]["message"]["content"],
        )
    )
    reply_status = json.loads(
        re.sub(
            "```(json)?",
            "",
            response_status.model_dump()["choices"][0]["message"]["content"],
        )
    )
    return reply_beloop, reply_status


def load_pompts():
    with open(Path(__file__).parents[1] / "prompts" / "user_prompt.txt", "r") as file:
        user_prompt = file.read()
    with open(Path(__file__).parents[1] / "prompts" / "system_prompt.txt", "r") as file:
        system_prompt = file.read()
    return user_prompt, system_prompt


def load_evaluatie_prompt():
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
