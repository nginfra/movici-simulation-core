from setuptools import setup, find_packages


def parse_requirements(file):
    try:
        with open(file) as fh:
            return [r.strip("\n") for r in fh.readlines() if not r.startswith("--")]
    except FileNotFoundError:
        return ""


def read_file_or_empty_str(file, comment_tag=None):
    try:
        with open(file) as fh:
            if comment_tag is not None:
                return "\n".join(
                    r.strip("\n") for r in fh.readlines() if not r.startswith(comment_tag)
                )
            return fh.read()
    except FileNotFoundError:
        return ""


README = read_file_or_empty_str("README.md")
LICENSE = read_file_or_empty_str("LICENSE")
VERSION = read_file_or_empty_str("VERSION", comment_tag="#")

REQUIREMENTS = parse_requirements("requirements.txt")
EXTRA_REQUIREMENTS = {
    "models": parse_requirements("requirements-models.txt"),
    "dev": parse_requirements("requirements-dev.txt"),
    "docs": parse_requirements("requirements-docs.txt"),
}
EXTRA_REQUIREMENTS["all"] = (
    EXTRA_REQUIREMENTS["models"] + EXTRA_REQUIREMENTS["dev"] + EXTRA_REQUIREMENTS["docs"]
)

MODEL_PATH = "movici_simulation_core.models"
SVC_PATH = "movici_simulation_core.services"
setup(
    name="movici-simulation-core",
    version=VERSION,
    description="Movici Simulation Core",
    long_description=README,
    author="Pelle Koster",
    author_email="pelle.koster@nginfra.nl",
    url="http://www.movici.nl",
    license=LICENSE,
    scripts=[
        "bin/rename_attributes.py",
    ],
    entry_points={
        "movici.plugins": [
            # fmt: off
            f"orchestrator = {SVC_PATH}.orchestrator.service:Orchestrator",
            f"update_data_service = {SVC_PATH}.update_data.service:UpdateDataService",
            f"init_data_service = {SVC_PATH}.init_data.service:InitDataService",

            "global_attributes = movici_simulation_core.core.attributes:GlobalAttributes",
            "common_attributes = movici_simulation_core.models.common.attributes:CommonAttributes",

            f"area_aggregation = {MODEL_PATH}.area_aggregation.model:Model",
            f"corridor = {MODEL_PATH}.corridor.model:Model",
            f"csv_player = {MODEL_PATH}.csv_player.csv_player:CSVPlayer",
            f"data_collector = {MODEL_PATH}.data_collector.data_collector:DataCollector",
            f"generalized_journey_time = {MODEL_PATH}.generalized_journey_time.gjt_model:GJTModel",
            f"opportunities = {MODEL_PATH}.opportunities.model:Model",
            f"overlap_status = {MODEL_PATH}.overlap_status.model:Model",
            f"shortest_path = {MODEL_PATH}.shortest_path.model:ShortestPathModel",
            f"tape_player = {MODEL_PATH}.tape_player.model:Model",
            f"time_window_status = {MODEL_PATH}.time_window_status.model:Model",
            f"traffic_assignment_calculation = {MODEL_PATH}.traffic_assignment_calculation.model:Model",  # noqa: E501
            f"traffic_demand_calculation = {MODEL_PATH}.traffic_demand_calculation.model:TrafficDemandCalculation",  # noqa: E501
            f"traffic_kpi = {MODEL_PATH}.traffic_kpi.model:Model",
            f"udf = {MODEL_PATH}.udf_model.udf_model:UDFModel",
            f"unit_conversions = {MODEL_PATH}.unit_conversions.model:Model",
            # fmt: on
        ],
    },
    packages=find_packages(),
    install_requires=REQUIREMENTS,
    extras_require=EXTRA_REQUIREMENTS,
    include_package_data=True,
    package_data={
        "movici_simulation_core.json_schemas": ["*"],
    },
)
