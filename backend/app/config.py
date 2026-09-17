"""Application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load .env file (does not override existing env vars)
load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment."""

    env: str = os.getenv("AVIP_ENV", "demo")
    data_dir: Path = Path(os.getenv("AVIP_DATA_DIR", "./data"))
    models_dir: Path = Path(os.getenv("AVIP_MODELS_DIR", "./ai_models"))
    demo_data_dir: Path = Path(os.getenv("AVIP_DEMO_DATA_DIR", "./demo_data"))

    # Vision LLM (GPT-4 Vision) — optional, additive to existing demo flow
    vision_llm_enabled: bool = os.getenv("AVIP_VISION_LLM", "false").lower() == "true"
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # PCBA TPI Generation multimodal provider — selects which provider drives
    # extraction + drafting for the TPI pipeline. Mirrors the AVIP_VISION_LLM /
    # OPENAI_* env pattern above. Values: "mock" (default, deterministic, no
    # network/API key) or "openai". A per-request override is also supported on
    # the process endpoint; this is the configured default.
    tpi_llm_provider: str = os.getenv("AVIP_TPI_LLM_PROVIDER", "mock")

    # Source-comparison simulator — feeds the LAIR/FAIR/SHQ pipeline with a
    # continuous stream of simulated records. Enabled by default for the demo
    # env; tests and production can disable it (AVIP_SC_SIMULATOR=false) to
    # avoid the unbounded feed. Mirrors the AVIP_VISION_LLM env pattern.
    sc_simulator_enabled: bool = (
        os.getenv("AVIP_SC_SIMULATOR", "true").lower() == "true"
    )

    # Derived paths
    @property
    def db_path(self) -> Path:
        return self.data_dir / "avip.db"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"

    @property
    def certificates_dir(self) -> Path:
        return self.data_dir / "certificates"

    @property
    def heatmaps_dir(self) -> Path:
        return self.data_dir / "heatmaps"

    def ensure_dirs(self) -> None:
        """Create all required directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.certificates_dir.mkdir(parents=True, exist_ok=True)
        self.heatmaps_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
