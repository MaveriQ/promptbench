# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
from abc import ABC, abstractmethod

LLAMA_MODELS = [
    'llama2-7b',
    'llama2-7b-chat',
    'llama2-13b',
    'llama2-13b-chat',
    'llama2-70b',
    'llama2-70b-chat',
]

GPT_MODELS = [
    'gpt-3.5-turbo',
    'gpt-4',
]

VICUNA_MODELS = [
    'vicuna-7b',
    'vicuna-13b',
    'vicuna-13b-v1.3',
]

UL2_MODELS = [
    'google/flan-ul2',
]

MODEL_LIST = {
    't5': ['google/flan-t5-large'],
    'llama': LLAMA_MODELS,
    'gpt': GPT_MODELS,
    'vicuna': VICUNA_MODELS,
    'ul2': UL2_MODELS,
}


class LMMBaseModel(ABC):
    def __init__(self, **kwargs):
        self.raw_dataset = None
        self.model = kwargs.get('model', None)
        self.max_new_tokens = kwargs.get('max_new_tokens', 20)

    @abstractmethod
    def predict(self, input_text, **kwargs):
        pass

    def __call__(self, input_text, **kwargs):
        return self.predict(input_text, **kwargs)

    def set_raw_dataset(self, raw_dataset):
        self.raw_dataset = raw_dataset
    
    def predict_dataset(self, prompt):
        assert self.raw_dataset is not None
        from utils import process_input, process_pred, eval
        input_texts, labels = process_input(prompt, self.raw_dataset)
        
        import tqdm
        raw_preds = []
        for input_text in tqdm.tqdm(input_texts):
            raw_preds.append(self.predict(input_text))
        
        preds = process_pred(self.raw_dataset.dataset_name, raw_preds)
        score = eval(self.raw_dataset, preds, labels)
        return score


class LLMModel(object):

    def __init__(self, **kwargs):
        self.model = kwargs.get('model', None)
        self.infer_model = self.create_model(**kwargs)

    def create_model(self, **kwargs):
        if self.model == 'google/flan-t5-large':
            return T5Model(**kwargs)
        elif self.model in LLAMA_MODELS:
            return LlamaModel(**kwargs)
        elif self.model in GPT_MODELS:
            return OpenAIModel(**kwargs)
        elif self.model in VICUNA_MODELS:
            return VicunaModel(**kwargs)
        elif self.model in UL2_MODELS:
            return UL2Model(**kwargs)
        else:
            raise ValueError("The model is not supported!")

    @staticmethod
    def model_list():
        return MODEL_LIST

    def __call__(self, input_text, **kwargs):
        return self.infer_model.predict(input_text, **kwargs)


class T5Model(LMMBaseModel):

    def __init__(self, **kwargs):
        super(T5Model, self).__init__(**kwargs)
        from transformers import T5Tokenizer, T5ForConditionalGeneration

        self.tokenizer = T5Tokenizer.from_pretrained(
            self.model, device_map="auto")
        self.pipe = T5ForConditionalGeneration.from_pretrained(
            self.model, device_map="auto")

    def predict(self, input_text):
        input_ids = self.tokenizer(
            input_text, return_tensors="pt").input_ids.to("cuda")
        outputs = self.pipe.generate(
            input_ids, max_new_tokens=self.max_new_tokens)
        out = self.tokenizer.decode(outputs[0])
        return out


class UL2Model(LMMBaseModel):

    def __init__(self, **kwargs):
        super(UL2Model, self).__init__(**kwargs)
        from transformers import AutoTokenizer, T5ForConditionalGeneration

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model, device_map="auto")
        self.pipe = T5ForConditionalGeneration.from_pretrained(
            self.model, device_map="auto")

    def predict(self, input_text):
        input_ids = self.tokenizer(
            input_text, return_tensors="pt").input_ids.to("cuda")
        outputs = self.pipe.generate(
            input_ids, max_new_tokens=self.max_new_tokens)
        out = self.tokenizer.decode(outputs[0])
        return out


class LlamaModel(LMMBaseModel):

    def __init__(self, **kwargs):
        super(LlamaModel, self).__init__(**kwargs)
        model_dir = kwargs.get('model_dir', None)
        if not model_dir:
            raise ValueError("model_dir is required for llama model!")

        from transformers import LlamaForCausalLM, LlamaTokenizer

        self.tokenizer = LlamaTokenizer.from_pretrained(
            model_dir, device_map="auto")
        self.pipe = LlamaForCausalLM.from_pretrained(
            model_dir, device_map="auto")

    def predict(self, input_text):
        input_ids = self.tokenizer(
            input_text, return_tensors="pt").input_ids.to("cuda")
        generate_ids = self.pipe.generate(
            input_ids, max_new_tokens=self.max_new_tokens)
        out = self.tokenizer.batch_decode(
            generate_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
        return out


class VicunaModel(LMMBaseModel):

    def __init__(self, **kwargs):
        super(VicunaModel, self).__init__(**kwargs)
        model_dir = kwargs.get('model_dir', None)
        if not model_dir:
            raise ValueError("model_dir is required for llama model!")

        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_dir, device_map="auto", use_fast=False)
        self.pipe = AutoModelForCausalLM.from_pretrained(
            model_dir, device_map="auto")

    def predict(self, input_text):
        input_ids = self.tokenizer(
            input_text, return_tensors="pt").input_ids.to("cuda")
        outputs = self.pipe.generate(
            input_ids, max_new_tokens=self.max_new_tokens)
        out = self.tokenizer.decode(outputs[0])
        return out


class OpenAIModel(LMMBaseModel):

    def __init__(self, **kwargs):
        super(OpenAIModel, self).__init__(**kwargs)
        self.openai_key = kwargs.get('openai_key', None)
        self.temperature = kwargs.get('temperature', 0.0)
        self.sleep_time = kwargs.get('sleep_time', 3)
        if not self.openai_key:
            raise ValueError("openai_key is required for openai model!")

        if self.temperature > 0:
            raise Warning("Temperature is not 0, so that the results may not be reproducable!")

        if self.sleep_time > 0:
            raise Warning("We suggest to set sleep time > 0 (i.e., 5).")

    def sleep(self, seconds):
        import random
        import time
        time.sleep(seconds + random.random())

    def predict(self, input_text):
        
        import openai
        openai.api_key = self.openai_key
        try:
            while True:
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": input_text},
                    ],
                    temperature=self.temperature,
                )
                result = response['choices'][0]['message']['content']
                return result
            
        except Exception as e:
            print(e)
            print("Retrying...")
            self.sleep(self.sleep_time)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='llama2-13b-chat')
    parser.add_argument('--max_new_tokens', type=int, default=20)
    parser.add_argument('--model_dir', type=str, default='/media/Auriga/llms/llama2-13b-chat')
    args = parser.parse_args()
    # print(LLMModel.model_list())
    model = LLMModel(model=args.model, max_new_tokens=args.max_new_tokens, model_dir=args.model_dir)

    print(model('The quick brown fox jumps over the lazy dog'))