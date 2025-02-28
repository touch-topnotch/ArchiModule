from typing import List
import json
import os
import FreeCAD
from pydantic import BaseModel


class ProjectContextModel(BaseModel):
    prompt: str
    negative_prompt: str
    slider_value: float
    sketches: List[str]
    generations2d: List[str]
    generations3d: List[str]

def get_project_path(proj_name = FreeCAD.ActiveDocument.Name):
    project_path = f"{FreeCAD.getResourceDir()}/Mod/Archi/Resources/{proj_name}"
    if not os.path.exists(f"{project_path}"):
        os.makedirs(f"{project_path}")
    return project_path

def save_source(folder, path, proj_name = FreeCAD.ActiveDocument.Name):
    project_path = get_project_path(proj_name)
    if(not os.path.exists(f"{project_path}/{folder}")):
        os.makedirs(f"{project_path}/{folder}")
    to = f"{project_path}/{folder}/{path.split('/')[-1]}"

    save_arr_item(folder, to, proj_name)
    if(path == to):
        return to

    with open(path, "rb") as fr_f:
        fr_f  = fr_f.read()

    with open(to, "wb") as to_f:
        to_f.write(fr_f)
        
    return to

def save_prop(key, value, proj_name = FreeCAD.ActiveDocument.Name):
    project_path = get_project_path(proj_name)
    with open(f"{project_path}/ProjectContext.json", "r") as f:
        project_context = json.load(f)
        project_context[key] = value
    with open(f"{project_path}/ProjectContext.json", "w") as f:
        json.dump(project_context, f)

def save_arr_item(key, value, proj_name = FreeCAD.ActiveDocument.Name,):
    project_path = get_project_path(proj_name)
    with open(f"{project_path}/ProjectContext.json", "r") as f:
        project_context = json.load(f)
        if(key not in project_context):
            project_context[key] = []
        if(value not in project_context[key]):
            project_context[key].append(value)      
    with open(f"{project_path}/ProjectContext.json", "w") as f:
        json.dump(project_context, f)

def load(project_name=FreeCAD.ActiveDocument.Name):
    project_path = get_project_path(project_name)
    if not os.path.exists(f"{project_path}/ProjectContext.json"):
        with open(f"{project_path}/ProjectContext.json", "w") as f:
            json.dump({
                "prompt": "",
                "negative_prompt": "",
                "slider_value": 0.5,
                "sketches": [],
                "generations2d": [],
                "generations3d": []
            }, f)

    with open(f"{project_path}/ProjectContext.json", "r") as f:
        context = ProjectContextModel(**json.load(f))
        return context