"""
Quick test script for RAG with domain support
"""
import argparse
import requests
import json

def main():
    parser = argparse.ArgumentParser(description='Test RAG with domain')
    parser.add_argument('--domain', default='curriculum', help='Domain to query (announcements, regulations, curriculum)')
    parser.add_argument('--query', '-q', required=True, help='Query string')
    parser.add_argument('--port', default=8001, type=int, help='Server port (default: 8001)')
    
    args = parser.parse_args()
    
    url = f"http://127.0.0.1:{args.port}/rag/answer"
    payload = {
        "question": args.query,
        "domain": args.domain
    }
    
    print(f"\n🔍 Query: {args.query}")
    print(f"📂 Domain: {args.domain}")
    print(f"🌐 URL: {url}")
    print("\n" + "="*70)
    
    try:
        resp = requests.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        
        data = resp.json()
        
        print(f"\n✅ Status: {resp.status_code}")
        print(f"\n💬 Answer:\n")
        print(data.get("answer", "(no answer)"))
        
        print(f"\n📚 Contexts ({len(data.get('contexts', []))}):")
        for i, ctx in enumerate(data.get("contexts", [])[:5], 1):
            source = ctx.get("source", "?")
            page_start = ctx.get("page_start", ctx.get("page", "?"))
            page_end = ctx.get("page_end", ctx.get("page", "?"))
            score = ctx.get("score_rrf", 0)
            print(f"  [{i}] {source} | p{page_start}-{page_end} | score: {score:.4f}")
        
        print(f"\n📊 Token estimate: {data.get('token_est', 0)}")
        print("="*70 + "\n")
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: Cannot connect to server at {url}")
        print("   Make sure the RAG server is running:")
        print("   cd services/rag-service && python run_server.py")
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
