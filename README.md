# Discharge_Documentation_Generator

Author: Ruben Peters
Email: r.peters-7@umcutrecht.nl

## Installation

To install the discharge_docs package use:

```{bash}
pip install -e .
```

## Deploying to PositConnect

To deploy to PositConnect install rsconnect (`pip install rsconnect-python`) and run (in case of a dash app):
```{bash}
rsconnect deploy dash --server https://rsc.ds.umcutrecht.nl/ --api-key <(user specific key)> --entrypoint run.app:app .
```

## Documentation

A dataset card specifying the dataset can be found [here](/docs/dataset_card.md)
A model card specifying the used model can be found [here](/docs/model_card.md)
