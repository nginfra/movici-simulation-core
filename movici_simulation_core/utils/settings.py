from __future__ import annotations

import tempfile
import typing as t
from pathlib import Path

from pydantic import BaseSettings, Field, DirectoryPath
from movici_simulation_core.utils.moment import TimelineInfo


class Settings(BaseSettings):
    data_dir: DirectoryPath = "."
    log_level: str = "INFO"
    log_format: str = "[{asctime}] [{levelname:8s}] {name:17s}: {message}"
    name: str = ""
    storage: t.Union[t.Literal["api"], t.Literal["disk"]] = "disk"
    storage_dir: t.Optional[Path] = None
    temp_dir: DirectoryPath = str(tempfile.gettempdir())

    timeline_info: t.Optional[TimelineInfo] = Field(default=None, env="")
    datasets: t.List[dict] = Field(default_factory=list, env="")
    model_names: t.List[str] = Field(default_factory=list, env="")
    models: t.List[dict] = Field(default_factory=list, env="")
    service_types: t.List[str] = Field(default_factory=list, env="")
    scenario_config: t.Optional[dict] = Field(default=None, env="")
    service_discovery: t.Dict[str, str] = Field(default_factory=dict, env="")

    class Config:
        env_prefix = "movici_"
        fields = {
            "log_level": {"env": ["movici_log_level", "movici_loglevel"]},
            "log_format": {"env": ["movici_log_format", "movici_logformat"]},
        }

    def apply_scenario_config(self, config: dict):
        self.scenario_config = config
        if simulation_info := config.get("simulation_info"):
            if simulation_info.pop("mode", "time_oriented") == "time_oriented":
                self.timeline_info = TimelineInfo(
                    start_time=simulation_info["start_time"],
                    time_scale=simulation_info["time_scale"],
                    reference=simulation_info["reference_time"],
                    duration=simulation_info["duration"],
                )
        self.models = config.get("models", [])
        self.model_names = [model["name"] for model in self.models]
        self.service_types = config.get("services", [])
        self.datasets = config.get("datasets", [])
