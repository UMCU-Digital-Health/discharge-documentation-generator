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
Generate the Sphinx documentation as follows:

```
sphinx-build -b html docs docs/_build
```
