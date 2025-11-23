import os
import torch
from typing import Optional, List, Dict, Union, Any
from .config import (
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_ENABLE,
    LLM_4BIT,
    LLM_PIPELINE,
)

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
except Exception:
    AutoTokenizer = None  # type: ignore
    AutoModelForCausalLM = None  # type: ignore
    pipeline = None  # type: ignore

class LLMEngine:
    def __init__(self, model_name: str):
        self.model_name = model_name
        # We deliberately use 'Any' to silence static analysis complaints for dynamic HF objects.
        self.tokenizer: Any = None
        self.model: Any = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipe: Any = None
        self._load_error: Optional[str] = None

    def load(self):
        if not LLM_ENABLE:
            return
        # Use pipeline path if requested
        if LLM_PIPELINE:
            if self.pipe is not None:
                return
            if pipeline is None:
                self._load_error = "transformers.pipeline not available"
                return
            try:
                print(f"[LLM] Loading pipeline for {self.model_name} (4bit={LLM_4BIT}) ...")
                model_kwargs: Dict[str, Any] = {}
                if self.device == 'cuda':
                    if LLM_4BIT:
                        model_kwargs['load_in_4bit'] = True
                    else:
                        model_kwargs['torch_dtype'] = torch.float16
                # Note: pipeline() does not accept device_map directly for text-generation in some versions.
                # We rely on HF accelerate auto device placement via model_kwargs.
                self.pipe = pipeline(
                    task="text-generation",
                    model=self.model_name,
                    model_kwargs=model_kwargs
                )
                print("[LLM] Pipeline loaded.")
            except Exception as e:
                self._load_error = str(e)
                print(f"[LLM] Pipeline load failed: {e}")
            return

        # Direct model path
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

    def generate(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        if not LLM_ENABLE:
            return "(LLM disabled: set LLM_ENABLE=1 to enable generation)"
        self.load()
        # Pipeline path
        if LLM_PIPELINE:
            if self.pipe is None:
                return f"(LLM pipeline unavailable: {self._load_error})"
            # Prefer messages (chat style) if provided; else use raw prompt.
            input_payload: Union[str, List[Dict[str,str]]] = messages if messages else prompt
            try:
                out = self.pipe(
                    input_payload,
                    max_new_tokens=LLM_MAX_TOKENS,
                    temperature=LLM_TEMPERATURE,
                    do_sample=True,
                    top_p=0.9,
                    return_full_text=False
                )
                if isinstance(out, list):
                    # HF pipeline returns list of dicts
                    first = out[0]
                    generated = first.get('generated_text') or first.get('text') or ''
                else:
                    generated = str(out)
                return generated.strip() or "(empty response)"
            except Exception as e:
                return f"(pipeline error: {e})"

        if self.model is None or self.tokenizer is None:
            return f"(LLM unavailable: {self._load_error})"
        inputs = self.tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs,
                max_new_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.1
            )[0]
        gen_ids = output_ids[inputs["input_ids"].shape[-1]:]
        text = self.tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
        return text or "(empty response)"

# Singleton
llm_engine = LLMEngine(LLM_MODEL)
