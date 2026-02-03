"""
Simple test for Ollama connection (without loading full RAG dependencies)
"""
import os

# Set environment
os.environ['LLM_ENABLE'] = '1'
os.environ['LLM_PROVIDER'] = 'ollama'
os.environ['LLM_MODEL'] = 'scb10x/typhoon2.5-qwen3-30b-a3b'

print("🧪 Testing Ollama Connection")
print("=" * 60)
print(f"Model: {os.environ['LLM_MODEL']}")
print(f"Provider: {os.environ['LLM_PROVIDER']}")
print()

try:
    import ollama
    print("✅ Ollama package imported successfully")
    print()
    
    # Test 1: Check Ollama server
    print("Test 1: Checking Ollama server...")
    try:
        models = ollama.list()
        print(f"✅ Ollama server is running")
        model_list = models.get('models', [])
        print(f"   Available models: {len(model_list)}")
        available_names = []
        for model in model_list:
            # Try different keys
            name = model.get('name') or model.get('model') or str(model)
            print(f"   - {name}")
            available_names.append(name)
        print()
    except Exception as e:
        print(f"❌ Ollama server connection failed: {e}")
        print()
        print("💡 To fix:")
        print("   1. Install Ollama: curl -fsSL https://ollama.com/install.sh | sh")
        print("   2. Start server: ollama serve")
        exit(1)
    
    # Test 2: Try to generate (this will auto-pull if model exists in Ollama registry)
    model_name = os.environ['LLM_MODEL']
    
    print(f"Test 2: Testing model '{model_name}'...")
    print("   (Will attempt to use the model directly)")
    print()
    
    # Test 2: Try to generate (this will auto-pull if model exists in Ollama registry)
    model_name = os.environ['LLM_MODEL']
    
    print(f"Test 2: Testing model '{model_name}'...")
    print("   (Will attempt to use the model directly)")
    print()
    
    # Test 3: Simple generation
    print("Test 3: Testing text generation...")
    print()
    
    prompt = "สวัสดีครับ ตอบสั้นๆ ว่าคุณคือใคร"
    print(f"Prompt: {prompt}")
    print()
    
    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt,
            options={'num_predict': 100}
        )
        
        answer = response.get('response', '').strip()
        print(f"Response:\n{answer}")
        print()
        
        if answer:
            print("✅ Generation successful!")
            print()
            print("=" * 60)
            print("🎉 All tests passed! Ollama is ready to use.")
            print()
            print("Next steps:")
            print("  1. Install full dependencies: pip install -r requirements.txt")
            print("  2. Run full test: python3 test_ollama_typhoon.py")
            print("  3. Start RAG service:")
            print("     export LLM_ENABLE=1")
            print("     export LLM_PROVIDER=ollama")
            print(f"     export LLM_MODEL={model_name}")
            print("     python3 run_server.py")
        else:
            print("❌ Empty response from model")
    except Exception as e:
        print(f"❌ Model generation failed: {e}")
        print()
        print("💡 Common issues:")
        print("   1. Model not found - try: ollama pull scb10x/typhoon2.5-qwen3-30b-a3b")
        print("   2. Model name might need :latest tag")
        print()
        print("   Available models on this system:")
        for name in available_names:
            print(f"   - {name}")
        print()
        print("   Try one of these by setting:")
        if available_names:
            print(f"   export LLM_MODEL=\"{available_names[0]}\"")
        exit(1)
        
except ImportError as e:
    print(f"❌ Failed to import ollama: {e}")
    print()
    print("💡 To fix:")
    print("   pip install ollama")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
