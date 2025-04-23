from typing import List
import json
import os
import FreeCAD
from pydantic import BaseModel
from Tools.Models import Gen3dSaved
    

class ProjectContextModel(BaseModel):
    prompt: str
    negative_prompt: str
    slider_value: float
    sketches: List[str]
    generations2d: List[str]
    generations3d: List[Gen3dSaved]
    
recall_proj_name = "None"
def get_project_path(proj_name = FreeCAD.ActiveDocument.Name):
    project_path = f"{FreeCAD.getUserAppDataDir()}/Mod/Archi/Resources/{proj_name}"
    global recall_proj_name
    recall_proj_name = proj_name
    if not os.path.exists(f"{project_path}"):
        os.makedirs(f"{project_path}")
    return project_path
def rename_project(new_name, old_name = recall_proj_name):
    '''
    1. Create new folder with new_name
    2. Copy all files from old folder to new folder
    3. Delete old folder
    4. Update ProjectContext.json
    '''
    old_path = get_project_path(old_name)
    new_path = get_project_path(new_name)
    if(os.path.exists(new_path)):
        return new_path
    os.rename(old_path, new_path)
    with open(f"{new_path}/ProjectContext.json", "r") as f:
        data = f.read()
        if old_name in data:
            data = data.replace(old_name, new_name)
    with open(f"{new_path}/ProjectContext.json", "w") as fw:
        fw.write(data)
    return new_path
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

def save_props(props, proj_name = FreeCAD.ActiveDocument.Name):
    project_path = get_project_path(proj_name)
    with open(f"{project_path}/ProjectContext.json", "r") as f:
        project_context = json.load(f)
        for key, value in props.items():
            project_context[key] = value
    with open(f"{project_path}/ProjectContext.json", "w") as f:
        json.dump(project_context, f)

def save_arr_item(key, value, proj_name = FreeCAD.ActiveDocument.Name):
    project_path = get_project_path(proj_name)
    with open(f"{project_path}/ProjectContext.json", "r") as f:
        project_context = json.load(f)
        if(key not in project_context):
            project_context[key] = []
        if isinstance(value, BaseModel):
            value = value.model_dump()
        if(value not in project_context[key]):
            project_context[key].append(value)      
    with open(f"{project_path}/ProjectContext.json", "w") as f:
        json.dump(project_context, f)
    
def remove_arr_item(key, value, proj_name = FreeCAD.ActiveDocument.Name):
    project_path = get_project_path(proj_name)
    with open(f"{project_path}/ProjectContext.json", "r") as f:
        project_context = json.load(f)
        if(key not in project_context):
            return
        if isinstance(value, BaseModel):
            value = value.model_dump()
        #value - path to file. Delete it
        if(os.path.exists(value)):
            os.remove(value)
            
        if(value in project_context[key]):
            project_context[key].remove(value)  
                
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
