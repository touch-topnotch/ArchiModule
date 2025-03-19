from typing import Optional
from pydantic import BaseModel, field_validator
from typing import List, Tuple

class Token(BaseModel):
    access_token: str
    token_type: str

class Gen2dInput(BaseModel):
    image_base64: str
    prompt: str
    negative_prompt: Optional[str] = None
    control_strength: float = 0.7
    seed: Optional[int] = None

class Gen2dResult(BaseModel):
    image_base64: str

class Gen3dInput(BaseModel):
    image_base64: str

class Gen3dId(BaseModel):
    obj_id: str

class Gen3dModel(BaseModel):
    glb_url: str
    fbx_url: str
    usdz_url: str
    obj_url: str

class Gen3dTexture(BaseModel):
    base_color_url: str
    metallic_url: str
    roughness_url: str
    normal_url: str

class Gen3dResult(BaseModel):
    progress: int
    object: Optional[Gen3dModel] = None
    texture: Optional[Gen3dTexture] = None

class Gen3dSaved(BaseModel):
    local: Optional[Gen3dResult] = None
    online: Optional[Gen3dResult] = None
    obj_id: Optional[str] = None

class RemoveBackgroundInput(BaseModel):
    image_base64: str
    remove_coords: List[Tuple[int, int]]
    keep_coords: Optional[List[Tuple[int, int]]] = None
class ClearBackgroundInput(BaseModel):
    image_base64: str