from pydantic import BaseModel, Field
from typing import Optional

class LocationOut(BaseModel):
    id: int
    name: str
    plant_code: str
    building: Optional[str] = None

class AssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    asset_tag: str = Field(..., pattern=r"^[A-Z]{2,4}-\d{4,6}$")
    category: str = Field(..., description="plc | sensor | drive | hmi | robot")
    status: str = Field(default="active", pattern=r"^(active|maintenance|retired)$")
    location_id: Optional[int] = None
    installed_date: Optional[str] = None
    next_service_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    notes: Optional[str] = None

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern=r"^(active|maintenance|retired)$")
    location_id: Optional[int] = None
    next_service_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    notes: Optional[str] = None

class AssetOut(BaseModel):
    id: int
    name: str
    asset_tag: str
    category: str
    status: str
    location_id: Optional[int] = None
    installed_date: Optional[str] = None
    next_service_date: Optional[str] = None
    notes: Optional[str] = None

class MaintenanceEventCreate(BaseModel):
    due_at: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1, max_length=500)
    completed: bool = False

class MaintenanceEventOut(BaseModel):
    id: int
    asset_id: int
    due_at: str
    task: str
    completed: bool

class BulkImportRequest(BaseModel):
    assets: list[AssetCreate]

class BulkImportResult(BaseModel):
    imported: int
