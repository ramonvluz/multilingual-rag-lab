from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    qdrant_url: str = "http://localhost:6333"
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_device: str = "cpu"
    embedding_dimension: int = 1024
    chunk_size: int = 512
    retrieval_top_k: int = 5
    rerank_top_k: int = 10
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.8-flash"
    upload_max_size: int = 10 * 1024 * 1024
    log_level: str = "INFO"
    runtime_dir: Path = Path("runtime")
