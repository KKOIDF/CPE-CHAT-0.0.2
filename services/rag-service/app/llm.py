import os
import torch
from typing import Optional
from .config import LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_ENABLE, LLM_4BIT

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
except Exception:
    AutoTokenizer = None  # type: ignore
    AutoModelForCausalLM = None  # type: ignore

class LLMEngine:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.tokenizer: Optional[object] = None
        self.model: Optional[object] = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_error: Optional[str] = None

    def load(self):
        if not LLM_ENABLE:
            return
        if self.model is not None:
            return
        if AutoTokenizer is None or AutoModelForCausalLM is None:
            self._load_error = "transformers not installed"
            return
        try:
            print(f"[LLM] Loading model {self.model_name} on {self.device} (4bit={LLM_4BIT}) ...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            load_kwargs = {
                'device_map': 'auto',
                'trust_remote_code': True
            }
            if self.device == 'cuda':
                if LLM_4BIT:
                    # Attempt 4-bit load
                    load_kwargs['load_in_4bit'] = True
                else:
                    load_kwargs['torch_dtype'] = torch.float16
            else:
                load_kwargs['torch_dtype'] = torch.float32
            self.model = AutoModelForCausalLM.from_pretrained(self.model_name, **load_kwargs)
            print("[LLM] Model loaded.")
        except Exception as e:
            self._load_error = str(e)
            print(f"[LLM] Load failed: {e}")

    def generate(self, prompt: str) -> str:
        if not LLM_ENABLE:
            return "(LLM disabled: set LLM_ENABLE=1 to enable generation)"
        self.load()
        if self.model is None or self.tokenizer is None:
            return f"(LLM unavailable: {self._load_error})"
        # Basic generation (prompt already contains instruction + context)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.1
            )[0]
        # Slice only generated part
        gen_ids = output_ids[inputs["input_ids"].shape[-1]:]
        text = self.tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
        return text or "(empty response)"

# Singleton
llm_engine = LLMEngine(LLM_MODEL)
