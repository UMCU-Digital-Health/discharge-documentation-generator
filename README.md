# Discharge Documentation Generator

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FUMCU-Digital-Health%2FDischarge_Documentation_Generator%2Fmain%2F%257B%257Bpyproject.toml)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/UMCU-Digital-Health/Discharge_Documentation_generator/unit_test.yml)

Authors: Ruben Peters & Laura Veerhoek

Email: r.peters-7@umcutrecht.nl & l.p.veerhoek@umcutrecht.nl

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
