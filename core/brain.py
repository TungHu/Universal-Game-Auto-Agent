"""
brain.py - AI Agent bridge
Support: Gemini, OpenAI, Claude, Groq, DeepSeek, OpenRouter, Ollama
Doc prompt.txt, thay {board} bang du lieu that, gui cho AI, parse response

API key priority:
  1. config["providers"][provider]["api_key"]
  2. Environment variable (e.g. OPENAI_API_KEY)

Model priority:
  1. --model CLI arg (config["model"])
  2. config["providers"][provider]["model"]
  3. Hardcoded default
"""

import os
import re


class AIConnectionError(Exception):
    """Loi ket noi AI"""
    pass


class BaseBrain:
    """Base class cho AI providers"""

    PROVIDERS = {
        "gemini", "openai", "claude", "groq", "deepseek", "openrouter", "ollama"
    }
    ENV_MAP = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }

    def __init__(self, config: dict):
        self.config = config
        self.provider = config.get("ai_provider", "gemini")

    def _get_provider_config(self) -> dict:
        """Lay cau hinh cho provider hien tai: api_key + model"""
        providers = self.config.get("providers", {})
        prov_cfg = providers.get(self.provider, {})

        # API key: providers section -> env var
        api_key = prov_cfg.get("api_key", "")
        if not api_key:
            env_var = self.ENV_MAP.get(self.provider, "")
            api_key = os.environ.get(env_var, "")

        # Model: --model CLI -> providers section -> default
        model = self.config.get("model")  # tu --model CLI
        if not model:
            model = prov_cfg.get("model", "")

        return {"api_key": api_key, "model": model}

    def load_prompt(self, prompt_path: str) -> str:
        """Doc prompt tu file"""
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def format_prompt(self, prompt_template: str, board_state: str) -> str:
        """Thay {board} bang du lieu that"""
        return prompt_template.replace("{board}", board_state)

    def think(self, prompt: str) -> str:
        """Gui prompt cho AI, tra ve hanh dong"""
        if self.provider == "gemini":
            return self._think_gemini(prompt)
        elif self.provider in ("openai", "claude", "groq", "deepseek", "openrouter"):
            return self._think_openai_compatible(prompt)
        elif self.provider == "ollama":
            return self._think_ollama(prompt)
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}")

    def _think_gemini(self, prompt: str) -> str:
        """Gui prompt cho Gemini (dung google.genai)"""
        try:
            from google import genai
        except ImportError:
            raise ImportError("google-genai not installed. Run: pip install google-genai")

        prov_cfg = self._get_provider_config()
        api_key = prov_cfg["api_key"]
        if not api_key:
            raise AIConnectionError(
                "Gemini API key not found.\n"
                "  -> Add to config.json: providers.gemini.api_key\n"
                "  -> Or set GEMINI_API_KEY environment variable"
            )

        model = prov_cfg["model"] or "gemini-2.0-flash"

        client = genai.Client(api_key=api_key)
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            return response.text.strip().lower()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                raise AIConnectionError(
                    "Gemini API quota exceeded (429).\n"
                    "  -> Thu lai sau vai phut\n"
                    "  -> Hoac dung model khac: --model gemini-1.5-flash\n"
                    "  -> Hoac dung Ollama (local, free): --provider ollama"
                )
            raise

    def _think_openai_compatible(self, prompt: str) -> str:
        """
        Gui prompt cho cac provider tuong thich OpenAI:
        - openai, claude, groq, deepseek, openrouter
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

        # API endpoints cho tung provider
        provider_endpoints = {
            "openai": "https://api.openai.com/v1",
            "claude": "https://api.anthropic.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "deepseek": "https://api.deepseek.com/v1",
            "openrouter": "https://openrouter.ai/api/v1",
        }
        default_models = {
            "openai": "gpt-4o-mini",
            "claude": "claude-3-haiku-20240307",
            "groq": "llama3-8b-8192",
            "deepseek": "deepseek-chat",
            "openrouter": "openai/gpt-4o-mini",
        }

        prov_cfg = self._get_provider_config()
        api_key = prov_cfg["api_key"]
        if not api_key:
            env_var = self.ENV_MAP.get(self.provider, "")
            raise AIConnectionError(
                f"{self.provider.title()} API key not found.\n"
                f"  -> Add to config.json: providers.{self.provider}.api_key\n"
                f"  -> Or set {env_var} environment variable"
            )

        base_url = self.config.get("api_url", provider_endpoints.get(self.provider))
        model = prov_cfg["model"] or default_models.get(self.provider, "gpt-4o-mini")

        try:
            import httpx
            client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                http_client=httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))
            )

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            error_str = str(e)
            if "connect" in error_str.lower() or "refused" in error_str.lower() or "timeout" in error_str.lower():
                raise AIConnectionError(
                    f"Khong the ket noi toi {self.provider.title()} tai {base_url}.\n"
                    f"  -> Kiem tra internet connection\n"
                    f"  -> Kiem tra API key"
                )
            raise

    def _think_ollama(self, prompt: str) -> str:
        """Gui prompt cho Ollama (local)"""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

        prov_cfg = self._get_provider_config()
        base_url = self.config.get("ollama_url", "http://localhost:11434/v1")
        model = prov_cfg["model"] or "llama3.2"

        try:
            import httpx
            client = OpenAI(
                base_url=base_url,
                api_key="ollama",
                http_client=httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0))
            )
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            error_msg = str(e)
            if "connect" in error_msg.lower() or "refused" in error_msg.lower() or "timeout" in error_msg.lower():
                raise AIConnectionError(
                    f"Khong the ket noi Ollama tai {base_url}.\n"
                    f"  -> Cai dat Ollama: https://ollama.com\n"
                    f"  -> Sau do chay: ollama pull {model}\n"
                    f"  -> Va khoi dong: ollama serve"
                )
            raise