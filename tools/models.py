from typing import Optional, Any, Generic, TypeVar
from pydantic import BaseModel, field_validator, computed_field, Field
from typing import List, Tuple
from datetime import datetime, timedelta

T = TypeVar('T', bound=Any)

class Token(BaseModel):
    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }
    }
    
    access_token: str
    token_type: str = "Bearer"
    delta_minutes: int = 15
    last_update: datetime = Field(default_factory=datetime.now)

    @computed_field
    def is_expired(self) -> bool:
        return datetime.now() - self.last_update > timedelta(minutes=self.delta_minutes)

    @field_validator('access_token')
    @classmethod
    def validate_token(cls, v: str) -> str:
        if not v:
            raise ValueError("Token cannot be empty")
        return v

    def update_token(self, new_token: str) -> None:
        if new_token != self.access_token:
            self.access_token = new_token
            self.last_update = datetime.now()

    def get_token(self) -> str:
        if self.is_expired:
            raise Exception("Token expired")
        return self.access_token

    def model_dump(self, **kwargs) -> dict:
        return {
            "access_token": self.access_token,
            "token_type": self.token_type
        }

class AsyncResponse(BaseModel, Generic[T]):
    model_config = { 'arbitrary_types_allowed': True }
    result: Optional[T] = None
    error: Optional[Exception] = None

    def has_result(self) -> bool:
        """Check if result is not None."""
        return self.result is not None

    def has_error(self) -> bool:
        """Check if error is not None."""
        return self.error is not None

class AuthInput(BaseModel):
    username: str
    password: str

class Gen2dInput(BaseModel):
    image_base64: str
    prompt: str
    negative_prompt: Optional[str] = None
    control_strength: float = 0.7
    seed: Optional[int] = None

class Gen2dResult(BaseModel):
    image_base64: str

class Gen3dInput(BaseModel):
    # Multi-image mode support
    front: Optional[str] = None
    back: Optional[str] = None
    left: Optional[str] = None
    right: Optional[str] = None
    other: Optional[str] = None
    
    # Legacy single image mode (kept for backward compatibility)
    image_base64: Optional[str] = None
    
    # 3D generation parameters (from test_hitem3d.py)
    # resolution может быть строкой качества ("low", "medium", "high", "ultra") или числом ("512", "1024", "1536", "1536 Pro")
    resolution: Optional[str] = "low"  # Model resolution: "low" (512), "medium" (1024), "high" (1536), "ultra" (1536 Pro)
    # face может быть строкой качества ("low", "high", "ultra") или числом (100000, 1000000, 2000000)
    face: Optional[str] = "low"  # Number of polygons: "low" (100000), "high" (1000000), "ultra" (2000000)

class Gen3dId(BaseModel):
    # New API uses task_id, but keep obj_id for backward compatibility
    task_id: Optional[str] = None
    obj_id: Optional[str] = None
    
    def get_id(self) -> str:
        """Returns task_id if available, otherwise obj_id"""
        return self.task_id or self.obj_id or ""

class Gen3dModel(BaseModel):
    glb_url: Optional[str] = ""
    fbx_url: Optional[str] = ""
    usdz_url: Optional[str] = ""
    obj_url: Optional[str] = ""

class Gen3dTexture(BaseModel):
    base_color_url: str
    metallic_url: str
    roughness_url: str
    normal_url: str

class Gen3dResult(BaseModel):
    progress: int
    object: Optional[Gen3dModel] = None
    texture: Optional[Gen3dTexture] = None
    estimated_time: Optional[int] = None  # Estimated time in seconds (from Obj3dResult API model)

class Gen3dSaved(BaseModel):
    local: Optional[Gen3dResult] = None
    online: Optional[Gen3dResult] = None
    obj_id: Optional[str] = None

class RemoveBackgroundInput(BaseModel):
    image_base64: str
    keep_coords: List[Tuple[int, int]]
    remove_coords: List[Tuple[int, int]] = None
    
class RemoveBackgroundOutput(BaseModel):
    image_base64: str

class ClearBackgroundInput(BaseModel):
    image_base64: str