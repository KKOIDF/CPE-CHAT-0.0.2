import os
import torch
from typing import Optional, List, Dict, Union, Any
from .config import (
    LLM_MODEL,
    LLM_AUX_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_ENABLE,
    LLM_4BIT,
    LLM_PIPELINE,
    LLM_CPU_FALLBACK,
    LLM_DEVICE_MAP,
    LLM_PROVIDER,
    LLM_AUX_PROVIDER,
    LLM_AUX_FOR_REWRITE,
    LLM_AUX_FOR_MULTIQUERY,
    LLM_AUX_FOR_ROUTING,
    LLM_AUX_FALLBACK_FOR_ANSWER,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_TIMEOUT_S,
    TYPHOON_API_KEY,
    TYPHOON_BASE_URL,
    TYPHOON_TIMEOUT_S,
    OLLAMA_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_TIMEOUT_S,
    OLLAMA_THINK,
    OLLAMA_KEEP_ALIVE,
)

import os
import json
import re
import time
import requests
from .perf import add_metric


def _estimate_tokens(text: str) -> int:
    # Rough estimator. Avoid treating every Thai character as one full token,
    # because that trims RAG context too aggressively.
    return max(1, int(len(text or '') / 2))


def _estimate_messages_tokens(messages: List[Dict[str, str]]) -> int:
    total = 0
    for m in (messages or []):
        total += _estimate_tokens(str(m.get('content') or '')) + 4
    return max(1, total)


def _trim_messages_to_budget(messages: List[Dict[str, str]], max_prompt_tokens: int) -> List[Dict[str, str]]:
    """Trim oversized user content conservatively to fit prompt-token budget."""
    msgs = [dict(m or {}) for m in (messages or [])]
    if _estimate_messages_tokens(msgs) <= max_prompt_tokens:
        return msgs

    for i in range(len(msgs) - 1, -1, -1):
        role = str(msgs[i].get('role') or '')
        if role != 'user':
            continue
        content = str(msgs[i].get('content') or '')
        if not content:
            continue
        over = _estimate_messages_tokens(msgs) - max_prompt_tokens
        remove_chars = max(100, over * 5)
        if len(content) > remove_chars:
            msgs[i]['content'] = content[: max(200, len(content) - remove_chars)]
            add_metric('prompt_trim_attempted', 1)
            if _estimate_messages_tokens(msgs) <= max_prompt_tokens:
                add_metric('prompt_trim_succeeded', 1)
                return msgs

    # Hard fallback: cap the final user message if still too large.
    if msgs:
        last = msgs[-1]
        last_content = str(last.get('content') or '')
        if last_content:
            max_chars = max(400, max_prompt_tokens * 4)
            last['content'] = last_content[:max_chars]
            msgs[-1] = last
            add_metric('prompt_trim_attempted', 1)
            if _estimate_messages_tokens(msgs) <= max_prompt_tokens:
                add_metric('prompt_trim_succeeded', 1)
            else:
                add_metric('prompt_trim_failed', 1)
    return msgs

class LLMTimeoutError(Exception):
    def __init__(self, message: str, stage: str):
        super().__init__(message)
        self.stage = stage

def _stream_chat_completion(
    url: str, 
    headers: Dict[str, str], 
    payload: Dict[str, Any], 
    first_token_timeout: float, 
    overall_timeout: float,
    max_retries: int = 1,
    debug: bool = False,
    provider: str = 'Unknown'
) -> str:
    payload['stream'] = True
    backoff_s = 0.5
    
    for attempt in range(max_retries + 1):
        try:
            start_t = time.time()
            if debug:
                print(f"[{provider}][stream] Attempt {attempt+1}/{max_retries+1}")
            # First-token connection and read timeout
            resp = _HTTP.post(url, headers=headers, json=payload, stream=True, timeout=(3.0, first_token_timeout))
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(backoff_s)
                continue
            add_metric('llm_retry_count', attempt)
            raise LLMTimeoutError(f"{provider} network timeout on start", "first_token_network")
        except Exception as e:
            if attempt < max_retries:
                time.sleep(backoff_s)
                continue
            add_metric('llm_retry_count', attempt)
            raise
            
        if resp.status_code >= 300:
            is_transient = (resp.status_code == 429 or 500 <= resp.status_code <= 599)
            if is_transient and attempt < max_retries:
                resp.close()
                time.sleep(backoff_s)
                continue
            body = resp.text[:300]
            resp.close()
            # Note: The original code handled 400 token bumping for Typhoon, 
            # but user feedback requests strictly limiting retries to transient errors.
            add_metric('llm_retry_count', attempt)
            raise RuntimeError(f"{provider} HTTP {resp.status_code}: {body}")
            
        add_metric('llm_retry_count', attempt)
        
        # Stream processing
        first_token_t = None
        accumulated = []
        try:
            for line in resp.iter_lines():
                curr_t = time.time()
                if first_token_t is None:
                    if curr_t - start_t > first_token_timeout:
                        resp.close()
                        raise LLMTimeoutError(f"{provider} first-token timeout exceeded {first_token_timeout}s", "first_token")
                
                if curr_t - start_t > overall_timeout:
                    resp.close()
                    raise LLMTimeoutError(f"{provider} overall timeout exceeded {overall_timeout}s", "overall")
                    
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith("data: "):
                        data_str = decoded[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    accumulated.append(content)
                                    if first_token_t is None:
                                        first_token_t = time.time()
                                        add_metric('llm_first_token_ms', int((first_token_t - start_t) * 1000))
                        except json.JSONDecodeError:
                            pass
        finally:
            resp.close()
            end_t = time.time()
            if first_token_t is None:
                add_metric('llm_first_token_ms', int((end_t - start_t) * 1000))
            add_metric('llm_total_ms', int((end_t - start_t) * 1000))
            
        out = "".join(accumulated).strip()
        return out or '(empty response)'

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
except Exception:
    AutoTokenizer = None  # type: ignore
    AutoModelForCausalLM = None  # type: ignore
    pipeline = None  # type: ignore


# Reuse HTTP connections to remote providers (OpenAI/Typhoon/Ollama) to reduce latency.
_HTTP = requests.Session()
_LOCAL_ENGINE_CACHE: Dict[str, "LLMEngine"] = {}


def _normalize_provider(provider: str, model_name: str = '') -> str:
    p = (provider or '').strip().lower()
    if p:
        return p
    if (model_name or '').startswith('gpt-'):
        return 'openai'
    return p


def _aux_is_configured() -> bool:
    return bool((LLM_AUX_PROVIDER or '').strip() and (LLM_AUX_MODEL or '').strip())


def _selection_matches(provider: str, model_name: str, other_provider: str, other_model: str) -> bool:
    return _normalize_provider(provider, model_name) == _normalize_provider(other_provider, other_model) and (model_name or '').strip() == (other_model or '').strip()


def _is_diagnostic_response(text: str) -> bool:
    t = str(text or '').strip()
    if not t:
        return True
    if t == '(empty response)':
        return True
    if t.startswith('('):
        return True
    if 'ไม่พบข้อมูลนี้ในเอกสารที่ค้นได้' in t:
        return True
    if 'ไม่พบข้อความยืนยันโดยตรง' in t:
        return True
    return False


def _resolve_task_selection(task: str = 'answer', requested_model: str = '') -> tuple[str, str]:
    req = (requested_model or '').strip()
    primary_provider = _normalize_provider(LLM_PROVIDER, LLM_MODEL)
    primary_model = (LLM_MODEL or '').strip()
    aux_provider = _normalize_provider(LLM_AUX_PROVIDER, LLM_AUX_MODEL)
    aux_model = (LLM_AUX_MODEL or '').strip()

    if req:
        if req == primary_model:
            return primary_provider, primary_model
        if _aux_is_configured() and req == aux_model:
            return aux_provider, aux_model

    task_key = (task or 'answer').strip().lower()
    if _aux_is_configured():
        if task_key == 'rewrite' and LLM_AUX_FOR_REWRITE:
            return aux_provider, aux_model
        if task_key == 'multiquery' and LLM_AUX_FOR_MULTIQUERY:
            return aux_provider, aux_model
        if task_key == 'routing' and LLM_AUX_FOR_ROUTING:
            return aux_provider, aux_model

    return primary_provider, primary_model

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

    def load(self, provider_override: Optional[str] = None):
        if not LLM_ENABLE:
            return

        provider = _normalize_provider(provider_override or LLM_PROVIDER, self.model_name)
        # Remote providers have no local loading.
        if provider in ('openai', 'typhoon', 'ollama') or (self.model_name or '').startswith('gpt-'):
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

    def generate(
        self,
        prompt: str,
        messages: Optional[List[Dict[str, str]]] = None,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> str:
        if not LLM_ENABLE:
            return "(LLM disabled: set LLM_ENABLE=1 to enable generation)"

        model_name = (model_override or self.model_name or '').strip()
        provider = _normalize_provider(provider_override or LLM_PROVIDER, model_name)

        if model_name and model_name != (self.model_name or '').strip() and provider not in ('openai', 'typhoon', 'ollama'):
            temp_engine = _LOCAL_ENGINE_CACHE.get(model_name)
            if temp_engine is None:
                temp_engine = LLMEngine(model_name)
                _LOCAL_ENGINE_CACHE[model_name] = temp_engine
            return temp_engine.generate(prompt, messages=messages, provider_override=provider, model_override=model_name)

        try:
            if provider == 'openai':
                return self._generate_openai(prompt=prompt, messages=messages, model_name=model_name)
            
            if provider == 'typhoon':
                return self._generate_typhoon(prompt=prompt, messages=messages, model_name=model_name)

            if provider == 'ollama':
                return self._generate_ollama(prompt=prompt, messages=messages, model_name=model_name)
        except LLMTimeoutError as e:
            add_metric('fallback_reason', f"{e.stage}_timeout")
            add_metric('timeout_stage', e.stage)
            return "(TIMEOUT_FALLBACK)"
        except Exception as e:
            if "LLMTimeoutError" in str(e) or "timeout" in str(e).lower():
                add_metric('fallback_reason', 'nested_timeout')
                add_metric('timeout_stage', 'nested')
                return "(TIMEOUT_FALLBACK)"
            # Log the exception but do not crash the service if called from legacy orchestrators
            print(f"[LLM][ERROR] generate failed: {e}")
            return f"(Error: {e})"

        self.load(provider_override=provider)
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

    def _stream_and_enforce_timeouts(self, url: str, headers: Dict[str, str], payload: Dict[str, Any], provider_name: str, debug: bool = False) -> str:
        from .perf import add_metric
        
        # Hard limits per user requirements
        first_token_timeout = float(os.getenv(f'{provider_name.upper()}_FIRST_TOKEN_TIMEOUT_S', '3.0'))
        overall_timeout = float(os.getenv(f'{provider_name.upper()}_OVERALL_TIMEOUT_S', '15.0'))
        max_retries = 1
        
        for attempt in range(max_retries + 1):
            start_t = time.time()
            first_token_ms = -1
            collected_text = []
            
            try:
                # Use stream=True to get chunks
                with _HTTP.post(url, headers=headers, json=payload, stream=True, timeout=(first_token_timeout, first_token_timeout)) as resp:
                    if resp.status_code >= 300:
                        if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                            time.sleep(0.5)
                            continue
                        else:
                            return f"({provider_name} error {resp.status_code})"
                    
                    got_first_token = False
                    
                    for line in resp.iter_lines():
                        if time.time() - start_t > overall_timeout:
                            add_metric('timeout_stage', 'overall')
                            raise TimeoutError("overall")
                            
                        if not line:
                            continue
                        
                        decoded = line.decode('utf-8')
                        if decoded.startswith('data: '):
                            data_str = decoded[6:]
                            if data_str.strip() == '[DONE]':
                                break
                            try:
                                data = json.loads(data_str)
                                delta = data.get('choices', [{}])[0].get('delta', {})
                                content = delta.get('content')
                                if content:
                                    if not got_first_token:
                                        got_first_token = True
                                        first_token_ms = int((time.time() - start_t) * 1000)
                                    collected_text.append(content)
                            except Exception:
                                pass
                    
                    # Success
                    total_ms = int((time.time() - start_t) * 1000)
                    add_metric('llm_first_token_ms', first_token_ms if first_token_ms >= 0 else total_ms)
                    add_metric('llm_total_ms', total_ms)
                    add_metric('llm_retry_count', attempt)
                    return "".join(collected_text).strip()
                    
            except Exception as e:
                if str(e) == "overall":
                    add_metric('llm_retry_count', attempt)
                    add_metric('fallback_reason', 'overall_timeout')
                    raise TimeoutError(f"{provider_name} overall timeout exceeded")
                
                # Assume first_token delay / network issue
                if attempt < max_retries:
                    add_metric('timeout_stage', 'first_token')
                    time.sleep(0.5)
                    continue
                else:
                    add_metric('llm_retry_count', attempt)
                    add_metric('fallback_reason', 'first_token_timeout')
                    raise TimeoutError(f"{provider_name} first-token timeout exceeded")
                    
        return "(LLM Generation Failed)"

    def _generate_openai(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None, model_name: Optional[str] = None) -> str:
        if not OPENAI_API_KEY:
            return "(OpenAI unavailable: set OPENAI_API_KEY)"

        base = (OPENAI_BASE_URL or 'https://api.openai.com/v1').rstrip('/')
        debug = os.getenv('OPENAI_DEBUG', '0') in ('1', 'true', 'True')
        selected_model = (model_name or self.model_name or '').strip()
        is_gpt5 = selected_model.startswith('gpt-5')
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json',
        }

        msgs = messages or [{'role': 'user', 'content': prompt}]
        model_limit = int(os.getenv('LLM_MODEL_CONTEXT_LIMIT', '8192') or '8192')
        reserve_output = max(64, int(os.getenv('LLM_OUTPUT_RESERVE_TOKENS', '256') or '256'))
        prompt_tokens = _estimate_messages_tokens(msgs)
        if prompt_tokens + reserve_output > model_limit:
            add_metric('prompt_oversized_guard_triggered', 1)
            msgs = _trim_messages_to_budget(msgs, max(512, model_limit - reserve_output))
            prompt_tokens = _estimate_messages_tokens(msgs)
        url = f"{base}/chat/completions"
        payload: Dict[str, Any] = {
            'model': selected_model,
            'messages': msgs,
            'stream': True,
        }

        if not is_gpt5:
            payload['temperature'] = LLM_TEMPERATURE
        else:
            payload['reasoning_effort'] = os.getenv('OPENAI_REASONING_EFFORT', 'low')

        if is_gpt5:
            payload['max_completion_tokens'] = LLM_MAX_TOKENS
        else:
            payload['max_tokens'] = LLM_MAX_TOKENS

        first_token_timeout = float(os.getenv('OPENAI_FIRST_TOKEN_TIMEOUT_S', '3.0'))
        overall_timeout = float(os.getenv('OPENAI_OVERALL_TIMEOUT_S', '15.0'))
        
        try:
            return _stream_chat_completion(
                url=url,
                headers=headers,
                payload=payload,
                first_token_timeout=first_token_timeout,
                overall_timeout=overall_timeout,
                max_retries=1, # strictly 1 retry allowed
                debug=debug,
                provider='OpenAI'
            )
        except Exception as e:
            if not isinstance(e, LLMTimeoutError):
                add_metric('llm_total_ms', 0)
                add_metric('llm_first_token_ms', 0)
            raise e

    def _generate_typhoon(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None, model_name: Optional[str] = None) -> str:
        if not TYPHOON_API_KEY:
            return "(Typhoon unavailable: set TYPHOON_API_KEY)"

        selected_model = (model_name or self.model_name or '').strip()
        base = (TYPHOON_BASE_URL or 'https://api.opentyphoon.ai/v1').rstrip('/')
        debug = os.getenv('TYPHOON_DEBUG', '0') in ('1', 'true', 'True')
        
        headers = {
            'Authorization': f'Bearer {TYPHOON_API_KEY}',
            'Content-Type': 'application/json',
        }

        # Build messages for Typhoon API
        msgs = messages or [{'role': 'user', 'content': prompt}]
        model_limit = int(os.getenv('LLM_MODEL_CONTEXT_LIMIT', '8192') or '8192')
        reserve_output = max(64, int(os.getenv('LLM_OUTPUT_RESERVE_TOKENS', '256') or '256'))
        completion_tokens = max(1, int(LLM_MAX_TOKENS or 1))
        prompt_tokens = _estimate_messages_tokens(msgs)

        if prompt_tokens + reserve_output > model_limit:
            add_metric('prompt_oversized_guard_triggered', 1)
            msgs = _trim_messages_to_budget(msgs, max(512, model_limit - reserve_output))
            prompt_tokens = _estimate_messages_tokens(msgs)

        # Typhoon can validate against total tokens; keep max_tokens above prompt+1.
        safe_total_max_tokens = max(prompt_tokens + 1, prompt_tokens + completion_tokens)
        url = f"{base}/chat/completions"

        payload: Dict[str, Any] = {
            'model': selected_model,
            'messages': msgs,
            'temperature': LLM_TEMPERATURE,
            'max_completion_tokens': completion_tokens,
            'max_tokens': safe_total_max_tokens,
            'top_p': 0.6,
            'frequency_penalty': 0,
            'stream': True,
        }

        first_token_timeout = float(os.getenv('TYPHOON_FIRST_TOKEN_TIMEOUT_S', '3.0'))
        overall_timeout = float(os.getenv('TYPHOON_OVERALL_TIMEOUT_S', '15.0'))
        
        try:
            return _stream_chat_completion(
                url=url,
                headers=headers,
                payload=payload,
                first_token_timeout=first_token_timeout,
                overall_timeout=overall_timeout,
                max_retries=1, # strictly 1 retry allowed for transient errors
                debug=debug,
                provider='Typhoon'
            )
        except Exception as e:
            if not isinstance(e, LLMTimeoutError):
                add_metric('llm_total_ms', 0)
                add_metric('llm_first_token_ms', 0)
            raise e

    def _generate_ollama(self, prompt: str, messages: Optional[List[Dict[str, str]]] = None, model_name: Optional[str] = None) -> str:
        selected_model = (model_name or self.model_name or '').strip()
        base = (OLLAMA_BASE_URL or 'http://localhost:11434').rstrip('/')
        debug = os.getenv('OLLAMA_DEBUG', '0') in ('1', 'true', 'True')

        headers = {
            'Content-Type': 'application/json',
        }
        if OLLAMA_API_KEY:
            headers['Authorization'] = f'Bearer {OLLAMA_API_KEY}'

        msgs = messages or [{'role': 'user', 'content': prompt}]
        model_limit = int(os.getenv('LLM_MODEL_CONTEXT_LIMIT', '8192') or '8192')
        reserve_output = max(64, int(os.getenv('LLM_OUTPUT_RESERVE_TOKENS', '256') or '256'))
        prompt_tokens = _estimate_messages_tokens(msgs)
        if prompt_tokens + reserve_output > model_limit:
            add_metric('prompt_oversized_guard_triggered', 1)
            msgs = _trim_messages_to_budget(msgs, max(512, model_limit - reserve_output))

        url = f"{base}/api/chat"
        payload: Dict[str, Any] = {
            'model': selected_model,
            'messages': msgs,
            'stream': True,
            'think': bool(OLLAMA_THINK),
            'options': {
                'temperature': LLM_TEMPERATURE,
                'num_predict': LLM_MAX_TOKENS,
            },
        }
        if OLLAMA_KEEP_ALIVE:
            payload['keep_alive'] = OLLAMA_KEEP_ALIVE

        first_token_timeout = float(os.getenv('OLLAMA_FIRST_TOKEN_TIMEOUT_S', '10.0'))
        overall_timeout = float(os.getenv('OLLAMA_OVERALL_TIMEOUT_S', str(OLLAMA_TIMEOUT_S or 120.0)))
        backoff_s = 0.5
        max_retries = 1

        for attempt in range(max_retries + 1):
            try:
                start_t = time.time()
                if debug:
                    print(f"[Ollama][stream] Attempt {attempt+1}/{max_retries+1}")
                resp = _HTTP.post(url, headers=headers, json=payload, stream=True, timeout=(3.0, first_token_timeout))
            except requests.exceptions.Timeout:
                if attempt < max_retries:
                    time.sleep(backoff_s)
                    continue
                add_metric('llm_retry_count', attempt)
                raise LLMTimeoutError("Ollama network timeout on start", "first_token_network")
            except Exception:
                if attempt < max_retries:
                    time.sleep(backoff_s)
                    continue
                add_metric('llm_retry_count', attempt)
                raise

            if resp.status_code >= 300:
                is_transient = (resp.status_code == 429 or 500 <= resp.status_code <= 599)
                if is_transient and attempt < max_retries:
                    resp.close()
                    time.sleep(backoff_s)
                    continue
                body = resp.text[:300]
                resp.close()
                add_metric('llm_retry_count', attempt)
                raise RuntimeError(f"Ollama HTTP {resp.status_code}: {body}")

            add_metric('llm_retry_count', attempt)
            first_token_t = None
            accumulated = []
            try:
                for line in resp.iter_lines():
                    curr_t = time.time()
                    if first_token_t is None and curr_t - start_t > first_token_timeout:
                        resp.close()
                        raise LLMTimeoutError(f"Ollama first-token timeout exceeded {first_token_timeout}s", "first_token")
                    if curr_t - start_t > overall_timeout:
                        resp.close()
                        raise LLMTimeoutError(f"Ollama overall timeout exceeded {overall_timeout}s", "overall")
                    if not line:
                        continue

                    try:
                        chunk = json.loads(line.decode('utf-8'))
                    except json.JSONDecodeError:
                        continue

                    content = str((((chunk.get('message') or {}).get('content')) or ''))
                    if content:
                        accumulated.append(content)
                        if first_token_t is None:
                            first_token_t = time.time()
                            add_metric('llm_first_token_ms', int((first_token_t - start_t) * 1000))
                    if chunk.get('done'):
                        break
            finally:
                resp.close()
                end_t = time.time()
                if first_token_t is None:
                    add_metric('llm_first_token_ms', int((end_t - start_t) * 1000))
                add_metric('llm_total_ms', int((end_t - start_t) * 1000))

            out = "".join(accumulated).strip()
            return out or '(empty response)'

        return "(Ollama Generation Failed)"


def generate_text(
    prompt: str,
    messages: Optional[List[Dict[str, str]]] = None,
    *,
    task: str = 'answer',
    requested_model: str = '',
) -> str:
    provider, model_name = _resolve_task_selection(task=task, requested_model=requested_model)
    add_metric('llm_task', task)
    add_metric('llm_selected_provider', provider or 'local')
    add_metric('llm_selected_model', model_name or llm_engine.model_name or '')

    out = llm_engine.generate(
        prompt,
        messages=messages,
        provider_override=provider,
        model_override=model_name or None,
    )

    if task == 'answer' and not (requested_model or '').strip() and _aux_is_configured() and LLM_AUX_FALLBACK_FOR_ANSWER:
        primary_provider = _normalize_provider(LLM_PROVIDER, LLM_MODEL)
        primary_model = (LLM_MODEL or '').strip()
        aux_provider = _normalize_provider(LLM_AUX_PROVIDER, LLM_AUX_MODEL)
        aux_model = (LLM_AUX_MODEL or '').strip()
        used_primary = _selection_matches(provider, model_name, primary_provider, primary_model)
        if used_primary and _is_diagnostic_response(out):
            add_metric('llm_aux_fallback_attempt', 1)
            aux_out = llm_engine.generate(
                prompt,
                messages=messages,
                provider_override=aux_provider,
                model_override=aux_model or None,
            )
            if not _is_diagnostic_response(aux_out):
                add_metric('llm_aux_fallback_success', 1)
                add_metric('llm_selected_provider', aux_provider or 'local')
                add_metric('llm_selected_model', aux_model or '')
                return aux_out
    return out


def list_configured_models() -> List[Dict[str, str]]:
    models: List[Dict[str, str]] = []
    primary_provider = _normalize_provider(LLM_PROVIDER, LLM_MODEL) or 'local'
    primary_model = (LLM_MODEL or '').strip()
    if primary_model:
        models.append({'id': primary_model, 'provider': primary_provider, 'role': 'primary'})

    aux_provider = _normalize_provider(LLM_AUX_PROVIDER, LLM_AUX_MODEL) or 'local'
    aux_model = (LLM_AUX_MODEL or '').strip()
    if aux_model and not any(m.get('id') == aux_model for m in models):
        models.append({'id': aux_model, 'provider': aux_provider, 'role': 'aux'})
    return models


# Singleton
llm_engine = LLMEngine(LLM_MODEL)
