import shutil
import uuid

import pytest
from aequilibrae import Project

# Shared fixtures (additional_attributes, global_schema, clean_strategies,
# set_global_timeline_info, etc.) are provided by the movici_testing pytest
# plugin registered in pyproject.toml.


@pytest.fixture(scope="session")
def clean_aequilibrae_project(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("clean_aequilibrae_project") / uuid.uuid4().hex)
    project = Project()
    if hasattr(project, "_new_original"):
        project._new_original(path)
    else:
        project.new(path)
    project.close()
    return path


@pytest.fixture
def patch_aequilibrae(monkeypatch, clean_aequilibrae_project):
    def new(self, project_dir):
        shutil.copytree(clean_aequilibrae_project, project_dir)
        self.open(project_dir)

    if not hasattr(Project, "_new_original"):
        Project._new_original = Project.new
    monkeypatch.setattr(Project, "new", new)
