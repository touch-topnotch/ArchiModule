# filepath: /Users/dmitry057/Projects/DeepL/archi-ve/FreeCAD/src/Mod/Archi/InitGui.py
import os                       # standard library
os.environ["QT_LOGGING_RULES"] = "qt.pointer.dispatch=false"

import FreeCAD
import FreeCADGui
import tools.log as log

class Archi_Sketch3d_Command:
    def GetResources(self):
        return {
            "MenuText": "3D Sketch",
            "ToolTip": "Create or edit a 3D sketch",
            "Pixmap": "Archi_Sketch3d"
        }

    def Activated(self):
        log.info("Archi_Sketch3d activated\n")

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
        log.info("Archi_FloorPlaner activated\n")

    def IsActive(self):
        return True

class ArchiWorkbench(Workbench):
    """Archi workbench."""

    def __init__(self):
        super().__init__()
        self.__class__.Icon = FreeCAD.getResourceDir() + "Mod/ArchiModule/Resources/icons/Archi_Workbench.svg"
        self.__class__.MenuText = "Archi"
        self.__class__.ToolTip = "Archi workbench"
        
        self.master_api_instance = None
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
            
            if not self.master_api_instance:
                self.master_api_instance = master_api.MasterAPI("http://89.169.36.93:8001")
            
                self.auth_session_command = authentication.Archi_Authentication_Command(
                    masterAPI=self.master_api_instance,
                )
                
                FreeCADGui.addCommand("Archi_Authentication", self.auth_session_command)
                FreeCADGui.runCommand("Archi_Authentication")
                self.session = self.auth_session_command.session

        except Exception as e:
            log.error(f"Error during workbench initialization: {str(e)}\n")

    def initialize_project_context(self):
        """Initialize project context after successful authentication."""
        try:
            import tools.project_context as project_context
            import tools.log as log
            
            if not self.session:
                log.error("Cannot initialize project context: no active session")
                return
                
            project_context_command = project_context.ProjectContextCommand(self.session)
            FreeCADGui.addCommand("Archi_ProjectContext", project_context_command)
            project_context_command.Activated()
            
            # # Add commands to menu
            # self.appendContextMenu("Archi", ["Archi_ProjectContext", "Archi_Authentication"])
            # # Add commands to toolbars
            # self.appendToolbar("Archi tools", ["Archi_ProjectContext", "Archi_Authentication"])
                
        except Exception as e:
            log.error(f"Error initializing project context: {str(e)}\n")

    def Activated(self):
        self.initialize_project_context()
        
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
        
    def slotCloseTransaction(self, abort):
        log.info("On slotCloseTransaction called")




# Initialize workbench
try:
    archi_workbench = ArchiWorkbench()
    FreeCADGui.addWorkbench(archi_workbench)
    archi_workbench.Initialize()
    observer = DocumentObserver(archi_workbench)
    FreeCADGui.addDocumentObserver(observer)
    log.info("Archi workbench initialized successfully\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"Error creating workbench: {str(e)}\n")
