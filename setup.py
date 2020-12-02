from setuptools import setup, find_packages


def parse_requirements(file):
    try:
        with open(file) as fh:
            return [r.strip("\n") for r in fh.readlines() if not r.startswith("--")]
    except FileNotFoundError:
        return ""


def read_file_or_empty_str(file):
    try:
        with open(file) as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


REQUIREMENTS = parse_requirements("requirements.txt")
README = read_file_or_empty_str("README.md")
LICENSE = read_file_or_empty_str("LICENSE")
VERSION = read_file_or_empty_str("VERSION")

setup(
    name="movici-simulation-core",
    version=VERSION,
    description="Movici Simulation Core",
    long_description=README,
    author="Pelle Koster",
    author_email="pelle.koster@nginfra.nl",
    url="http://www.movici.nl",
    license=LICENSE,
    scripts=["bin/run_time_window_status.py"],
    packages=find_packages(),
    install_requires=REQUIREMENTS,
)
