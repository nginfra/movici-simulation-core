import json
from pathlib import Path
from tempfile import mkdtemp

from movici_simulation_core import AttributeSpec, Simulation
from movici_simulation_core.models import DataCollectorModel, UDFModel

input_dir = mkdtemp(prefix="movici-input-")
output_dir = mkdtemp(prefix="movici-output-")

dataset = {
    "figures": {
        "square_entities": {
            "id": [1, 2],
            "shape.edge_length": [10.0, 20.0],
        }
    }
}

Path(input_dir).joinpath("figures.json").write_text(json.dumps(dataset))

sim = Simulation(data_dir=input_dir, storage_dir=output_dir)
sim.register_attributes(
    [
        AttributeSpec("shape.edge_length", data_type=float),
        AttributeSpec("shape.area", data_type=float),
    ]
)
sim.add_model(
    "square_maker",
    UDFModel(
        {
            "entity_group": [["figures", "square_entities"]],
            "inputs": {"length": [None, "shape.edge_length"]},
            "functions": [
                {
                    "expression": "length * length",
                    "output": [None, "shape.area"],
                },
            ],
        }
    ),
)
sim.add_model("data_collector", DataCollectorModel({}))

sim.run()
print(f"results stored in {output_dir}")
