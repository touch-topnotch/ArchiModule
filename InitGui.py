# filepath: /Users/dmitry057/Projects/DeepL/archi-ve/FreeCAD/src/Mod/Archi/InitGui.py
import FreeCAD
import FreeCADGui


class Archi_Sketch3d_Command:
    def GetResources(self):
        return {
            "MenuText": "3D Sketch",
            "ToolTip": "Create or edit a 3D sketch",
            "Pixmap": "Archi_Sketch3d"
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Archi_Sketch3d activated\n")

    def IsActive(self):
        return True


class Archi_FloorPlaner_Command:
    def GetResources(self):
        return {
            "MenuText": "Floor Planer",
            "ToolTip": "Create or modify floor plans",
            "Pixmap": "Archi_FloorPlaner"
        }

    def Activated(self):
        FreeCAD.Console.PrintMessage("Archi_FloorPlaner activated\n")

    def IsActive(self):
        return True


class ArchiWorkbench(Workbench):
    """Archi workbench."""

    def __init__(self):
        self.__class__.Icon = FreeCAD.getResourceDir() + "Mod/Archi/Resources/icons/Archi_Workbench.svg"
        self.__class__.MenuText = "Archi"
        self.__class__.ToolTip = "Archi workbench"

    def Initialize(self):
        import Archi
        import ArchiGui

        # import ProjectContext
        import Authentication
        import MasterAPI

        masterAPI = MasterAPI.MasterAPI("http://89.169.36.93:8001")
        # FreeCADGui.addCommand("Archi_ProjectContext", ProjectContext.Archi_ProjectContext_Command())
        # FreeCADGui.addCommand("Archi_Sketch3d", Archi_Sketch3d_Command())
        FreeCADGui.addCommand("Archi_Authentication", Authentication.Archi_Authentication_Command(masterAPI=masterAPI))

    def Activated(self):
        # Add commands to menu
        self.appendMenu("Archi", ["Archi_ProjectContext", "Archi_Authentication"])
        # Add commands to toolbars
        self.appendToolbar("Archi Tools", ["Archi_ProjectContext"])
        # Run authentication after everything is initialized

        FreeCADGui.runCommand("Archi_Authentication")

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::Workbench"

Gui.addWorkbench(ArchiWorkbench())
