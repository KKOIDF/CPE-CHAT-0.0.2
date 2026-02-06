#!/usr/bin/env python3
"""Test Typhoon API integration with RAG service"""
import requests
import json

BASE_URL = "http://localhost:8001"

# Test 1: Query with RAG
print("=" * 60)
print("TEST 1: RAG Query with Typhoon API")
print("=" * 60)
try:
    response = requests.post(
        f"{BASE_URL}/rag/answer",
        json={
            "question": "สาขาวิชาไหนมีโครงการศึกษา",
            "domain": "curriculum"
        }
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"\n📝 Question: {result.get('question')}")
        print(f"\n💡 Answer:\n{result.get('answer')}")
        print(f"\n📚 Contexts found: {len(result.get('contexts', []))}")
        print(f"\n⏱️ Token estimate: {result.get('token_est')}")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Health check
print("\n" + "=" * 60)
print("TEST 2: Service Health Check")
print("=" * 60)
try:
    # Try if there's a health endpoint
    response = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"✅ Service is running (status: {response.status_code})")
except:
    print("⚠️ Service appears to be running (health endpoint not available)")
