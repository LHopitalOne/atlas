from fastapi import APIRouter, HTTPException

from app.store import MENUS

router = APIRouter(prefix="/menus", tags=["menus"])


@router.get("/{restaurant_id}")
def get_menu(restaurant_id: int) -> dict:
    items = MENUS.get(restaurant_id)
    if items is None:
        raise HTTPException(status_code=404, detail="restaurant not found")
    return {"restaurant_id": restaurant_id, "items": items}
