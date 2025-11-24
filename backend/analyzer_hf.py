import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

def analyze_text(text):
    hf_token = os.getenv("HUGGINGFACE_API_KEY")
    headers = {"Authorization": f"Bearer {hf_token}"}
    
    prompt = f"""
    [INST] 
    You are a food critic assistant. Analyze the following text from a Reddit post about Toronto food.
    Extract any restaurant names mentioned. For each restaurant, determine the sentiment (0 to 10, where 10 is amazing) and a very brief summary (max 10 words).
    
    Return ONLY a valid JSON array of objects. Each object should have keys: "name", "sentiment", "summary".
    If no restaurants are mentioned, return an empty array [].

    Text:
    "{text[:1000]}" 
    [/INST]
    """

    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 500,
            "return_full_text": False,
            "temperature": 0.1
        }
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        # response.raise_for_status() # Optional: handle errors
        result = response.json()
        
        if isinstance(result, list) and len(result) > 0 and 'generated_text' in result[0]:
            generated_text = result[0]['generated_text']
            
            # Basic cleanup to find JSON array
            start_idx = generated_text.find('[')
            end_idx = generated_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx != -1:
                json_str = generated_text[start_idx:end_idx]
                return json.loads(json_str)
        return []
        
    except Exception as e:
        print(f"Error analyzing text: {e}")
        return []

if __name__ == "__main__":
    # Test the analyzer
    sample_text = "I went to Pai Northern Thai Kitchen yesterday and it was amazing. The curry was perfect. 10/10 would recommend."
    print(analyze_text(sample_text))
