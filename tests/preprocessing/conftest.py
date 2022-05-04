def pytest_configure(config):
    config.addinivalue_line(
        "markers", "no_validate_config: use in test_dataset_creator.py to skip config validation"
    )
