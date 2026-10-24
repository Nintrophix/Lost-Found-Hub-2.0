def test_health_reports_database_and_foreign_keys(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "foreign_keys": "on"}
