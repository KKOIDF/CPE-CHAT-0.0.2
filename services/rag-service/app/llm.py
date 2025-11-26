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
    LLM_CPU_FALLBACK,
    LLM_DEVICE_MAP,
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
        self._warned = False

    def load(self):
        if not LLM_ENABLE:
            return
        # Auto recommend 4-bit for very large models if not already enabled.
        if ("30" in self.model_name or "70" in self.model_name) and not LLM_4BIT and not self._warned:
            print(f"[LLM][WARN] Large model '{self.model_name}' detected. Consider setting LLM_4BIT=1 to reduce VRAM.")
            self._warned = True
        if self.device == 'cuda' and not self._warned:
            try:
                dev_name = torch.cuda.get_device_name(0)
                free_mem, total_mem = torch.cuda.mem_get_info()
                print(f"[LLM][GPU] Device: {dev_name} | Free: {free_mem/1e9:.2f} GB / Total: {total_mem/1e9:.2f} GB")
            except Exception:
                print("[LLM][GPU] Unable to query detailed GPU memory info.")
            self._warned = True
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
                    model_kwargs=model_kwargs,
                    trust_remote_code=True
                )
                # Keep a reference to tokenizer for chat templating
                try:
                    self.tokenizer = self.pipe.tokenizer
                except Exception:
                    pass
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
                'device_map': LLM_DEVICE_MAP,
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
            # Attempt CPU fallback on OOM or quantization failures
            if ('CUDA out of memory' in str(e) or 'quantize_4bit' in str(e)) and LLM_CPU_FALLBACK:
                try:
                    print("[LLM][WARN] GPU OOM. Retrying on CPU (no 4-bit). This will be slow.")
                    self.device = 'cpu'
                    self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
                    load_kwargs = {
                        'device_map': None,
                        'trust_remote_code': True,
                        'torch_dtype': torch.float32,
                    }
                    # Remove 4bit for CPU path
                    self.model = AutoModelForCausalLM.from_pretrained(self.model_name, **load_kwargs)
                    print("[LLM] CPU fallback load complete.")
                    return
                except Exception as e2:
                    self._load_error = f"GPU OOM then CPU fallback failed: {e2}"
                    print(f"[LLM] CPU fallback failed: {e2}")
            # Recommend smaller model
            if 'CUDA out of memory' in str(e):
                print("[LLM][ADVICE] Use a smaller model (e.g. 7B/13B) or external inference API. Set LLM_MODEL to a lighter checkpoint.")
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
            # If messages supplied and tokenizer supports chat template, render to a single prompt string.
            input_payload: Union[str, List[Dict[str,str]]] = prompt
            if messages:
                try:
                    if self.tokenizer and hasattr(self.tokenizer, 'apply_chat_template'):
                        rendered = self.tokenizer.apply_chat_template(
                            messages,
                            tokenize=False,
                            add_generation_prompt=True
                        )
                        input_payload = rendered
                    else:
                        # Fallback: simple concat of roles
                        joined_parts = []
                        for m in messages:
                            role = m.get('role','user')
                            content = m.get('content','')
                            joined_parts.append(f"<{role}>: {content}")
                        input_payload = "\n".join(joined_parts) + "\nตอบ:"  # encourage answer
                except Exception as e:
                    print(f"[LLM][WARN] chat template failed: {e}")
                    input_payload = prompt
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
