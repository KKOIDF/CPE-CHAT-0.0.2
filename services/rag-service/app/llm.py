import os
import torch
from typing import Optional
from .config import LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_ENABLE

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
            print(f"[LLM] Loading model {self.model_name} on {self.device} ...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                trust_remote_code=True
            )
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
