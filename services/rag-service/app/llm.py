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
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_TIMEOUT_S,
    TYPHOON_API_KEY,
    TYPHOON_BASE_URL,
    TYPHOON_TIMEOUT_S,
)

import requests
import os
import json
import re
import time

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
except Exception:
    AutoTokenizer = None  # type: ignore
    AutoModelForCausalLM = None  # type: ignore
    pipeline = None  # type: ignore


# Reuse HTTP connections to remote providers (OpenAI/Typhoon) to reduce latency.
_HTTP = requests.Session()

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

        # Remote provider has no local loading.
        if (LLM_PROVIDER or '').strip().lower() == 'openai' or (self.model_name or '').startswith('gpt-'):
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

        provider = (LLM_PROVIDER or '').strip().lower()
        if provider == 'openai' or (provider == '' and (self.model_name or '').startswith('gpt-')):
            return self._generate_openai(prompt=prompt, messages=messages)
        
        if provider == 'typhoon':
            return self._generate_typhoon(prompt=prompt, messages=messages)

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

    def _generate_openai(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        if not OPENAI_API_KEY:
            return "(OpenAI unavailable: set OPENAI_API_KEY)"

        base = (OPENAI_BASE_URL or 'https://api.openai.com/v1').rstrip('/')
        debug = os.getenv('OPENAI_DEBUG', '0') in ('1', 'true', 'True')
        is_gpt5 = (self.model_name or '').startswith('gpt-5')
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json',
        }

        # For maximum compatibility across OpenAI model families, send a single text input.
        # Our `prompt` already contains system-style instructions + context.
        text_input = prompt
        msgs = [{'role': 'user', 'content': text_input}]

        # 1) Try Responses API (newer)
        try:
            url = f"{base}/responses"
            payload: Dict[str, Any] = {
                'model': self.model_name,
                'input': text_input,
                'max_output_tokens': LLM_MAX_TOKENS,
            }
            if not is_gpt5:
                payload['temperature'] = LLM_TEMPERATURE
            else:
                # Reduce reasoning so we get visible text within token budget.
                payload['reasoning'] = {'effort': 'minimal'}
                payload['text'] = {'format': {'type': 'text'}}
            resp = _HTTP.post(url, headers=headers, json=payload, timeout=OPENAI_TIMEOUT_S)
            if debug:
                print(f"[OpenAI][responses] status={resp.status_code}")
            if resp.status_code < 300:
                data = resp.json()
                # Common fields: output_text (SDK), or output[] content[] text
                if isinstance(data, dict) and data.get('output_text'):
                    return str(data.get('output_text')).strip() or '(empty response)'
                def _collect_texts(obj: Any, acc: List[str]):
                    if obj is None:
                        return
                    if isinstance(obj, str):
                        return
                    if isinstance(obj, dict):
                        t = obj.get('text')
                        if isinstance(t, str) and t.strip():
                            acc.append(t)
                        for v in obj.values():
                            _collect_texts(v, acc)
                        return
                    if isinstance(obj, list):
                        for v in obj:
                            _collect_texts(v, acc)

                out_texts: List[str] = []
                _collect_texts((data or {}).get('output'), out_texts)
                # De-duplicate while preserving order
                seen: set[str] = set()
                uniq: List[str] = []
                for t in out_texts:
                    tt = t.strip()
                    if tt and tt not in seen:
                        uniq.append(tt)
                        seen.add(tt)
                joined = '\n'.join(uniq).strip()
                if joined:
                    return joined
                if debug:
                    print('[OpenAI][responses] empty parse; raw:', resp.text[:800])
                # Some models may return reasoning-only or incomplete responses here;
                # fall back to chat.completions for a plain assistant message.
                raise RuntimeError('responses_api_empty_output')
            # If endpoint unsupported, fall through to chat completions.
        except Exception:
            pass

        # 2) Fallback to Chat Completions
        try:
            url = f"{base}/chat/completions"
            payload: Dict[str, Any] = {
                'model': self.model_name,
                'messages': msgs,
            }

            if not is_gpt5:
                payload['temperature'] = LLM_TEMPERATURE
            else:
                payload['reasoning_effort'] = 'minimal'

            # Newer OpenAI models (e.g., gpt-5*) require max_completion_tokens.
            if is_gpt5:
                payload['max_completion_tokens'] = LLM_MAX_TOKENS
            else:
                payload['max_tokens'] = LLM_MAX_TOKENS

            resp = _HTTP.post(url, headers=headers, json=payload, timeout=OPENAI_TIMEOUT_S)
            if debug:
                print(f"[OpenAI][chat.completions] status={resp.status_code}")
            if resp.status_code >= 300:
                return f"(OpenAI error {resp.status_code}: {resp.text[:300]})"
            data = resp.json()
            content = (((data or {}).get('choices') or [{}])[0].get('message') or {}).get('content')
            out = (content or '').strip()
            if out:
                return out
            if debug:
                print('[OpenAI][chat.completions] empty content; raw:', resp.text[:800])
            return '(empty response)'
        except Exception as e:
            return f"(OpenAI request failed: {e})"

    def _generate_typhoon(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        if not TYPHOON_API_KEY:
            return "(Typhoon unavailable: set TYPHOON_API_KEY)"

        base = (TYPHOON_BASE_URL or 'https://api.opentyphoon.ai/v1').rstrip('/')
        debug = os.getenv('TYPHOON_DEBUG', '0') in ('1', 'true', 'True')
        
        headers = {
            'Authorization': f'Bearer {TYPHOON_API_KEY}',
            'Content-Type': 'application/json',
        }

        # Build messages for Typhoon API
        # If messages are supplied, use them; otherwise use prompt as user message
        if messages:
            msgs = messages
        else:
            msgs = [{'role': 'user', 'content': prompt}]

        def _parse_token_error(resp_text: str) -> tuple[int, int, int] | None:
            """Return (prompt_tokens, required, provided) if resp_text matches token-limit error."""
            try:
                data = json.loads(resp_text or '')
                detail = data.get('detail') if isinstance(data, dict) else None
                if not isinstance(detail, str):
                    return None
                m = re.search(
                    r"prompt_tokens:\s*(\d+).*required:\s*(\d+).*provided:\s*(\d+)",
                    detail,
                    flags=re.IGNORECASE,
                )
                if not m:
                    return None
                return int(m.group(1)), int(m.group(2)), int(m.group(3))
            except Exception:
                return None

        def _post(payload: Dict[str, Any]) -> requests.Response:
            url = f"{base}/chat/completions"
            return _HTTP.post(url, headers=headers, json=payload, timeout=TYPHOON_TIMEOUT_S)

        def _is_transient_status(status_code: int) -> bool:
            return status_code == 429 or 500 <= status_code <= 599

        try:
            payload: Dict[str, Any] = {
                'model': self.model_name,
                'messages': msgs,
                'temperature': LLM_TEMPERATURE,
                # Typhoon's API enforces max_tokens >= prompt_tokens + 1.
                # Some deployments accept max_completion_tokens, others only max_tokens.
                'max_completion_tokens': LLM_MAX_TOKENS,
                'max_tokens': LLM_MAX_TOKENS,
                'top_p': 0.6,
                'frequency_penalty': 0,
            }

            # Retry transient provider failures (5xx/429) and network errors.
            max_retries = max(0, int(os.getenv('TYPHOON_RETRIES', '2')))
            backoff_s = max(0.1, float(os.getenv('TYPHOON_RETRY_BACKOFF_S', '2.0')))
            resp: Optional[requests.Response] = None

            for attempt in range(max_retries + 1):
                try:
                    resp = _post(payload)
                except Exception as e:
                    if attempt >= max_retries:
                        return f"(Typhoon request failed after retries: {e})"
                    sleep_s = backoff_s * (attempt + 1)
                    if debug:
                        print(f"[Typhoon][retry] request exception on attempt {attempt + 1}: {e}; sleeping {sleep_s:.1f}s")
                    time.sleep(sleep_s)
                    continue

                if debug:
                    print(f"[Typhoon][chat.completions] status={resp.status_code} attempt={attempt + 1}/{max_retries + 1}")

                # Auto-retry once when max_tokens is too small for the prompt.
                if resp.status_code == 400:
                    parsed = _parse_token_error(resp.text)
                    if parsed:
                        _prompt_tokens, required, _provided = parsed
                        margin = int(os.getenv('TYPHOON_TOKEN_MARGIN', '512'))
                        cap = int(os.getenv('TYPHOON_MAX_TOKENS_CAP', '8192'))
                        bumped = min(required + max(1, margin), cap)
                        if bumped > int(payload.get('max_tokens') or 0):
                            payload['max_tokens'] = bumped
                            payload['max_completion_tokens'] = bumped
                            resp = _post(payload)
                            if debug:
                                print(f"[Typhoon][chat.completions] retry status={resp.status_code} (max_tokens={bumped})")

                if resp.status_code < 300:
                    break

                if not _is_transient_status(resp.status_code) or attempt >= max_retries:
                    break

                sleep_s = backoff_s * (attempt + 1)
                if debug:
                    print(f"[Typhoon][retry] transient status={resp.status_code}; sleeping {sleep_s:.1f}s")
                time.sleep(sleep_s)

            if resp is None:
                return "(Typhoon request failed: no response)"

            if resp.status_code >= 300:
                if _is_transient_status(resp.status_code):
                    return "(Typhoon unavailable temporarily. Please try again in 30-60 seconds.)"
                return f"(Typhoon error {resp.status_code}: {resp.text[:300]})"
            data = resp.json()
            content = (((data or {}).get('choices') or [{}])[0].get('message') or {}).get('content')
            out = (content or '').strip()
            if out:
                return out
            if debug:
                print('[Typhoon][chat.completions] empty content; raw:', resp.text[:800])
            return '(empty response)'
        except Exception as e:
            return f"(Typhoon request failed: {e})"

# Singleton
llm_engine = LLMEngine(LLM_MODEL)
