"""Application configuration."""

import os
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings loaded from environment."""

    env: str = os.getenv("AVIP_ENV", "demo")
    data_dir: Path = Path(os.getenv("AVIP_DATA_DIR", "./data"))
    models_dir: Path = Path(os.getenv("AVIP_MODELS_DIR", "./ai_models"))
    demo_data_dir: Path = Path(os.getenv("AVIP_DEMO_DATA_DIR", "./demo_data"))

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
