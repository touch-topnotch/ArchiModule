# filepath: /Users/dmitry057/Projects/DeepL/archi-ve/FreeCAD/src/Mod/Archi/InitGui.py

import FreeCAD
import FreeCADGui
import tools.log as log
from FreeCADGui import Workbench

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
        
        self.__class__.Icon = FreeCAD.getResourceDir() + "Mod/ArchiModule/Resources/icons/Archi_Workbench.svg"
        self.__class__.MenuText = "Archi"
        self.__class__.ToolTip = "Archi workbench"
        
        self.auth_session_command = None
        self.project_context_command = None
        self.session = None

    def Initialize(self):
        try:
            import Archi
            import ArchiGui
            import tools.log as log
            import tools.master_api as master_api
            import tools.authentication as authentication
            
            # Change the main window title
            main_window = FreeCADGui.getMainWindow()
            if main_window:
                main_window.setWindowTitle("ARCHI 1.1.0 dev")
            
            self.master_api_instance = master_api.MasterAPI("http://89.169.36.93:8001")
            
            self.auth_session_command = authentication.Archi_Authentication_Command(masterAPI=self.master_api_instance)
            FreeCADGui.addCommand("Archi_Authentication", self.auth_session_command)
            FreeCADGui.runCommand("Archi_Authentication")
            

        except Exception as e:
            log.error(f"Error during workbench initialization: {str(e)}\n")


    def Activated(self):
        try:
                
            import tools.project_context as project_context
            import tools.log as log
            
            
            main_window = FreeCADGui.getMainWindow()
            
            if self.auth_session_command is None:
                if not self.Initialize():
                    log.error("Failed to initialize workbench\n")
                    return
                
            if not self.auth_session_command.session or not self.auth_session_command.session.is_authenticated():
                log.warning("User is not authenticated\n")
                FreeCADGui.runCommand("Archi_Authentication")
                return
            
            session = self.auth_session_command.session
            project_context_command = project_context.ProjectContextCommand(session)
            FreeCADGui.addCommand("Archi_ProjectContext", project_context_command)
            project_context_command.Activated()
            
            
            # Add commands to menu
            self.appendContextMenu("Archi", ["Archi_ProjectContext", "Archi_Authentication"])
            # Add commands to toolbars
            self.appendToolbar("Archi tools", ["Archi_ProjectContext", "Archi_Authentication"])
                
        except Exception as e:
            log.error(f"Error during workbench activation: {str(e)}\n")

    def Deactivated(self):
        pass
    
    def GetClassName(self):
        return "Gui::PythonWorkbench"

class DocumentObserver:
    
    def __init__(self, workbench):
        self.workbench = workbench
        self.singleton = False
        
    def slotRelabelDocument(self, Doc):
        import tools.exporting as exporting
        # rename folder by tools.exporting.rename_project()
        if FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.Name:
            exporting.rename_project(FreeCAD.ActiveDocument.Name)
            print("On slotRelabelDocument called")

    def slotActivateDocument(self, Doc):
        if FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.Name:
            print(f"Project selected: {FreeCAD.ActiveDocument.Name}")
            self.workbench.Activated()
            self.singleton = True
    
    def slotCloseDocument(self, Doc):
        log.info("On slotCloseDocument called")


    # def slotBeforeChangeDocument(self, Obj, Prop):
    #     print("On slotBeforeChangeDocument called")

    # def slotChangedDocument(self, Obj, Prop):
    #     print("On slotChangedDocument called")

    # # def slotCreatedObject(self, Obj):
    # #     print("On slotCreatedObject called")

    # def slotDeletedObject(self, Obj):
    #     print("On slotDeletedObject called")

    # # def slotBeforeChangeObject(self, Obj, Prop):
    # #     print("On slotBeforeChangeObject called")

    # # def slotChangedObject(self, Obj, Prop):
    # #     print("On slotChangedObject called")

    # def slotUndoDocument(self, Doc):
    #     print("On slotUndoDocument called")

    # def slotRedoDocument(self, Doc):
    #     print("On slotRedoDocument called")

    # def slotRecomputedObject(self, Obj):
    #     print("On slotRecomputedObject called")

    # def slotBeforeRecomputeDocument(self, Doc):
    #     print("On slotBeforeRecomputeDocument called")

    # def slotRecomputedDocument(self, Doc):
    #     print("On slotRecomputedDocument called")

    # def slotOpenTransaction(self, Doc, transactionName):
    #     print("On slotOpenTransaction called")

    # def slotCommitTransaction(self, Doc):
    #     print("On slotCommitTransaction called")

    # def slotAbortTransaction(self, Doc):
    #     print("On slotAbortTransaction called")

    # def slotUndo(self):
    #     print("On slotUndo called")

    # def slotRedo(self):
    #     print("On slotRedo called")

    # def slotBeforeCloseTransaction(self, abort):
    #     print("On slotBeforeCloseTransaction called")

    def slotCloseTransaction(self, abort):
        log.info("On slotCloseTransaction called")

    # def slotAppendDynamicProperty(self, Prop):
    #     print("On slotAppendDynamicProperty called")

    # def slotRemoveDynamicProperty(self, Prop):
    #     print("On slotRemoveDynamicProperty called")

    # def slotChangePropertyEditor(self, Doc, Prop):
    #     print("On slotChangePropertyEditor called")

    # def slotStartSaveDocument(self, Doc, filename):
    #     print("On slotStartSaveDocument called")

    # def slotFinishSaveDocument(self, Doc, filename):
    #     print("On slotFinishSaveDocument called")

    # def slotBeforeAddingDynamicExtension(self, extensionContainer, extension):
    #     print("On slotBeforeAddingDynamicExtension called")

    # def slotAddedDynamicExtension(self, extensionContainer, extension):
    #     print("On slotAddedDynamicExtension called")
    # def slotChangedObject(self, Obj, Prop):
        # if FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.Name and not self.singleton:
        #     print(f"Project selected: {FreeCAD.ActiveDocument.Name}")
        #     self.workbench.Initialize()
        #     self.singleton = True
        # print("On changed object called")



# Initialize workbench
try:
    archi_workbench = ArchiWorkbench()
    FreeCADGui.addWorkbench(archi_workbench)
    archi_workbench.Initialize()
    observer = DocumentObserver(archi_workbench)
    FreeCADGui.addDocumentObserver(observer)
    FreeCAD.Console.PrintMessage("Archi workbench initialized successfully\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"Error creating workbench: {str(e)}\n")
