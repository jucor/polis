"""
Pytest configuration and fixtures for delphi tests.

This module provides:
- Command line options --include-local and --datasets for dataset selection
- Fixtures for accessing dataset information
- @pytest.mark.use_discovered_datasets for dynamic dataset parametrization
- Helper functions for parallel test execution with xdist_group markers
- require_dynamodb() and require_s3() helpers for failing fast when services are unavailable
"""

import pytest
from polismath.regression.datasets import (
    discover_datasets,
    list_regression_datasets,
)


def require_dynamodb(
    endpoint: str | None = None,
    timeout: float = 3.0,
) -> None:
    """Fail the test immediately if DynamoDB is not responding.

    Performs a ``list_tables`` call with short timeouts and zero retries
    so the test fails in seconds rather than hanging indefinitely.
    """
    import os

    import boto3
    from botocore.config import Config

    endpoint = endpoint or os.environ.get(
        "DYNAMODB_ENDPOINT", "http://localhost:8000"
    )
    cfg = Config(
        connect_timeout=timeout,
        read_timeout=timeout,
        retries={"max_attempts": 0},
    )
    client = boto3.client(
        "dynamodb",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
        config=cfg,
    )
    try:
        client.list_tables(Limit=1)
    except Exception as exc:
        pytest.fail(f"DynamoDB is not available at {endpoint}: {exc}")


def require_s3(
    endpoint: str | None = None,
    timeout: float = 3.0,
) -> None:
    """Skip the test if S3/MinIO is not responding.

    Uses pytest.skip (not fail) because MinIO is a local dev service
    that is not available in CI.
    """
    import os

    import boto3
    from botocore.config import Config

    endpoint = endpoint or os.environ.get(
        "AWS_S3_ENDPOINT", "http://host.docker.internal:9000"
    )
    cfg = Config(
        connect_timeout=timeout,
        read_timeout=timeout,
        retries={"max_attempts": 0},
        signature_version="s3v4",
    )
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin"),
        config=cfg,
        verify=False,
    )
    try:
        client.list_buckets()
    except Exception as exc:
        pytest.skip(f"S3/MinIO is not available at {endpoint}: {exc}")


# =============================================================================
# Parallel Execution Helpers
# =============================================================================

def make_dataset_params(datasets: list[str]) -> list:
    """
    Create pytest.param objects with xdist_group markers for parallel execution.

    When using pytest-xdist with --dist=loadgroup, tests with the same
    xdist_group marker will run on the same worker. This ensures fixtures
    are computed only once per dataset per worker.

    Args:
        datasets: List of dataset names

    Returns:
        List of pytest.param objects with xdist_group markers

    Example:
        @pytest.mark.parametrize("dataset_name", make_dataset_params(["biodiversity", "vw"]))
        def test_something(dataset_name):
            ...
    """
    return [
        pytest.param(ds, marks=pytest.mark.xdist_group(ds))
        for ds in datasets
    ]


def pytest_addoption(parser):
    """Add custom command line options to pytest."""
    parser.addoption(
        "--include-local",
        action="store_true",
        default=False,
        help="Include datasets from real_data/.local/ in tests"
    )
    parser.addoption(
        "--datasets",
        action="store",
        default=None,
        help="Comma-separated list of datasets to run (e.g., --datasets=biodiversity,vw)"
    )


def _get_requested_datasets(config) -> set[str] | None:
    """Get the set of datasets requested via --datasets, or None for all."""
    datasets_opt = config.getoption("--datasets")
    if not datasets_opt:
        return None

    # Split on commas, strip whitespace, and drop empty entries to avoid
    # treating trailing/repeated commas as empty dataset names.
    requested = {d.strip() for d in datasets_opt.split(",") if d.strip()}

    if not requested:
        raise pytest.UsageError(
            "No valid dataset names specified in --datasets option. "
            "Provide a comma-separated list, e.g. --datasets=biodiversity,vw."
        )

    return requested


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "use_discovered_datasets: dynamically parametrize with discovered "
        "datasets, respecting --include-local and --datasets CLI options"
    )


@pytest.fixture(scope="session")
def include_local(request):
    """Fixture that returns True if --include-local flag was passed."""
    return request.config.getoption("--include-local")


@pytest.fixture(scope="session")
def all_datasets(include_local):
    """Fixture that returns all discovered datasets based on --include-local flag."""
    return discover_datasets(include_local=include_local)


@pytest.fixture(scope="session")
def regression_datasets(include_local):
    """Fixture that returns datasets valid for regression testing."""
    return list_regression_datasets(include_local=include_local)


def pytest_generate_tests(metafunc):
    """
    Dynamically parametrize tests marked with @pytest.mark.use_discovered_datasets.

    These tests must declare a 'dataset_name' parameter. They will be parametrized
    with all regression datasets, filtered by --include-local and --datasets.

    Uses xdist_group markers for efficient parallel execution with pytest-xdist.
    """
    if not list(metafunc.definition.iter_markers("use_discovered_datasets")):
        return

    include_local = metafunc.config.getoption("--include-local")
    requested = _get_requested_datasets(metafunc.config)

    datasets = list_regression_datasets(include_local=include_local)
    if requested:
        datasets = [d for d in datasets if d in requested]

    metafunc.parametrize("dataset_name", make_dataset_params(datasets))


# Provide summary of discovered datasets at start of test run
def pytest_report_header(config):
    """Add dataset discovery info to pytest header."""
    include_local = config.getoption("--include-local")
    requested = _get_requested_datasets(config)
    datasets = discover_datasets(include_local=include_local)
    regression_valid = [
        name for name, info in datasets.items()
        if info.is_valid
    ]

    local_count = sum(1 for info in datasets.values() if info.is_local)
    committed_count = len(datasets) - local_count

    lines = [
        f"Datasets discovered: {len(datasets)} total ({committed_count} committed, {local_count} local)",
        f"Valid for regression: {len(regression_valid)} ({', '.join(sorted(regression_valid)) or 'none'})",
    ]

    if requested:
        lines.append(f"Filtered to: {', '.join(sorted(requested))}")

    if not include_local:
        lines.append("Use --include-local to include datasets from real_data/.local/")

    return lines
