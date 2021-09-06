def require_dependency(dependency, flag):
    def require_():
        if not flag:
            raise RuntimeError(f"Dependency {dependency} is required")

    return require_


try:
    from model_engine.utils.serializers import get_schema_for_parser

    HAS_MODEL_ENGINE = True

except ImportError:
    HAS_MODEL_ENGINE = False

    def get_schema_for_parser(*_, **__):
        return require_model_engine()


try:
    from movici.optional import type_code_to_data_type

    HAS_MOVICI_SDK = True

except ImportError:
    HAS_MOVICI_SDK = False

    def type_code_to_data_type(*_, **__):
        return require_sdk()


require_model_engine = require_dependency("model_engine", HAS_MODEL_ENGINE)
require_sdk = require_dependency("movici_sdk", HAS_MOVICI_SDK)
