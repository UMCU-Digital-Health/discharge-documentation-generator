import json

import openai


def get_chatgpt_output(patient_file, engine):
    response_beloop = openai.ChatCompletion.create(
        engine=engine,
        messages=[
            {
                "role": "system",
                "content": """Retourneer alle delen van het paragraaf tekst in het
                format van JSON, gegroupeerd per categorie
                zoals hieronder aangegeven. Geef daarnaast ook de bron zinnen waaruit
                het beloop is gehaald weer.
                [{"Categorie": *Categorie*,
                    "Beloop tijdens opname": *Beloop tijdens de opname van die
                    categorie*,
                    "Bron:", *Bron zinnen waaruit het beloop is gehaald*}].
                Geef alleen dit JSON object terug als content,
                geef verder geen output terug. Hou het antwoord in het JSON object
                kort. Als je het antwoord niet weet, geef dat dan aan en verzin
                niet iets. Schrijf het alsof je een arts bent die communiceert met een
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
                    - Wanneer er een compliactie optrad in verhouding tot de opname op
                    dag 1
                    - Wat deze complicatie was
                    - Hoe deze complicatie behandeld is
                    - Hoe lang er nog last van heeft gehad
                    - De huidige status van de complicatie
                Mochten er geen klachten zijn, dan kun je dit ook aangeven.
                Geef ook de bron zinnen waaruit het beloop is gehaald weer, CITEER de
                bron woord voor woord.
                Antwoord in een enkel JSON formaat per categorie van de vorm
                [{"Categorie": *Categorie*, "Beloop tijdens opname":
                *Beloop tijdens opname*,  "Bron:", *Bron zinnen waaruit het beloop is
                gehaald*}].
                """,
            },
            {"role": "user", "content": patient_file},
        ],
        temperature=0,
    )

    response_status = openai.ChatCompletion.create(
        engine=engine,
        messages=[
            {
                "role": "system",
                "content": """Retourneer alle delen van het paragraaf tekst in het
                format van JSON, gegroupeerd per categorie
                zoals hieronder aangegeven.
                [{"Categorie": *Categorie*,
                    "Huidige status": *Huidige status*,
                    "Bron:", *Bron zinnen waaruit de huidige status is gehaald*}].
                Geef alleen dit JSON object terug als content,
                geef verder geen output terug. Hou het antwoord in het JSON object
                kort. Als je het antwoord niet weet, geef dat dan aan en verzin
                niet iets. Schrijf het alsof je een arts bent die communiceert met een
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
                Antwoord in een enkel JSON formaat per categorie van de vorm
                [{"Categorie": *Categorie*, "Huidige status": *Huidige status*,
                "Bron:", *Bron zinnen waaruit de huidige status is gehaald*}].
                """,
            },
            {"role": "user", "content": patient_file},
        ],
    )

    reply_beloop = json.loads(response_beloop["choices"][0]["message"]["content"])
    reply_status = json.loads(response_status["choices"][0]["message"]["content"])
    return reply_beloop, reply_status
