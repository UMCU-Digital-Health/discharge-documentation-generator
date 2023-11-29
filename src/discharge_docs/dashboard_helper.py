import re

from dash import html


def highlight(text, selected_words):
    # als text string is
    if isinstance(text, str):
        sequences = re.split(re.escape(selected_words), text, flags=re.IGNORECASE)
        i = 1
        while i < len(sequences):
            sequences.insert(i, html.Mark(selected_words.upper()))
            i += 2
        return sequences
    else:  # als text een lijst is
        for i, t in enumerate(text):
            if isinstance(t, str):
                text[i] = highlight(t, selected_words)
        flat_list = []

        for sublist in text:
            if isinstance(sublist, list):
                for item in sublist:
                    flat_list.append(item)
            else:
                flat_list.append(sublist)
        return flat_list
