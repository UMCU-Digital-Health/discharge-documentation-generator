## Dataset Description

- **Repository:** [https://github.com/UMCU-Digital-Health/Discharge_Documentation_Generator](https://github.com/UMC Utrecht-Digital-Health/Discharge_Documentation_Generator)
- **Point of Contact:** [Laura Veerhoek](mailto:l.p.veerhoek@umcutrecht.nl), [Ruben Peters](mailto:r.peters-7@umcutrecht.nl)

Based on the dataset card template from huggingface, which can be found [here](https://github.com/huggingface/datasets/blob/main/templates/README_guide.md#table-of-contents).

### Dataset Summary

The data used in this project is a collection of medical discharge documents and patient files from the UMC Utrecht hospital from the NICU, ICU and Cardiology department. The dataset is used to perform prompt engineering was a retrospective set of admissions over a period of a few months in 2023 and 2024. The language is Dutch and contains medical terminology.  

### Supported Tasks and Leaderboards

- `Summarization`: The dataset is used to summaries medical discharge notes into a course of a patient's admission. Success on this task is measured periodically according to a post market surveillance plan.

### Languages

The language present in the dataset is Dutch. The text contains Dutch medical terms and abbreviations.

## Dataset Structure

### Data Instances
There are two data sources and formats possible within the UMC Utrecht, depending on the electronic health record system used. The two systems are HiX and Metavision. The data is stored in a SQL database and can be queried using SQL queries. Examples of the two data sources are shown below. The data format is also specified in various pydantic dataclasses, which can be found in [/src/api/pydantic_models.py](/src/api/pydantic_models.py).

#### HiX Discharge docs
```
{
    'pseudo_id': 'FHEU73824HFWYU87',
    'specialty_Organization_value: 'CAR',
    'identifier_value': 1234567,
    'period_start': '2024-04-20',
    'period_end': '2024-04-25',
    'type2_display_original': 'Ontslagbericht',
    'created': '2024-04-25',
    'content_attachment1_plain_data': 'Actual discharge text'
}
```

Can be joined with patient files using the identifier_value

#### HiX patient files

```
{
    'pseudo_id': 'FHEU73824HFWYU87',
    'specialty_Organization_value: 'CAR',
    'identifier_value': 1234567,
    'period_start': '2024-04-20',
    'period_end': '2024-04-25',
    'NAAM': 'CAR Consult - beleid',
    'TEXT': 'actual patient file info',
    'DATE': '2024-04-21 09:00:00',
}
```

Can be joined with discharge documents using the identifier_value

#### Metavision data

```
{
    'pseudo_id': 'FHEIJW7832J932FD',
    'location_Location_value_original': 'Neonatologie',
    'identifier_value': 1234567,
    'period_start': '2024-04-12',
    'period_end': '2024-04-14',
    'code_display_original': 'Anamnese'
    'valueString': 'Reden voor opname: postoperatieve ademhalingsproblemen.',
    'effectiveDateTime': '2024-04-12 11:00:00',
},
```

### Data Fields

#### HiX Discharge Docs
- `pseudo_id`: string with pseudonomised patientid
- `specialty_Organization_value` string containing specialization
- `identifier_value`: integer with the encounter id
- `period_start`: datetime with start of patient admission
- `period_end`: datetime with end of patient admission
- `type2_display_original`: string with type of document
- `created`: datetime of the creation time of the document
- `content_attachment1_plain_data`: string with actual content of the document

#### HiX Patient files
- `pseudo_id`: string with pseudonomised patientid
- `specialty_Organization_value` string containing specialization
- `identifier_value`: integer with the encounter id
- `period_start`: datetime with start of patient admission
- `period_end`: datetime with end of patient admission
- `NAAM`: string of the item name
- `TEXT`: string of the actual patient file
- `DATE`: datetime of the item creation time

#### Metavision data
- `pseudo_id`: string of pseudonomised patient id
- `location_Location_value_original` : string of the department
- `identifier_value`: int with the encounter id
- `period_start` : datetime of the start of admission
- `period_end` : datetime of the end of admission
- `code_display_original` : string of the field display value
- `valueString` : string with actual data
- `effectiveDateTime` : datetime of when the field was authored

### Data Splits

There have been no data splits, since we are not training a Machine learning model, but just using LLMs for inference.

## Dataset Creation

### Curation Rationale

The dataset was created to aid in the task of writing medical discharge documents. This is a time-intensive task that could be automated by using a LLM that generates a draft version of the discharge documents. To generate this, the entire patient file during admission is needed as input for the LLM.

### Source Data

The sources of the data are electronic health record (EHR) systems, specifically HiX and Metavision. The data is being provided by the dataplatform maintained by the UMC Utrecht.

#### Initial Data Collection and Normalization

The data is collected using the SQL-queries found in the [/data/sql/](/data/sql/) folder. This can be done either though [/run/data_pipeline.py](/run/data_pipeline.py), or through running the query directly on the SQL server.

#### Who are the source language producers?

The data is human generated. Both patient files and discharge documents are written by physicians and physician-assistants. These documents were written in the EHR as part of their normal administration process. 

### Annotations

The dataset does not contain annotations.


### Personal and Sensitive Information

The dataset contains pseudo-ids based on the original patient ids. Furthermore the dataset has been pseudonomised using [DEDUCE](https://github.com/vmenger/deduce).
However this process is not perfect and the data could still contain privacy-sensitive information. Furthermore, since the data contains the patient files, the identity of the patient could still be inferred even without their identifiers. Therefore this dataset is still considered sensitive and not shared outside the development team.

## Considerations for Using the Data

### Social Impact of Dataset

This dataset could positively impact society by minimizing both human-made errors and time spent writing discharge documents. This will enable health care providers to spend more of their time on actual care instead of administration. This is important since the pressure on the health care system will only increase with a population that will both live longer and consists of a bigger part of the total population.

This risk of this dataset is that it contains very sensitive information and the quality of the patients files might not always be as good, for example containing spelling errors as well as many (not generally known) abbreviations.

### Discussion of Biases

The dataset only contains data from patients at the UMC Utrecht. However since the intended use of this dataset is currently limited to the UMC Utrecht, this bias is not a problem and therefore no steps were taken to mitigate this bias.

### Other Known Limitations

Texts can contain characters that indicate structure, like headings and lists that are not parsed. This should not be a problem for models like Large Language models, but should still be taken into account. 

## Additional Information

### Dataset Curators

The dataset curators are Laura Veerhoek and Ruben Peters (see intro for contact information). This project was not externally funded.

### Licensing Information

The dataset is not licensed, since it is not meant to be shared.
