path = "/Users/dmitry057/Projects/DeepL/archi-ve/FreeCAD/src/Gui/Icons/"
mask = "freecadsplash"

logos = [
    "/Users/dmitry057/Projects/DeepL/archi-ve/FreeCAD/src/Mod/Archi/EngineHandlers/freecadsplash0_2x.png"
    ]
logos_1x = [
    "/Users/dmitry057/Projects/DeepL/archi-ve/FreeCAD/src/Mod/Archi/EngineHandlers/freecadsplash0_1x.png"
]
import os
import random
from PIL import Image
import io

def refresh_logos():
    # find all files in the path
    files = os.listdir(path)
    # filter files with the mask
    files = list(filter(lambda x: mask in x and "hidden" not in x, files))
    # get files from files, which ends on "2x.png"
    files_2x = list(filter(lambda x: "2x.png" in x, files))
    files_1x = list(filter(lambda x: x not in files_2x, files))
    if(len(files_2x) > len(files_1x)):
        print("There are more 2x files than 1x files.")
        exit()
    for i in range(len(files_2x)):
        '''
        1. rename file to <filename>_hidden.png
        2. select randomly one path from logos, read it and save it to the path files_2x[i]
        '''
        # name_2x_hidden = files_2x[i].replace('.png', '_hidden.png')
        # name_1x_hidden = files_1x[i].replace('.png', '_hidden.png')
        # if not os.path.exists(f"{path}{name_2x_hidden}"):
        #     os.rename(f"{path}{files_2x[i]}", f"{path}{name_2x_hidden}")
        # if not os.path.exists(f"{path}{name_1x_hidden}"):
        #     os.rename(f"{path}{files_1x[i]}", f"{path}{name_1x_hidden}")
        random_index = random.randint(0, len(logos) - 1)
      
        with open(logos[random_index], "rb") as logo_bytes_2x:
            logo_bytes_2x = logo_bytes_2x.read()
            
        with open(f"{path}{files_2x[i]}", "wb") as f:
            f.write(logo_bytes_2x)
        
        with open(logos_1x[random_index], "rb") as logo_bytes_1x:
            logo_bytes_1x = logo_bytes_1x.read()
            
        with open(f"{path}{files_1x[i]}", "wb") as f:
            f.write(logo_bytes_1x)
        
        
        print(f"{files_2x[i]} is replaced with {logos[random_index]}")
        print(f"{files_1x[i]} is replaced with {logos_1x[random_index]}")
        
def remove_copies():
    files = os.listdir(path)
    mask="_hidden.png"
    files = list(filter(lambda x: mask in x, files))
    for file in files:
        if file.endswith("hidden_hidden.png"):
            os.remove(f"{path}{file.split('_hidden_hidden.png')[0]}_hidden.png")
            print(f"{path}{file.split('_hidden.png')[0]}_hidden.png is removed")
            os.rename(f"{path}{file}", f"{path}{file.split('_hidden_hidden.png')[0]}_hidden.png")
refresh_logos()
    