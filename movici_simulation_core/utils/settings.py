from __future__ import annotations

import tempfile
import typing as t
from pathlib import Path

from pydantic import BaseSettings, Field, DirectoryPath
from movici_simulation_core.utils.moment import TimelineInfo


class Settings(BaseSettings):
    name: str = ""
    timeline_info: t.Optional[TimelineInfo] = None
    models: t.List[dict] = Field(default_factory=list, env="")
    model_names: t.List[str] = Field(default_factory=list, env="")
    service_types: t.List[str] = Field(default_factory=list, env="")
    datasets: t.List[dict] = Field(default_factory=list, env="")
    scenario_config: t.Optional[dict] = Field(default=None, env="")

    log_level: str = "INFO"
    log_format: str = "[{asctime}] [{levelname:8s}] {name:17s}: {message}"
    data_dir: DirectoryPath = "."
    service_discovery: t.Dict[str, str] = Field(default_factory=dict, env="")

    storage: t.Union[t.Literal["api"], t.Literal["disk"]] = "disk"
    storage_dir: t.Optional[Path] = None
    temp_dir: DirectoryPath = str(tempfile.gettempdir())

    class Config:
        env_prefix = "movici_"
        fields = {
            "timeline_info": {"env": ""},
            "log_level": {"env": ["log_level", "loglevel"]},
            "log_format": {"env": ["log_format", "logformat"]},
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
