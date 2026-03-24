import sys
import os
import json
import time
from pathlib import Path

# Add rag-service to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../services/rag-service')))

from app.routing import infer_domain
from app.retrieval import retrieve_all_domains

def run_eval(cases_file: str):
    cases_path = Path(cases_file)
    if not cases_path.exists():
        print(f"File {cases_file} not found")
        return

    cases = json.loads(cases_path.read_text(encoding='utf-8'))
    
    results_by_domain = {}
    total = 0
    correct_domain = 0
    correct_retrieval = 0

    print(f"Running evaluation on {len(cases)} cases from {cases_file}...")

    for case in cases:
        q = case.get('question')
        expected_domain = case.get('expected_domain')
        if expected_domain == "multi":
            continue
            
        must_contain = case.get('expected_source_contains', [])

        total += 1
        
        # Test routing
        inferred = infer_domain(q)
        domain_match = (inferred == expected_domain)
        if domain_match:
            correct_domain += 1
            
        # Test retrieval
        k_vec = 20
        k_kw = 30
        
        hits = retrieve_all_domains(q, k_vec=k_vec, k_kw=k_kw)
        
        hit_sources = [str(h.get('source') or h.get('path') or '').lower() for h in hits]
        
        source_found = True
        for expected in must_contain:
            found = False
            for src in hit_sources:
                if expected.lower() in src:
                    found = True
                    break
            if not found:
                source_found = False
                break
                
        if source_found:
            correct_retrieval += 1
            
        # Track by domain
        dom = expected_domain or "unknown"
        if dom not in results_by_domain:
            results_by_domain[dom] = {"total": 0, "routing_correct": 0, "retrieval_correct": 0}
            
        results_by_domain[dom]["total"] += 1
        if domain_match:
            results_by_domain[dom]["routing_correct"] += 1
        if source_found:
            results_by_domain[dom]["retrieval_correct"] += 1

    print("\n--- Domain-by-Domain Metrics ---")
    for dom, stats in results_by_domain.items():
        t = stats["total"]
        if t == 0: continue
        r_acc = (stats["routing_correct"] / t) * 100
        ret_acc = (stats["retrieval_correct"] / t) * 100
        print(f"Domain '{dom}' (Total: {t}):")
        print(f"  Routing Accuracy:   {stats['routing_correct']}/{t} ({r_acc:.1f}%)")
        print(f"  Retrieval Accuracy: {stats['retrieval_correct']}/{t} ({ret_acc:.1f}%)")
        
    print("\n--- Overall Metrics ---")
    print(f"Total Cases Tested:  {total}")
    if total > 0:
        print(f"Routing Accuracy:    {correct_domain}/{total} ({(correct_domain/total)*100:.1f}%)")
        print(f"Retrieval Accuracy:  {correct_retrieval}/{total} ({(correct_retrieval/total)*100:.1f}%)")

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'data/hard_negatives.json'
    run_eval(target)
