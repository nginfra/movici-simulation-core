#!/usr/bin/env python3
from movici_simulation_core.legacy_base_model.base import model_factory
from movici_simulation_core.models.overlap_status.model import Model
from model_engine import execute

if __name__ == "__main__":
    execute(model_factory(Model))
