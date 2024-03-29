from setuptools import find_packages, setup


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


README = read_file_or_empty_str("README.rst")
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
    description="Core package for running Movici geospatial temporal simulations",
    long_description=README,
    long_description_content_type="text/x-rst",
    author="NGinfra Movici",
    author_email="movici@nginfra.nl",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: Free for non-commercial use",
        "License :: Other/Proprietary License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Libraries",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    project_urls={
        "Homepage": "https://www.movici.nl/",
        "Documentation": "https://docs.movici.nl/",
        "Source": "https://github.com/nginfra/movici-simulation-core/",
    },
    url="http://www.movici.nl",
    license="Movici Public License",
    scripts=[
        "bin/rename_attributes.py",
    ],
    entry_points={
        "movici.plugins": [
            # fmt: off
            f"orchestrator = {SVC_PATH}.orchestrator.service:Orchestrator",
            f"update_data_service = {SVC_PATH}.update_data.service:UpdateDataService",
            f"init_data_service = {SVC_PATH}.init_data.service:InitDataService",

            "global_attributes = movici_simulation_core.attributes:GlobalAttributes",
            "common_attributes = movici_simulation_core.models.common.attributes:CommonAttributes",

            f"area_aggregation = {MODEL_PATH}.area_aggregation.model:Model",
            f"corridor = {MODEL_PATH}.corridor.model:Model",
            f"csv_player = {MODEL_PATH}.csv_player.csv_player:CSVPlayer",
            f"data_collector = {MODEL_PATH}.data_collector.data_collector:DataCollector",
            f"evacuation_point_resolution = {MODEL_PATH}.evacuation_point_resolution:EvacuatonPointResolution",  # noqa: E501
            f"generalized_journey_time = {MODEL_PATH}.generalized_journey_time.gjt_model:GJTModel",
            f"netcdf_player = {MODEL_PATH}.netcdf_player.netcdf_player:NetCDFPlayer",
            f"operational_status = {MODEL_PATH}:OperationalStatusModel",
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
    packages=find_packages(exclude=["tests*"]),
    install_requires=REQUIREMENTS,
    extras_require=EXTRA_REQUIREMENTS,
    package_data={
        "": ["*.json"],
    },
)
