from alembic.config import Config


def test_percent_encoded_database_url_is_safe_for_alembic_config():
    database_url = (
        "postgresql+psycopg://alembic_user:Vriddhi%401405"
        "@localhost/alembic_test"
    )
    config = Config()

    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    assert config.get_main_option("sqlalchemy.url") == database_url
