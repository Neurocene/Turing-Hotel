import json
import os
import openai

def get_api_key(provider):
    if provider == "gemini":
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    elif provider == "openai":
        return os.environ.get("OPENAI_API_KEY")
    return None

def query_llm(provider, model, instructions, prompt_data, base_url=None):
    api_key = get_api_key(provider) or "lm-studio"

    if provider == "gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    elif provider == "lmstudio":
        url = base_url or "http://localhost:1234/v1"
    else:
        url = None

    client = openai.OpenAI(base_url=url, api_key=api_key)

    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": json.dumps(prompt_data, ensure_ascii=False)}
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Errore durante la generazione ({provider}): {str(e)}"
