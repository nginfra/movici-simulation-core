from jsonschema import Draft7Validator


def model_config_validator(model_schema: dict):
    validator = Draft7Validator(model_schema)

    def _validate(model_config):
        validator.validate(model_config)
        return True

    return _validate
