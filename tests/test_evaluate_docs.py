# import tempfile

from openai import AzureOpenAI

# from discharge_docs.evaluate.evaluate_prompt import evaluate_prompt_alternative


class MockAzureOpenAI(AzureOpenAI):
    def __init__(self):
        pass

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, model, messages, temperature):
        return MockAzureOpenAIResponse()


class MockAzureOpenAIResponse:
    def __init__(self):
        pass

    def model_dump(self):
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "logprobs": None,
                    "message": {
                        "content": (
                            '[{"Categorie": "Test",' '"Beloop tijdens opname": "Test"}]'
                        )
                    },
                }
            ],
            "created": 1626161224,
            "id": "cmpl-3LwvXrU5W6iY0Gd9ZJf9eY4v",
            "model": "aiva-gpt",
        }


def test_evaluate_doc():
    pass


#     """Tests the evaluate prompt function with a mock AzureOpenAI client"""

#     with tempfile.TemporaryDirectory() as temp_dir:
#         evaluate_prompt_alternative(
#             patient_file="This is a test",
#             patient_discharge="This is a test",
#             system_prompt="This is a test",
#             user_prompt="This is a test",
#             client=MockAzureOpenAI(),
#             dvclive_dir=temp_dir,
#             temperature=0.8,
#             save_exp=False,
#             dvcyaml=None,  # Make sure dvclive does not update dvc.yaml
#         )
