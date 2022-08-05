import shutil
import uuid
import pytest

from movici_simulation_core.attributes import GlobalAttributes
from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.moment import set_timeline_info
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.core.serialization import UpdateDataFormat
from movici_simulation_core.utils import strategies
from aequilibrae import Project


def pytest_configure(config):
    config.addinivalue_line("markers", "no_global_timeline_info")


@pytest.fixture
def global_timeline_info():
    return None


@pytest.fixture(autouse=True)
def set_global_timeline_info(global_timeline_info, request):
    if "no_global_timeline_info" in request.keywords:
        yield
    else:
        with set_timeline_info(global_timeline_info):
            yield


@pytest.fixture
def additional_attributes():
    return []


@pytest.fixture
def global_schema(additional_attributes):
    schema = AttributeSchema(attributes=additional_attributes)
    schema.use(GlobalAttributes)
    return schema


@pytest.fixture(autouse=True)
def clean_strategies(global_schema):
    strategies.set(EntityInitDataFormat(schema=global_schema))
    strategies.set(UpdateDataFormat)
    yield
    strategies.reset()


@pytest.fixture(scope="session")
def clean_project(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("clean_project") / uuid.uuid4().hex)
    project = Project()
    project.new(path)
    project.close()
    return path


@pytest.fixture(autouse=True)
def patch_aequilibrae(monkeypatch, clean_project):
    def new(self, project_dir):
        shutil.copytree(clean_project, project_dir)
        self.open(project_dir)

    monkeypatch.setattr(Project, "new", new)
