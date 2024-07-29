## Dataset Description

- **Repository:** [https://github.com/UMCU-Digital-Health/Discharge_Documentation_Generator](https://github.com/UMCU-Digital-Health/Discharge_Documentation_Generator)
- **Point of Contact:** [Laura Veerhoek](mailto:l.p.veerhoek@umcutrecht.nl), [Ruben Peters](mailto:r.peters-7@umcutrecht.nl)

Based on the dataset card template from huggingface, which can be found [here](https://github.com/huggingface/datasets/blob/main/templates/README_guide.md#table-of-contents).

### Dataset Summary

The dataset consists of discharge letters and patient files from NICU, IC, Cardiology and Psychiatry departments. It was exported in May 2024 and covers the patients that were admitted between March and May 2024. The language is Dutch and contains medical terminology.  

### Supported Tasks and Leaderboards

- `Summarization`: The dataset is used to summaries medical discharge documents. Success on this task is measured by clinical evaluation and optionally by metrics like ROUGE and using LLMs to score the quality of generated documents.

### Languages

The language present in the dataset is Dutch. The text contains Dutch medical terms and abbreviations.

## Dataset Structure

### Data Instances

#### HiX Discharge docs
```
{
    'pseudo_id': 'FHEU73824HFWYU87',
    'specialty_Organization_value: 'CAR',
    'enc_id': 56482357,
    'period_start': '2024-04-20',
    'period_end': '2024-04-25',
    'status': 'finished',
    'type2_display_original': 'Ontslagbericht',
    'created': '2024-04-25',
    'docStatus': 'final',
    'content_attachment1_plain_data': 'Actual discharge text'
}
```

Can be joined with patient files using the enc_id

#### HiX patient files

```
{
    'pseudo_id': 'FHEU73824HFWYU87',
    'specialty_Organization_value: 'CAR',
    'enc_id': 56482357,
    'period_start': '2024-04-20',
    'period_end': '2024-04-25',
    'status': 'finished',
    'qn_id': 'CS549357',
    'category_display': 'Cardiologie',
    'name': 'CAR Consult',
    'qr_id': 523895,
    'authored': '2024-04-21 09:00:00',
    'created': '2024-04-21 09:00:00',
    'qri_id': 74920572,
    'item_text': 'Beleid',
    'item_answer_value_valueString': 'actual patient file info'
}
```

Can be joined with discharge documents using the enc_id

#### Metavision data

```
{
    'enc_id': 0123456,
    'pseudo_id': 'FHEIJW7832J932FD',
    'period_start': '2024-04-12',
    'period_end': '2024-04-14',
    'location_Location_value_original': 'Neonatologie',
    'effectiveDateTime': '2024-04-12 11:00:00',
    'valueString': 'Reden voor opname: postoperatieve ademhalingsproblemen.',
    'code_display_original': 'Anamnese'
},
```

### Data Fields

#### HiX Discharge Docs
- `pseudo_id`: string with pseudonomised patientid
- `specialty_Organization_value` string containing specialization
- `enc_id`: integer with the encounter id
- `period_start`: datetime with start of patient admission
- `period_end`: datetime with end of patient admission
- `status`: string with status of patient admission
- `type2_display_original`: string with type of document
- `created`: datetime of the creation time of the document
- `docStatus`: string with status of the document
- `content_attachment1_plain_data`: string with actual content of the document

#### HiX Patient files
- `pseudo_id`: string with pseudonomised patientid
- `specialty_Organization_value` string containing specialization
- `enc_id`: integer with the encounter id
- `period_start`: datetime with start of patient admission
- `period_end`: datetime with end of patient admission
- `status`: string with status of patient admission
- `qn_id`: int with id of the questionnaire
- `category_display`: string with the display name of the questionnaire
- `name`: string with the name of the questionnaire
- `qr_id`: int id of the questionnaire response
- `authored`: datetime when the file was authored
- `created`: datetime when the file was created
- `qri_id`: int of the questionnaire response item
- `item_text`: string of the item name
- `item_answer_value_valueString`: string of the actual patient file

#### Metavision data
- `end_id`: int with the encounter id
- `pseudo_id`: string of pseudonomised patient id
- `period_start` : datetime of the start of admission
- `period_end` : datetime of the end of admission
- `location_Location_value_original` : string of the department
- `effectiveDateTime` : datetime of when the field was authored
- `valueString` : string with actual data
- `code_display_original` : string of the field display value

### Data Splits

There have been no data splits, since we are not training a Machine learning model, but just using LLMs for inference.

## Dataset Creation

### Curation Rationale

The dataset was created to aid in the task of writing medical discharge documents. This is a time-intensive task that could be automated by using a LLM that generates a draft version of the discharge documents. To generate this, the entire patient file during admission is needed as input for the LLM.

### Source Data

The sources of the data are electronic health record (EHR) systems, specifically HiX and Metavision. The data is being provided by the dataplatform maintained by the UMCU.

#### Initial Data Collection and Normalization

The data is collected using the SQL-queries found in the [/data/sql/](/data/sql/) folder. It's filtered on the departments currently enrolled in this project (NICU, IC, Cardiology and Psychiatry) and for the evaluation the period of April - May 2024 is chosen. Furthermore the patient records that are used for the discharge documentation are written during their admission. 

#### Who are the source language producers?

The data is human generated. Both patient files and discharge documents are written by physicians and physician-assistants. These documents were written in the EHR as part of their normal administration process. 
The people represented in the data are patients from the UMCU that were admitted in one of the participating departments during the period April - May 2024.

### Annotations

The dataset does not contain annotations


### Personal and Sensitive Information

The dataset contains pseudo-ids based on the original patient ids. Furthermore the dataset has been pseudonomised using [DEDUCE](https://github.com/vmenger/deduce).
However this process is not perfect and the data could still contain privacy-sensitive information. Furthermore, since the data contains the patient files, the identity of the patient could still be inferred even without their identifiers. Therefore this dataset is still considered sensitive and not shared outside the development team.

## Considerations for Using the Data

### Social Impact of Dataset

This dataset could positively impact society by minimizing both human-made errors and time spend writing discharge documents. This will enable health care providers to spend more of their time on actual care instead of administration. This is important since the pressure on the health care system will only increase with a population that will both live longer and consists of a bigger part of the total population.

This risk of this dataset is that it contains very sensitive information and the quality of the patients files might not always be as good, for example containing spelling errors as well as many (not generally known) abbreviations.

### Discussion of Biases

The dataset only contains data from patients at the UMCU. However since the intended use of this dataset is limited to the UMCU, this bias is not a problem and therefore no steps were taken to mitigate this bias.

### Other Known Limitations

Texts can contain characters that indicate structure, like headings and lists that are not parsed. This should not be a problem for models like Large Language models, but should still be taken into account. 

## Additional Information

### Dataset Curators

The dataset curators are Laura Veerhoek and Ruben Peters (see intro for contact information). This project was not externally funded.

### Licensing Information

The dataset is not licensed, since it is not meant to be shared.
