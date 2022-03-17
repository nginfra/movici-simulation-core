from pathlib import Path

from .model import ShortestPathModel

MODEL_CONFIG_SCHEMA_PATH = Path(__file__).parent / "model_config_schema.json"
__all__ = ["MODEL_CONFIG_SCHEMA_PATH", "ShortestPathModel"]
