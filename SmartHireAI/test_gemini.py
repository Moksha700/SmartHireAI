import google.generativeai as genai
from config import GEMINI_API_KEY

def test_gemini_api():
    try:
        # Configure the API
        genai.configure(api_key=GEMINI_API_KEY)
        
        # List available models
        print("Attempting to list models...")
        models = genai.list_models()
        print(f"Available models: {[m.name for m in models]}")
        
        # Try a simple generation
        print("\nTesting model generation...")
        model = genai.GenerativeModel('models/gemini-pro-latest')
        response = model.generate_content("Write 'Hello, World!'")
        print(f"Test response: {response.text}")
        
        return True, "API test successful"
    except Exception as e:
        return False, f"API test failed: {str(e)}"

if __name__ == "__main__":
    success, message = test_gemini_api()
    print(f"\nTest result: {'Success' if success else 'Failed'}")
    print(f"Message: {message}")