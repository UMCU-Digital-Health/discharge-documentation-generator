import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chat_models import ChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.vectorstores import Chroma
from markdownify import markdownify as md

load_dotenv()
template = """Gegeven de volgende geextraheerde stukken tekst uit verschillende lange
 documenten en een vraag.
Als je het antwoord niet weet, zeg dan dat je het niet weet. Verzin zelf geen
 antwoorden, maar gebruik alleen informatie uit de stukken informatie die hier gegeven
 worden.
Antwoord in het NEDERLANDS.

Vraag: {question}
=========
Context:{summaries}
=========
GEEF HET ANTWOORD IN HET NEDERLANDS:"""
PROMPT = PromptTemplate(template=template, input_variables=["summaries", "question"])

persist_directory = "./db_ser_adviezen"
embedding = OpenAIEmbeddings()
# Now we can load the persisted database from disk, and use it as normal.
docsearch = Chroma(persist_directory=persist_directory, embedding_function=embedding)

qa = load_qa_with_sources_chain(llm=ChatOpenAI(), chain_type="stuff", prompt=PROMPT)
st.header("Chatbot - Wat wilt u weten over de SER adviezen?")
adviezen = pd.DataFrame(
    [
        "SER advies Nationale klimaataanpak voor regionale industriële koplopers",
        "SER advies waardevol werk publieke dienstverlening onder druk",
        "SER verkenning evenwichtig sturen op de grondstoffentransitie en "
        + "energietransitie voor brede welvaart",
        "SER verkenning duurzame toekomstperspectieven landbouw",
        "SER advies MLT",
        "SER advies energietransitie en werkegelegenheßid",
        "SER voorverkenning transities en werkgelegenheid effecten",
    ],
    columns=["SER adviezen in de chatbot"],
)

user_question = st.text_input(
    "Vul hier uw vraag in: ",
    placeholder="Wat weten we over de relatie tussen transities en "
    + " arbeidsmarkt(beleid)?",
)

if user_question:
    pass
else:
    st.table(adviezen)
if user_question:
    with st.spinner("Documenten aan het zoeken..."):
        docs = docsearch.similarity_search(user_question, k=8)
    with st.spinner("Een antwoord aan het formuleren..."):
        output = qa(
            {"input_documents": docs, "question": user_question},
            return_only_outputs=True,
        )
    st.write("*:green[Antwoord:]*")
    st.write(output["output_text"])
    st.write("*:blue[Bronnen:]*")
    for i in range(len(docs)):
        st.write(md(docs[i].page_content))
        st.markdown("*Bron: " + str(docs[i].metadata["source"].split("/")[-1]) + "*")
        st.markdown("*Pagina: " + str(docs[i].metadata["page"]) + "*")
        st.markdown("---")
    user_question = None
    st.table(adviezen)
