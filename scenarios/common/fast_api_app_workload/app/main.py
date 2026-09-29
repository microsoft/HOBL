from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.version import BUILD_ID


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    price: float = Field(gt=0)
    tags: list[str] = Field(default_factory=list)


class Item(ItemCreate):
    id: int


class ItemStore:
    def __init__(self) -> None:
        self._items = {
            item_id: Item(
                id=item_id,
                name=f"Item {item_id}",
                price=float(item_id) + 0.99,
                tags=["sample"],
            )
            for item_id in range(1, 101)
        }

    def list(self, offset: int, limit: int) -> list[Item]:
        return list(self._items.values())[offset : offset + limit]

    def get(self, item_id: int) -> Item:
        try:
            return self._items[item_id]
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Item not found") from error

    def create(self, item: ItemCreate) -> Item:
        created = Item(id=max(self._items) + 1, **item.model_dump())
        self._items[created.id] = created
        return created


store = ItemStore()
app = FastAPI(title="HOBL FastAPI App Workload", version=str(BUILD_ID))


def get_store() -> ItemStore:
    return store


@app.get("/health")
def health() -> dict[str, int | str]:
    return {"status": "ok", "build": BUILD_ID}


@app.get("/items", response_model=list[Item])
def list_items(
    item_store: Annotated[ItemStore, Depends(get_store)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[Item]:
    return item_store.list(offset, limit)


@app.get("/items/{item_id}", response_model=Item)
def get_item(
    item_id: int,
    item_store: Annotated[ItemStore, Depends(get_store)],
) -> Item:
    return item_store.get(item_id)


@app.post("/items", response_model=Item, status_code=status.HTTP_201_CREATED)
def create_item(
    item: ItemCreate,
    item_store: Annotated[ItemStore, Depends(get_store)],
) -> Item:
    return item_store.create(item)
