from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]


def test_ai_insight_migration_is_the_only_alembic_head() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["20260907_0002"]