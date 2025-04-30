# Discharge Documentation Generator

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FUMCU-Digital-Health%2Fdischarge-documentation-generator%2Fmain%2F%257B%257Bpyproject.toml)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/UMCU-Digital-Health/discharge-documentation-generator/unit_test.yml)

Authors: Ruben Peters & Laura Veerhoek

Email: r.peters-7@umcutrecht.nl & l.p.veerhoek@umcutrecht.nl


The Discharge Documentation Generator is a tool that uses an LLM to generate a draft discharge letter summarizing the course of a patient's admission in a hospital based on the medical notes extracted from the patient's electronic health record. 
Currently, the tool has been developed for the Intensive Care Unit (IC), Neonative Intensive Care Unit (NICU) and the Cardiology department (CAR) of the UMC Utrecht hospital.
The tool is designed to assist healthcare professionals in creating discharge letters by providing a starting point for the writing process. The generated letters should be further adapted and supplemented by the healthcare professionals before being finalized and sent to the next treating physicians, which are often general practicioners.


Note that this public repository is a mirror of a private repository updated with releases. This means that some information such as feature branches and pull requests are not visible to you. If you are curious about our way of working, please contact us.


## Installation

To install the discharge_docs package use:

```bash
pip install -e .
```

## Deploying to PositConnect

To deploy to PositConnect, make sure to have installed the requirements and run:
```bash
. .env
. deploy.sh
```
Choose the desired deployment options.

## Documentation

A dataset card specifying the dataset can be found [here](/docs/dataset_card.md)

A model card specifying the used model can be found [here](/docs/model_card.md)

## Running data pipeline to get new export for development & testing purposes

To run the data pipeline, run the following command:
```bash
python run/data_pipeline.py
```
Specify the config parameters in data_pipeline.py.
