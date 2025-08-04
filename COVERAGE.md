# Code Coverage Guide

This document explains how to use the code coverage system in movici-simulation-core.

## Quick Start

### Run Tests with Coverage
```bash
# Run all tests with coverage
make coverage

# Run tests with coverage (manual)
pytest tests/ --cov=movici_simulation_core --cov-report=html --cov-report=xml --cov-report=json --cov-report=term-missing
```

### View Coverage Reports
```bash
# View HTML report (most detailed)
open htmlcov/index.html

# View XML report (for CI/CD)
cat coverage.xml

# View JSON report (for scripts)
cat coverage.json

# Generate coverage summary
python scripts/coverage_summary.py
```

## Coverage Configuration

Coverage is configured in `pyproject.toml` under the `[tool.coverage.*]` sections:

### Key Settings
- **Minimum Coverage**: 80% (configurable via `fail_under`)
- **Branch Coverage**: Enabled to track conditional execution
- **Parallel Processing**: Enabled for faster execution
- **Output Formats**: HTML, XML, JSON, and terminal

### Exclusions
The following are excluded from coverage:
- Test files (`*/tests/*`, `*/test_*`)
- Setup and build files
- Documentation files
- `__init__.py` files (typically just imports)
- Abstract methods and protocol definitions
- Debug and development code

## Makefile Targets

```bash
make coverage          # Run tests with coverage and summary
make coverage-report   # Generate reports from existing .coverage file  
make coverage-clean    # Clean coverage files
make clean            # Clean all build artifacts including coverage
```

## Coverage in CI/CD

Coverage is automatically run in GitHub Actions:
- Tests run with coverage on Python 3.12 + Ubuntu
- Coverage reports uploaded to Codecov
- Builds don't fail if coverage is below threshold (configurable)

## Coverage Thresholds

| Coverage | Status | Description |
|----------|--------|-------------|
| 90%+     | 🟢 Excellent | Very high coverage |
| 80-89%   | 🟡 Good | Meets minimum standards |
| 70-79%   | 🟠 Fair | Needs improvement |
| <70%     | 🔴 Poor | Significant gaps |

## Improving Coverage

### 1. Identify Low Coverage Areas
```bash
# Run coverage and see the summary
make coverage

# Look at HTML report for detailed file-by-file view
open htmlcov/index.html
```

### 2. Common Uncovered Code Patterns
- **Error handling**: Exception paths rarely executed
- **Edge cases**: Boundary conditions and rare scenarios  
- **Abstract methods**: Base class methods meant to be overridden
- **Configuration code**: Settings and initialization
- **Integration points**: External service interactions

### 3. Writing Tests for Coverage
```python
# Test both success and failure paths
def test_function_success():
    result = my_function(valid_input)
    assert result == expected

def test_function_failure():
    with pytest.raises(ValueError):
        my_function(invalid_input)

# Test all branches
def test_conditional_branches():
    assert my_function(condition=True) == "branch_a"
    assert my_function(condition=False) == "branch_b"
```

### 4. Coverage Pragmas
Use `# pragma: no cover` to exclude specific lines:
```python
def debug_function():  # pragma: no cover
    """This function is only used for debugging"""
    print("Debug info")
```

## Coverage Reports Explained

### Terminal Report
- Shows line-by-line coverage percentages
- Lists missing line numbers
- Provides branch coverage statistics

### HTML Report  
- Interactive web interface
- Click on files to see line-by-line coverage
- Color coding: green (covered), red (missed), yellow (partial)
- Shows which branches were taken

### XML Report
- Machine-readable format for CI/CD
- Used by tools like Codecov, SonarQube
- Contains detailed metrics and line information

### JSON Report
- Programmatic access to coverage data
- Used by custom scripts and analysis tools
- Contains file-level and line-level details

## Best Practices

### 1. Aim for Meaningful Coverage
- Focus on testing business logic and critical paths
- Don't chase 100% coverage at the expense of test quality
- Prioritize testing complex algorithms and error handling

### 2. Regular Coverage Monitoring
- Check coverage reports for each PR
- Set coverage requirements in CI/CD
- Monitor coverage trends over time

### 3. Coverage vs Quality
- High coverage doesn't guarantee good tests
- Focus on testing behavior, not just execution
- Use coverage to find untested code, not as the only metric

### 4. Integration with Development
- Run coverage locally before committing
- Include coverage in code review discussions
- Use coverage to guide test planning

## Troubleshooting

### Common Issues

**PyO3 Module Initialization Error**
```bash
# If you see PyO3 errors, run tests in a fresh process
python -m pytest tests/ --cov=movici_simulation_core
```

**Low Coverage Due to Import Errors**
```bash
# Check which modules failed to import
pytest tests/ --cov=movici_simulation_core --cov-report=term-missing -v
```

**Coverage Files Not Generated**
```bash
# Ensure pytest-cov is installed
pip install pytest-cov

# Check configuration in pyproject.toml
# Ensure .coveragerc is properly formatted
```

### Getting Help
- Check pytest-cov documentation: https://pytest-cov.readthedocs.io/
- Review coverage.py docs: https://coverage.readthedocs.io/
- Open an issue if you encounter project-specific problems