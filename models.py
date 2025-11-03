import secrets
import requests

from termcolor import colored

class LanguageModel:
    def generate_sync(self, prompt: str) -> str:
        print(colored(f"Prompt: '{prompt}'", "red"))
        out = self._generate_sync(prompt)
        print(colored(f"Out: '{out}'", "yellow"))
        return out

    def _generate_sync(self, prompt: str) -> str:
        raise NotImplementedError

class DebugHumanModel(LanguageModel):
    def _generate_sync(self, prompt: str) -> str:
        print(prompt)
        return input("> ")

class GoogleGeminiModel(LanguageModel):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _generate_sync(self, prompt: str) -> str:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}",
            json={
                "contents": [{"parts":[{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.9,
                    # topP": 0.99,
                    "topK": 100,
                    "thinkingConfig": {"thinkingBudget": 0},
                },
            }
        )

        j = r.json()

        if not r.ok:
            print("ERROR")
            print(j)
            assert r.ok

        return j["candidates"][0]["content"]["parts"][0]["text"]


def testing_model() -> LanguageModel:
    return GoogleGeminiModel(api_key=secrets.GEMINI_KEY)
