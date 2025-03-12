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

    def create(self, model, messages, temperature, response_format):
        return MockAzureOpenAIResponse()


class MockMessage:
    def __init__(self, content):
        self.content = content


class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)
        self.finish_reason = "stop"
        self.index = 0
        self.logprobs = None


class MockAzureOpenAIResponse:
    def __init__(self):
        self.choices = [MockChoice('{"Categorie1": "Beloop1","Categorie2": "Beloop2"}')]
        self.created = 1626161224
        self.id = "cmpl-3LwvXrU5W6iY0Gd9ZJf9eY4v"
        self.model = "aiva-gpt"
