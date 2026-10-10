from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    data_path: str = "data/flooding_smart_grid_dataset.csv"
    model_dir: str = "models/saved"
    db_path: str = "models/alerts.db"

    # Model hyperparameters
    rf_threshold_percentile: float = 95.0
    if_contamination: float = 0.05
    if_n_estimators: int = 200
    rf_n_estimators: int = 200
    ensemble_if_weight: float = 0.6  # RF weight = 1 - this

    # API
    cors_origins: str = "http://localhost:8080"
    api_key: str = ""  # empty = no auth

    @property
    def model_path(self) -> Path:
        return Path(self.model_dir) / "ensemble_detector.pkl"

    @property
    def ensemble_rf_weight(self) -> float:
        return 1.0 - self.ensemble_if_weight


settings = Settings()
