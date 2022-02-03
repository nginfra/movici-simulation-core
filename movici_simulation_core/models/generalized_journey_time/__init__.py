from pathlib import Path

from .gjt_model import GJTModel

MODEL_CONFIG_SCHEMA_PATH = Path(__file__).parent / "model_config_schema.json"
__all__ = ["MODEL_CONFIG_SCHEMA_PATH", "GJTModel"]
