from click.testing import CliRunner

from app import create_app
from app.models import ServiceType


def test_seed_db_creates_schema_and_inserts_service_types():
    app = create_app("testing")
    runner = CliRunner()

    with app.app_context():
        ServiceType.query.delete()

    result = runner.invoke(app.cli, ["seed-db"])

    assert result.exit_code == 0, result.output
    assert "Service types seeded" in result.output

    with app.app_context():
        assert ServiceType.query.count() == 5
