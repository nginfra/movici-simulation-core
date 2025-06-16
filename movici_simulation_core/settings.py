from __future__ import annotations

import tempfile
import typing as t
from pathlib import Path

from pydantic import DirectoryPath, Field

try:
    from pydantic import BaseSettings
    PYDANTIC_V1 = True
except ImportError:
    from pydantic_settings import BaseSettings
    from pydantic import ConfigDict
    PYDANTIC_V1 = False

from movici_simulation_core.core.moment import TimelineInfo


class Settings(BaseSettings):
    data_dir: DirectoryPath = "."
    log_level: str = "INFO"
    log_format: str = "[{asctime}] [{levelname:8s}] {name:17s}: {message}"
    name: str = ""
    storage: t.Union[t.Literal["api"], t.Literal["disk"]] = "disk"
    storage_dir: t.Optional[Path] = None
    temp_dir: DirectoryPath = str(tempfile.gettempdir())

    reference: float = 0
    time_scale: float = 1
    start_time: int = 0
    duration: int = 0

    datasets: t.List[dict] = Field(default_factory=list)
    model_names: t.List[str] = Field(default_factory=list)
    models: t.List[dict] = Field(default_factory=list)
    service_types: t.List[str] = Field(default_factory=list)
    scenario_config: t.Optional[dict] = Field(default=None)
    service_discovery: t.Dict[str, str] = Field(default_factory=dict)

    if PYDANTIC_V1:
        class Config:
            env_prefix = "movici_"
            fields = {
                "log_level": {"env": ["movici_log_level", "movici_loglevel"]},
                "log_format": {"env": ["movici_log_format", "movici_logformat"]},
            }
    else:
        model_config = ConfigDict(
            env_prefix="movici_",
            extra="forbid",
            protected_namespaces=('settings_',),
        )
        # Note: Pydantic V2 doesn't support multiple env names in the same way as V1
        # The functionality to use multiple environment variable names has been removed

    def apply_scenario_config(self, config: dict):
        self.scenario_config = config
        if simulation_info := config.get("simulation_info"):
            if simulation_info.pop("mode", "time_oriented") == "time_oriented":
                self.start_time = simulation_info["start_time"]
                self.time_scale = simulation_info["time_scale"]
                self.reference = simulation_info["reference_time"]
                self.duration = simulation_info["duration"]
        self.models = config.get("models", [])
        self.model_names = [model["name"] for model in self.models]
        self.service_types = config.get("services", [])
        self.datasets = config.get("datasets", [])

    # Dataclasses in pydantic Models don't pickle properly
    # (https://github.com/samuelcolvin/pydantic/issues/3453). This is fine in Linux as we use
    # forked processes (which bypasses the issues), but in Windows that is not available. So
    # instead, as a workaround, we use a property to pack and unpack the TimelineInfo dataclass
    # into its fields.
    #
    # However, now we run into a different issue where pydantic doesn't support property setters
    # (https://github.com/samuelcolvin/pydantic/issues/3395). So we have to use another workaround
    # involving __setattr__

    @property
    def timeline_info(self):
        return TimelineInfo(
            start_time=self.start_time,
            time_scale=self.time_scale,
            reference=self.reference,
            duration=self.duration,
        )

    @timeline_info.setter
    def timeline_info(self, timeline_info: TimelineInfo):
        self.start_time = timeline_info.start_time
        self.time_scale = timeline_info.time_scale
        self.reference = timeline_info.reference
        self.duration = timeline_info.duration

    def __setattr__(self, name, value):
        if name in ("timeline_info"):
            object.__setattr__(self, name, value)
        else:
            super().__setattr__(name, value)
