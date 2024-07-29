
<!-- Adapted from hugging face template: https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/templates/modelcard_template.md -->

# Model Card for Discharge Documentation generator

The model used for this project is GPT-4, trained by OpenAI and made available through Azure OpenAI.
The model version is `1106-Preview`

## Model Details

### Model Description

GPT-4 is a LLM developed by OpenAI

- **Developed by:** OpenAI
- **Model type:** LLM
- **Language(s) (NLP):** Multi-lingual
- **License:** None
- **Finetuned from model [optional]:** Not fine-tuned

## Uses

The model is intended to be used to generate discharge documentation based on the patient file that is included in the prompt. 

### Out-of-Scope Use

The model is not intended for use as a Clinical Decision Support (CDS) tool or other malicious uses, since for the intended purpose both content filtering and abuse monitoring are turned off.

## Bias, Risks, and Limitations

Using a pre-trained closed-source LLM like GPT-4 can lead to risks for patients. There is already research available about the risks of using such a model, see for example the paper `On the Dangers of Stochastic Parrots: Can Language Models Be Too Big?`. 

### Recommendations

Users should be aware of the limitations of using a LLM model, mainly that the model should not be used generating diagnoses or clinical-reasoning. The model can hallucinate or omit important information. Therefore a physician always needs to check the discharge document before sending it. This is also the current process where a supervisor always does a manual check of the document. 

## How to Get Started with the Model

See [/src/discharge_docs/prompts/prompt_builder.py](/src/discharge_docs/prompts/prompt_builder.py) for how to use this model.

## Training Details

Since the model used is proprietary, we have no details on the training data and process.

## Evaluation

The application of this model is evaluated using students and clinicians. The results are still pending.

### Testing Data, Factors & Metrics

#### Testing Data

See the [dataset card](/docs/dataset_card.md)

#### Metrics

The model performance is mainly tested on omissions, hallucinations and trivial information compared to the original discharge documentation. 
Annotations are performed by students and checked by clinicians.

### Results

TBA

#### Summary

TBA

## Environmental Impact [optional]

Since GPT-4 is a proprietary model running on Azure resources, it's not entirely clear what the CO2 emissions are. However, since we are only using inference on the model and not fine-tuning, the emissions of training the model are lower. 

- **Hardware Type:** Azure OpenAI resources
- **Hours used:** TBD
- **Cloud Provider:** Azure
- **Compute Region:** Sweden
- **Carbon Emitted:** unclear

## Citation

```
@article{achiam2023gpt,
  title={Gpt-4 technical report},
  author={Achiam, Josh and Adler, Steven and Agarwal, Sandhini and Ahmad, Lama and Akkaya, Ilge and Aleman, Florencia Leoni and Almeida, Diogo and Altenschmidt, Janko and Altman, Sam and Anadkat, Shyamal and others},
  journal={arXiv preprint arXiv:2303.08774},
  year={2023}
}
```

[DOI](https://doi.org/10.48550/arXiv.2303.08774)

## More Information [optional]

* (GPT-4 system card)[https://cdn.openai.com/papers/gpt-4-system-card.pdf]
* (Azure OpenAI)[https://azure.microsoft.com/en-us/products/ai-services/openai-service]

## Model Card Authors [optional]


* Laura Veerhoek
* Ruben Peters

## Model Card Contact

* l.p.veerhoek@umcutrecht.nl
* r.peters-7@umcutrecht.nl