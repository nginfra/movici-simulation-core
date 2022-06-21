import json
import logging
import shutil
import tempfile
import typing as t
from pathlib import Path

from movici_simulation_core.base_models.simple_model import SimpleModelAdapter
from movici_simulation_core.base_models.tracked_model import TrackedModel, TrackedModelAdapter
from movici_simulation_core.core import (
    EntityInitDataFormat,
    Model,
    UpdateDataFormat,
    dump_update,
    load_update,
)
from movici_simulation_core.core.data_format import dump_dataset_data
from movici_simulation_core.core.moment import set_timeline_info
from movici_simulation_core.core.schema import AttributeSchema, AttributeSpec
from movici_simulation_core.core.types import Extensible, ModelAdapterBase
from movici_simulation_core.messages import (
    NewTimeMessage,
    QuitMessage,
    UpdateMessage,
    UpdateSeriesMessage,
)
from movici_simulation_core.model_connector.init_data import (
    DirectoryInitDataHandler,
    InitDataHandler,
)
from movici_simulation_core.settings import Settings
from movici_simulation_core.testing.helpers import compare_dataset_dicts
from movici_simulation_core.types import (
    DataMask,
    NextTime,
    RawResult,
    RawUpdateData,
    Result,
    UpdateData,
)
from movici_simulation_core.utils import strategies


class PreProcessor:
    def __init__(self, model: Model, settings: Settings, schema=None):
        self.settings = settings
        self.schema = schema or AttributeSchema()
        self.schema.add_attributes(model.get_schema_attributes())
        adapter = model.get_adapter()
        self.model = adapter(model, settings, logging.getLogger())
        self.model.set_schema(self.schema)

    def process_input(self, input_data: UpdateData) -> RawUpdateData:
        raise NotImplementedError

    def process_result(self, result: RawResult) -> Result:
        raise NotImplementedError

    def initialize(self, data_handler: InitDataHandler) -> DataMask:
        return self.model.initialize(data_handler)

    def update(self, msg: UpdateMessage, data) -> Result:
        data = self.process_input(data)
        return self.process_result(self.model.update(msg, data))

    def update_series(self, msg: UpdateSeriesMessage, data_series) -> Result:
        data_series = map(self.process_input, data_series)
        return self.process_result(self.model.update_series(msg, data_series))

    def new_time(self, message: NewTimeMessage):
        return self.model.new_time(message)

    def close(self, message: QuitMessage):
        return self.model.close(message)


class NumpyPreProcessor(PreProcessor):
    def __init__(self, model: TrackedModel, settings: Settings, schema=None):
        super().__init__(model, settings, schema)
        self.parser = EntityInitDataFormat(schema)

    def process_input(self, input_data: UpdateData) -> RawUpdateData:
        if input_data is None:
            return None
        array_data = self.parser.load_json(input_data)
        return dump_update(array_data)

    def process_result(self, result: RawResult) -> Result:
        data, next_time = result
        if data is not None:
            data = dump_dataset_data(load_update(data))
        return data, next_time


DEFAULT_PREPROCESSORS: t.Dict[t.Type[ModelAdapterBase], t.Type[PreProcessor]] = {
    TrackedModelAdapter: NumpyPreProcessor,
    SimpleModelAdapter: NumpyPreProcessor,
}


class Plugin(t.Protocol):
    def install(cls, obj: Extensible):
        pass


SchemaT = t.Union[AttributeSchema, t.Sequence[AttributeSpec], Plugin]


def read_schema(schema: t.Optional[SchemaT]) -> AttributeSchema:
    if isinstance(schema, AttributeSchema):
        return schema
    rv = AttributeSchema()
    if isinstance(schema, t.Sequence) and len(schema) > 0 and isinstance(schema[0], AttributeSpec):
        rv.add_attributes(schema)
    elif hasattr(schema, "install"):
        rv.use(schema)
    elif schema is not None:
        rv.add_from_namespace(schema)

    return rv


NEXT_TIME_MISSING = -2


class ModelTester:
    def __init__(
        self,
        model,
        settings: Settings = None,
        init_data_handler=None,
        tmp_dir=None,
        schema: t.Optional[SchemaT] = None,
        raise_on_premature_shutdown=False,
    ):
        """

        :param model:
        :param settings:
        :param init_data_handler:
        :param tmp_dir:
        :param schema: Can be one of
          - An AttributeSchema object
          - An sequence (eg, list or tuple) of AttributeSpec objects
          - A Namespace (ie module, containing AttributeSpec objects
          - A `Plugin` that registers attributes
        """
        self.tmp_dir = Path(tmp_dir or tempfile.mkdtemp())
        self.init_data_handler = init_data_handler or DirectoryInitDataHandler(self.tmp_dir)
        self.settings = settings or Settings()
        self.schema = read_schema(schema)
        self._set_default_strategies()
        self.model = self._try_wrap_model(model)
        self.raise_on_premature_shutdown = raise_on_premature_shutdown

    def _set_default_strategies(self):
        strategies.set(UpdateDataFormat)
        strategies.set(EntityInitDataFormat(schema=self.schema))

    def _try_wrap_model(self, model: Model):
        adapter = model.get_adapter()
        if not (preprocessor := DEFAULT_PREPROCESSORS.get(adapter)):
            raise TypeError(f"Unsupported model adapter {adapter.__name__}")
        return preprocessor(model, settings=self.settings, schema=self.schema)

    def add_init_data(self, name: str, data: t.Union[dict, str, Path]):
        if isinstance(data, dict):
            self.tmp_dir.joinpath(f"{name}.json").write_text(json.dumps(data))
            return
        path = Path(data)
        if not path.is_file():
            raise ValueError(f"{data} is not a valid file")
        target = (self.tmp_dir / name).with_suffix(path.suffix)
        shutil.copyfile(path, target)

    def initialize(self):
        return self.model.initialize(self.init_data_handler)

    def update(self, timestamp: int, data: UpdateData, **msg_kwargs):
        message = UpdateMessage(timestamp, **msg_kwargs)
        return self.model.update(message, data)

    def update_series(self, timestamp: int, data_series: t.Sequence[UpdateData], **msg_kwargs):
        message = UpdateSeriesMessage(
            [UpdateMessage(timestamp, **msg_kwargs) for _ in data_series]
        )
        return self.model.update_series(message, data_series)

    def new_time(self, timestamp: int):
        message = NewTimeMessage(timestamp)
        self.model.new_time(message)

    def close(self):
        try:
            self.model.close(QuitMessage())
        except RuntimeError:
            if self.raise_on_premature_shutdown:
                raise

    @classmethod
    def run_scenario(
        cls,
        model: t.Type[Model],
        model_name: str,
        scenario: dict,
        rtol=1e-5,
        atol=1e-8,
        use_new_time=True,
        global_schema: t.Any = None,
    ):
        try:
            model_config = next(
                filter(lambda m: m["name"] == model_name, scenario["config"]["models"])
            )
        except (KeyError, StopIteration) as e:
            raise ValueError(f"model {model_name} not found in scenario") from e
        settings = Settings()
        settings.apply_scenario_config(scenario["config"])

        expected = [
            (exp["time"], exp["data"], exp.get("next_time", NEXT_TIME_MISSING))
            for exp in scenario.get("expected_results", [])
        ]

        inst = model(model_config)
        with set_timeline_info(settings.timeline_info):
            tester = ModelTester(
                inst, settings, schema=global_schema, raise_on_premature_shutdown=True
            )
            for init_data in scenario.get("init_data", []):
                tester.add_init_data(**init_data)

            tester.initialize()

            curr_time = None
            results: t.List[t.Tuple[int, UpdateData, NextTime]] = []
            for upd in scenario.get("updates"):
                time, data = upd["time"], upd["data"]
                if use_new_time and time != curr_time:
                    curr_time = time
                    tester.new_time(time)
                data, next_time = tester.update(time, data)
                results.append((time, data, next_time))
            tester.close()

        errors = compare_results(expected, results, rtol, atol)
        if errors:
            raise AssertionError(format_errors(errors))


ErrorList = t.List[t.Tuple[int, t.Dict[str, str]]]


def compare_results(
    expected: t.Sequence[t.Tuple[int, UpdateData, NextTime]],
    results: t.Sequence[t.Tuple[int, UpdateData, NextTime]],
    rtol=1e-5,
    atol=1e-8,
) -> ErrorList:
    if len(expected) != len(results):
        raise ValueError(
            f"Length of results [{len(results)}" f" doesnt match expected [{len(expected)}"
        )
    errors = []
    for (t_result, result, nt_result), (t_expected, expected_data, nt_expected) in zip(
        results, expected
    ):
        if nt_expected not in (NEXT_TIME_MISSING, nt_result):
            errors.append((t_expected, {"next_time": f"Expected {nt_expected}, got: {nt_result}"}))

        if t_result != t_expected:
            errors.append((t_expected, {"timestamp": f"timestamp differs: {t_result}"}))
            continue
        if result is None and expected_data is None:
            continue
        if result is None or expected_data is None:
            errors.append((t_expected, {"result": f"Expected {expected_data}, got: {result}"}))
        elif compare_errors := compare_dataset_dicts(expected_data, result, rtol, atol):
            errors.append((t_expected, compare_errors))
    return errors


def format_errors(errors: ErrorList):
    return "\n".join(f"t={ts}: {key}: {msg}" for ts, d in errors for key, msg in d.items())
