"""init_db must migrate an existing SQLite file that predates monitored_routes.replacement_attempts."""
from sqlalchemy import inspect, text

from app.database.connection import engine, init_db
from app.repositories.monitored_route_repository import monitored_route_repository


def _columns():
    return {c["name"] for c in inspect(engine).get_columns("monitored_routes")}


def test_init_db_adds_replacement_attempts_to_an_old_database():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE monitored_routes DROP COLUMN replacement_attempts"))
        conn.execute(text(
            "INSERT INTO monitored_routes (route_id, origin, destination, route_nodes, distance_m, "
            "estimated_time_s, created_at, last_checked_at, initial_hazard_summary, "
            "current_hazard_summary, monitor_status, transitions) VALUES "
            "('old-route', '{}', '{}', '[]', 0, 0, '2026-01-01T00:00:00', '2026-01-01T00:00:00', "
            "'{}', '{}', 'ACTIVE', '[]')"))
        conn.commit()
    assert "replacement_attempts" not in _columns()

    init_db()

    assert "replacement_attempts" in _columns()
    assert monitored_route_repository.get_by_id("old-route")["replacement_attempts"] == []
