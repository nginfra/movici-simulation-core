#!/usr/bin/env python3
from movici_simulation_core.base_model.base import model_factory
from movici_simulation_core.models.traffic_kpi.model import Model
from model_engine import execute

if __name__ == "__main__":
    execute(model_factory(Model))
