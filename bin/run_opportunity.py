#!/usr/bin/env python3
from model_engine import execute
from movici_simulation_core.legacy_base_model.base import model_factory
from movici_simulation_core.models.opportunities.model import Model

if __name__ == "__main__":
    execute(model_factory(Model))
