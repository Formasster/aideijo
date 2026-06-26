import sys
import os
from typing import Optional

# Add parent directory to path to allow importing config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings

class CoderAgent:
    def __init__(self, system_instruction: Optional[str] = None):
        self.system_instruction = system_instruction or (
            "You are Coder, the Aideijo coding assistant. "
            "Your job is to write clean, secure, well-structured, and idiomatic code. "
            "Always include comments, follow best practices for the language, and "
            "provide step-by-step explanations of the implementation."
        )
        self.client_type = None
        self.client = None
        self.model_name = None
        self._init_llm_client()

    def _init_llm_client(self):
        """Initialize the LLM client based on available API keys in settings."""
        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
                self.client_type = "gemini"
                self.model_name = "gemini-2.5-flash"
            except Exception as e:
                print(f"Warning: Failed to load google-genai package: {e}")
                
        if not self.client and settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.client_type = "openai"
                self.model_name = "gpt-4o-mini"
            except Exception as e:
                print(f"Warning: Failed to load openai package: {e}")

        if not self.client:
            self.client_type = "mock"
            self.model_name = "mock-model"

    def generate_code(self, prompt: str) -> str:
        """
        Generate code or answer a technical prompt.
        
        Args:
            prompt (str): The instructions or request.
            
        Returns:
            str: Generated code response.
        """
        if self.client_type == "gemini":
            try:
                from google.genai import types
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=self.system_instruction,
                        temperature=0.2
                    )
                )
                return response.text
            except Exception as e:
                return f"Error in Gemini execution: {str(e)}"
                
        elif self.client_type == "openai":
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self.system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"Error in OpenAI execution: {str(e)}"
                
        else:
            return (
                "--- DRY RUN (MOCK CODER AGENT) ---\n"
                f"Prompt: {prompt}\n"
                "To run the coder assistant, please install dependencies and configure GEMINI_API_KEY or "
                "OPENAI_API_KEY in your .env file.\n"
                "Here is a template structure of what would be generated:\n"
                "```python\n"
                "# Python script template for: " + prompt[:50] + "...\n"
                "def solve():\n"
                "    pass\n"
                "```"
            )

if __name__ == "__main__":
    # Test execution
    print("Testing Coder Agent...")
    coder = CoderAgent()
    print(f"Using client type: {coder.client_type}")
    result = coder.generate_code("Write a quicksort function in Python.")
    print(result)
