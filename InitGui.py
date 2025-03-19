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
        import Tools.Authentication as Authentication
        import Tools.MasterAPI as MasterAPI
        import Tools.ProjectContext as ProjectContext
        
        if(FreeCAD.ActiveDocument == None):
            return False

        masterAPI = MasterAPI.MasterAPI("http://89.169.36.93:8001")
        auth_session_command = Authentication.Archi_Authentication_Command(masterAPI=masterAPI)
        auth_session_command.Activated()
        session = auth_session_command.session
        project_context_command = ProjectContext.Archi_ProjectContext_Command(session)
        project_context_command.Activated()
        
        # FreeCADGui.addCommand("Archi_ProjectContext", ProjectContext.Archi_ProjectContext_Command())
        # FreeCADGui.addCommand("Archi_Sketch3d", Archi_Sketch3d_Command())
        return True
        

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


class DocumentObserver:
    
    def __init__(self, workbench):
        self.workbench = workbench
        self.singleton = False


    def slotCreatedObject(self, Obj):
        print("On created object called")

    def slotDeletedObject(self, Obj):
        print("On deleted object called")

    def slotChangedObject(self, Obj, Prop):
        if FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.Name and not self.singleton:
            print(f"Project selected: {FreeCAD.ActiveDocument.Name}")
            self.workbench.Initialize()
            self.singleton = True

    def slotRelabelObject(self, Obj):
        print("On relabel object called")

    def slotActivatedObject(self, Obj):
        print("On activated object called")

    def slotEnterEditObject(self, Obj):
        print("On enter edit object called")

    def slotResetEditObject(self, Obj):
        print("On reset edit object called")

    def slotUndoDocument(self, Doc):
        print("On undo document called")

    def slotRedoDocument(self, Doc):
        print("On redo document called")

    def slotDeleteDocument(self, Doc):
        print("On delete document called")

archi_workbench = ArchiWorkbench()
FreeCADGui.addWorkbench(archi_workbench)

observer = DocumentObserver(archi_workbench)
FreeCADGui.addDocumentObserver(observer)
print("Archi workbench initialized")
