import json
import logging
import io
from uuid import uuid4

from controlcheck.logging import (
    StructuredJsonFormatter,
    clear_log_context,
    configure_logging,
    get_logger,
    set_log_context,
)


def test_structured_json_formatter_outputs_valid_json():
    formatter = StructuredJsonFormatter()
    logger = logging.getLogger("test_logger")
    record = logger.makeRecord(
        name="test_logger",
        level=logging.INFO,
        fn="test.py",
        lno=10,
        msg="Testing message %s",
        args=("foo",),
        exc_info=None,
    )
    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert data["message"] == "Testing message foo"
    assert "timestamp" in data


def test_structured_json_formatter_includes_context_vars():
    req_id = str(uuid4())
    org_id = str(uuid4())
    proj_id = str(uuid4())
    run_id = str(uuid4())

    set_log_context(
        request_id=req_id,
        organization_id=org_id,
        project_id=proj_id,
        analysis_run_id=run_id,
    )

    try:
        formatter = StructuredJsonFormatter()
        logger = logging.getLogger("test_context_logger")
        record = logger.makeRecord(
            name="test_context_logger",
            level=logging.WARNING,
            fn="test.py",
            lno=20,
            msg="Context test",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["request_id"] == req_id
        assert data["organization_id"] == org_id
        assert data["project_id"] == proj_id
        assert data["analysis_run_id"] == run_id
    finally:
        clear_log_context()


def test_get_logger_namespaces_under_controlcheck():
    logger = get_logger("engine")
    assert logger.name == "controlcheck.engine"

    logger_already_prefixed = get_logger("controlcheck.api")
    assert logger_already_prefixed.name == "controlcheck.api"


def test_configure_logging_sets_level_and_formatter():
    stream = io.StringIO()
    configure_logging(level="DEBUG", log_format="json")

    logger = get_logger("test_config")
    logger.debug("Debug message")

    # Reset logging
    configure_logging(level="INFO", log_format="text")
