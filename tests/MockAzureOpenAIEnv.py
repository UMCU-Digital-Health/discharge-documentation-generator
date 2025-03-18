from openai import AzureOpenAI


class MockAzureOpenAI(AzureOpenAI):
    def __init__(self, json_error: bool = False, general_error: bool = False):
        self.json_error = json_error
        self.general_error = general_error

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, model, messages, temperature, response_format):
        if self.json_error:
            return MockAzureJSONError()
        if self.general_error:
            raise Exception("General error")
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


class MockAzureJSONError:
    """Alternative response, triggers JSONError"""

    def __init__(self):
        self.choices = [MockChoice('{"Categorie1": "Beloop1","Categorie2"= "Beloop2"}')]
        self.created = 1626161224
        self.id = "cmpl-3LwvXrU5W6iY0Gd9ZJf9eY4v"
        self.model = "aiva-gpt"
