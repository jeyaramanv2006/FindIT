from fastapi.testclient import TestClient
from app.main import app

def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "OK"
        assert data["version"] == "0.1.0"
        assert "model_loaded" in data
        assert "embedding_model" in data
        assert "registered_directories" in data
        assert "total_passages_indexed" in data
