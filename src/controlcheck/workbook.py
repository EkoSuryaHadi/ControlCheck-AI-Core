from __future__ import annotations

from typing import Any
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException

from .errors import InvalidWorkbookError


_PARSER_ERRORS = (BadZipFile, InvalidFileException, KeyError, ParseError)


def _is_optional_xml_parser_error(exc: Exception) -> bool:
    exception_type = type(exc)
    return (
        exception_type.__name__ == "XMLSyntaxError"
        and exception_type.__module__.startswith("lxml.")
    )


def open_xlsx(source: Any, **kwargs: Any):
    """Open an XLSX package while normalizing parser failures at the boundary."""
    try:
        return openpyxl.load_workbook(source, **kwargs)
    except _PARSER_ERRORS as exc:
        raise InvalidWorkbookError(InvalidWorkbookError.safe_message) from exc
    except Exception as exc:
        if _is_optional_xml_parser_error(exc):
            raise InvalidWorkbookError(InvalidWorkbookError.safe_message) from exc
        raise
