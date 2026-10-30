import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok", "build": 0}


def test_list_items() -> None:
    response = client.get("/items", params={"offset": 10, "limit": 5})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [11, 12, 13, 14, 15]


@pytest.mark.parametrize("item_id", range(1, 101))
def test_get_item(item_id: int) -> None:
    response = client.get(f"/items/{item_id}")
    assert response.status_code == 200
    assert response.json()["id"] == item_id


def test_missing_item() -> None:
    response = client.get("/items/1000")
    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_create_item() -> None:
    response = client.post(
        "/items",
        json={"name": "New item", "price": 12.5, "tags": ["new"]},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "New item"
