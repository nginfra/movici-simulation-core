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


REQUIREMENTS = parse_requirements("requirements.txt")
README = read_file_or_empty_str("README.md")
LICENSE = read_file_or_empty_str("LICENSE")
VERSION = read_file_or_empty_str("VERSION", comment_tag="#")

EXTRA_REQUIREMENTS = {"models": parse_requirements("requirements-models.txt")}

setup(
    name="movici-simulation-core",
    version=VERSION,
    description="Movici Simulation Core",
    long_description=README,
    author="Pelle Koster",
    author_email="pelle.koster@nginfra.nl",
    url="http://www.movici.nl",
    license=LICENSE,
    plugins={
        "simulation-core.model": [],
    },
    scripts=[
        "bin/run_time_window_status.py",
        "bin/run_overlap_status.py",
        "bin/run_opportunity.py",
        "bin/run_area_aggregation.py",
        "bin/run_traffic_assignment_calculation.py",
        "bin/run_traffic_demand_calculation.py",
        "bin/run_traffic_kpi.py",
        "bin/run_corridor.py",
        "bin/run_unit_conversions.py",
    ],
    packages=find_packages(),
    install_requires=REQUIREMENTS,
    extras_require=EXTRA_REQUIREMENTS,
)
