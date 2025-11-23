"""Batch test for RAG + LLM answers.
Run with env:
  $env:LLM_ENABLE=1; $env:LLM_PIPELINE=1; $env:LLM_MODEL="scb10x/typhoon-v1.5-8b-instruct"
"""
import os
from time import perf_counter
from app.rag_logic import rag_query
from app.llm import llm_engine

QUESTIONS = [
    "สรุปโครงสร้างหลักสูตรวิศวกรรมคอมพิวเตอร์",
    "รายวิชาบังคับสำคัญมีอะไรบ้าง",
    "เงื่อนไขการสำเร็จการศึกษาคืออะไร",
    "วิธีการถอนรายวิชาทำอย่างไร",
]

def run_one(q: str):
    t0 = perf_counter()
    rag = rag_query(q)
    t_retrieve = perf_counter()
    answer = llm_engine.generate(rag['prompt'])
    t_answer = perf_counter()
    return {
        'question': q,
        'contexts_used': len(rag['contexts']),
        'token_est': rag['token_est'],
        'retrieve_ms': int((t_retrieve - t0)*1000),
        'answer_ms': int((t_answer - t_retrieve)*1000),
        'answer': answer,
        'prompt_head': '\n'.join(rag['prompt'].split('\n')[:20])
    }

def main():
    print("Running batch RAG+LLM test...")
    print(f"LLM_ENABLE={os.getenv('LLM_ENABLE')} PIPELINE={os.getenv('LLM_PIPELINE')} MODEL={os.getenv('LLM_MODEL')}")
    results = []
    for q in QUESTIONS:
        print(f"\n=== Q: {q}")
        r = run_one(q)
        print(f"Contexts: {r['contexts_used']} token_est={r['token_est']} retr_ms={r['retrieve_ms']} gen_ms={r['answer_ms']}")
        print("Answer preview:\n" + '\n'.join(r['answer'].split('\n')[:10]))
        results.append(r)
    print("\nSummary:")
    for r in results:
        print(f"- {r['question']} -> ctx={r['contexts_used']} gen_ms={r['answer_ms']} len={len(r['answer'])}")

if __name__ == '__main__':
    main()
