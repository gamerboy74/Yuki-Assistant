import google.generativeai as genai
import os

API_KEY = "AIzaSyDSZOzm-itHa-lLkrSUUAIyFMysW104iYQ"
genai.configure(api_key=API_KEY)

def test_api():
    print("--- Testing Google API Key ---")
    try:
        # 1. List models
        print("Available models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - {m.name} ({m.display_name})")
        
        # 2. Try a simple generation to check quota/access
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hello, respond with 'OK' if you see this.")
        print(f"\nSimple test (gemini-1.5-flash): {response.text.strip()}")

        # 3. Try Gemini 2.0/3.0 if available
        try:
            model_3 = genai.GenerativeModel('gemini-2.0-flash-exp') # Common exp name
            response_3 = model_3.generate_content("OK?")
            print(f"Advanced test (gemini-2.0-flash-exp): {response_3.text.strip()}")
        except:
            print("Gemini 2.0/3.0 specific names not found or accessible via common names.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
