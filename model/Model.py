import time
import openai
import requests
from rich import print
from abc import abstractmethod



class Base:
    def __init__(self, key, language, api_base=None):
        self.key = key
        self.language = language
        self.current_key_index = 0

    def get_key(self, key_str):
        keys = key_str.split(",")
        key = keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(keys)
        return key

    @abstractmethod
    def translate(self, text):
        pass


class GPT3(Base):
    def __init__(self, key, language, api_base=None):
        super().__init__(key, language)
        self.api_key = key
        self.api_url = (
            f"{api_base}v1/completions"
            if api_base
            else "https://api.openai.com/v1/completions"
        )
        self.headers = {
            "Content-Type": "application/json",
        }
        # TODO support more models here
        self.data = {
            "prompt": "",
            "model": "text-davinci-003",
            "max_tokens": 1024,
            "temperature": 1,
            "top_p": 1,
        }
        self.session = requests.session()
        self.language = language

    def translate(self, text):
        print(text)
        self.headers["Authorization"] = f"Bearer {self.get_key(self.api_key)}"
        self.data["prompt"] = f"Please help me to generate questions and answer，`{text}`"
        r = self.session.post(self.api_url, headers=self.headers, json=self.data)
        if not r.ok:
            return text
        t_text = r.json().get("choices")[0].get("text", "").strip()
        print(t_text)
        return t_text


class DeepL(Base):
    def __init__(self, session, key, api_base=None):
        super().__init__(session, key, api_base=api_base)

    def translate(self, text):
        return super().translate(text)


class ChatGPT(Base):
    def __init__(self, key, language, api_base=None, options =None):
        super().__init__(key, language, api_base=api_base)
        self.key = key
        self.language = language
        self.NO_LIMIT = options.no_limit
        if api_base:
            openai.api_base = api_base

    def translate(self, text):
        print(text)
        openai.api_key = self.get_key(self.key)
        try:
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        # english prompt here to save tokens
                        "content": f"Please help me to generate questions and answer,`{text}`, please return only questions and answer content not include the origin text",
                    }
                ],
            )
            t_text = (
                completion["choices"][0]
                .get("message")
                .get("content")
                .encode("utf8")
                .decode()
            )
            if not self.NO_LIMIT:
                # for time limit
                time.sleep(3)
        except Exception as e:
            # TIME LIMIT for open api please pay
            key_len = self.key.count(",") + 1
            sleep_time = int(60 / key_len)
            time.sleep(sleep_time)
            print(e, f"will sleep  {sleep_time} seconds")
            openai.api_key = self.get_key(self.key)
            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": f"Please help me to generate questions and answer,`{text}`, please return only questions and answer content not include the origin text",
                    }
                ],
            )
            t_text = (
                completion["choices"][0]
                .get("message")
                .get("content")
                .encode("utf8")
                .decode()
            )
        print(t_text)
        return t_text
