"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)
load_dotenv(ROOT / "backend" / ".env", override=False)


class Settings(BaseModel):
    app_name: str = "ChargeWise AI"
    version: str = "0.1.0"
    hf_token: str = ""
    hf_base_url: str = "https://router.huggingface.co/v1"
    hf_model: str = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16"
    # Nemotron-3-Nano is served on Featherless via Inference Providers.
    hf_provider: str = "featherless-ai"
    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"
    nebius_model: str = ""
    nemotron_base_url: str = ""
    nemotron_model: str = ""
    cloud_inference_enabled: bool = False
    cloud_budget_usd: float = Field(default=.05, gt=0, le=30)
    cloud_max_requests: int = Field(default=12, ge=1, le=100)
    cloud_max_tokens: int = Field(default=1024, ge=64, le=2048)
    default_charger_count: int = 10
    default_station_power_kw: float = 80.0
    default_slot_minutes: int = 15
    default_charger_power_kw: float = 11.0
    max_upload_bytes: int = 2 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings(
        hf_token=os.getenv("HF_TOKEN", ""),
        hf_base_url=os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1").rstrip("/"),
        hf_model=os.getenv("HF_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16"),
        hf_provider=os.getenv("HF_PROVIDER", "featherless-ai").strip(),
        nebius_api_key=os.getenv("NEBIUS_API_KEY", ""),
        nebius_base_url=os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1").rstrip("/"),
        nebius_model=os.getenv("NEBIUS_MODEL", ""),
        nemotron_base_url=os.getenv("NEMOTRON_BASE_URL", "").rstrip("/"),
        nemotron_model=os.getenv("NEMOTRON_MODEL", ""),
        cloud_inference_enabled=os.getenv("CLOUD_INFERENCE_ENABLED", "false").lower() == "true",
        cloud_budget_usd=os.getenv("CLOUD_INFERENCE_BUDGET_USD", ".05"),
        cloud_max_requests=os.getenv("CLOUD_INFERENCE_MAX_REQUESTS", "12"),
        cloud_max_tokens=os.getenv("CLOUD_INFERENCE_MAX_TOKENS", "1024"),
    )
