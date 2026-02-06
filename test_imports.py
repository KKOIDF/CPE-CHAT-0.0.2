#!/usr/bin/env python3
"""Test if the app can import without errors"""
import sys
import os

# Add app directory to path
sys.path.insert(0, r'c:\Users\KritChaJ\CPE-CHAT-0.0.2\services\rag-service')

try:
    print("Importing app.config...")
    from app.config import TYPHOON_API_KEY, TYPHOON_BASE_URL, LLM_PROVIDER, LLM_MODEL
    print(f"✅ Config loaded")
    print(f"   LLM_PROVIDER: {LLM_PROVIDER}")
    print(f"   LLM_MODEL: {LLM_MODEL}")  
    print(f"   TYPHOON_API_KEY: {'***' + TYPHOON_API_KEY[-10:] if TYPHOON_API_KEY else '(not set)'}")
    print(f"   TYPHOON_BASE_URL: {TYPHOON_BASE_URL}")
    
    print("\nImporting app.llm...")
    from app.llm import llm_engine
    print(f"✅ LLM engine created: {llm_engine.model_name}")
    
    print("\nTesting _generate_typhoon method exists...")
    if hasattr(llm_engine, '_generate_typhoon'):
        print("✅ _generate_typhoon method exists")
    else:
        print("❌ _generate_typhoon method NOT found!")
        
    print("\nImporting app.main...")
    from app.main import app
    print("✅ FastAPI app loaded successfully")
    
    print("\n✅ All imports successful!")
    
except Exception as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
