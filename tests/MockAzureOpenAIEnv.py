from openai import AzureOpenAI


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
