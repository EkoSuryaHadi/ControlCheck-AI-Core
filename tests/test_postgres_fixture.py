from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urlsplit

import conftest as fixtures


class _FakeAdminConnection:
    def __init__(self, databases: set[str], commands: list[str]) -> None:
        self._databases = databases
        self._commands = commands

    def __enter__(self) -> "_FakeAdminConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, query: object) -> None:
        statement = query.as_string(None)  # type: ignore[attr-defined]
        self._commands.append(statement)
        match = re.fullmatch(
            r'(?:CREATE|DROP) DATABASE "([a-z0-9_]+)"(?: WITH \(FORCE\))?',
            statement,
        )
        assert match is not None, f"unexpected admin statement: {statement}"
        database_name = match.group(1)
        if statement.startswith("CREATE"):
            self._databases.add(database_name)
        else:
            self._databases.remove(database_name)


def test_postgres_fixture_never_targets_or_drops_shared_database(monkeypatch) -> None:
    databases = {"postgres", "controlcheck"}
    commands: list[str] = []

    monkeypatch.setattr(fixtures, "_is_postgres_available", lambda: True)
    monkeypatch.setattr(
        fixtures,
        "_get_target_database_url",
        lambda: "postgresql+psycopg://controlcheck:controlcheck@localhost:54329/controlcheck",
    )
    monkeypatch.setattr(
        fixtures.psycopg,
        "connect",
        lambda *_args, **_kwargs: _FakeAdminConnection(databases, commands),
    )

    fixture_value = fixtures.postgres_url.__wrapped__()
    fixture_iterator: Iterator[str] | None = (
        fixture_value if isinstance(fixture_value, Iterator) else None
    )

    try:
        postgres_url = next(fixture_iterator) if fixture_iterator else fixture_value
        database_name = urlsplit(postgres_url).path.removeprefix("/")
        assert database_name.startswith("controlcheck_test_")
        assert database_name != "controlcheck"
    finally:
        if fixture_iterator:
            fixture_iterator.close()

    assert "controlcheck" in databases
    assert not any(name.startswith("controlcheck_test_") for name in databases)
    assert all('DATABASE "controlcheck"' not in command for command in commands)
