from pathlib import Path

from movici_simulation_core.utils.moment import TimelineInfo, string_to_datetime
from movici_simulation_core.postprocessing.results import SimulationResults

EXAMPLES_DIR = Path(__file__).parent
INIT_DATA_DIR = EXAMPLES_DIR / "data"
UPDATES_DIR = EXAMPLES_DIR / "updates"

if __name__ == "__main__":
    timeline_info = TimelineInfo(
        reference=string_to_datetime("2020").timestamp(), time_scale=1, start_time=0
    )
    results = SimulationResults(INIT_DATA_DIR, UPDATES_DIR, timeline_info=timeline_info)
    dataset = results.get_dataset("antennas_test")
    print(
        "Slicing a dataset over a specific timestamp",
        dataset.slice("antenna_entities", timestamp="2020"),
        sep="\n",
    )
    print(
        "Slicing a dataset over a specific attribute",
        dataset.slice("antenna_entities", attribute="antennas.connected_people"),
        sep="\n",
    )
    print(
        "Slicing a dataset over a specific entity (entity ID 12)",
        dataset.slice("antenna_entities", entity_selector=12),
        sep="\n",
    )
