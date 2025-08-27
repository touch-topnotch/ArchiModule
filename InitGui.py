# filepath: /Users/dmitry057/Projects/DeepL/archi-ve/FreeCAD/src/Mod/Archi/InitGui.py
import os                       # standard library
os.environ["QT_LOGGING_RULES"] = "qt.pointer.dispatch=false"

import FreeCAD
import FreeCADGui
from FreeCADGui import Workbench
from tools import log


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

            import tools.master_api as master_api
            from tools.authentication.authentication import Archi_Authentication_Command
            from tools import log
            
            log.info("🔐 Starting Archi workbench initialization with TouchTopNotch authentication...")
            
            # Change the main window title
            main_window = FreeCADGui.getMainWindow()
            if main_window:
                main_window.setWindowTitle("ARCHI 1.1.0 dev")
                log.info("✅ Main window title updated to: ARCHI 1.1.0 dev")
            
            if not self.master_api_instance:
                log.info("🌐 Initializing MasterAPI with TouchTopNotch server...")
                self.master_api_instance = master_api.MasterAPI("http://89.169.36.93:8001")
                log.info("✅ MasterAPI initialized successfully")
            
                log.info("🔑 Creating TouchTopNotch authentication command...")
                self.auth_session_command = Archi_Authentication_Command(
                    masterAPI=self.master_api_instance,
                )
                log.info("✅ Authentication command created successfully")
                
                log.info("📝 Adding authentication command to FreeCAD GUI...")
                FreeCADGui.addCommand("Archi_Authentication", self.auth_session_command)
                log.info("✅ Authentication command added to GUI")
                
                log.info("🚀 Running authentication command to initialize session...")
                FreeCADGui.runCommand("Archi_Authentication")
                log.info("✅ Authentication command executed")
                
                self.session = self.auth_session_command.session
                if self.session:
                    log.info("✅ Authentication session created successfully")
                    log.info(f"🔍 Session type: {type(self.session).__name__}")
                    log.info(f"🔍 Session has auth_service: {hasattr(self.session, 'auth_service')}")
                    if hasattr(self.session, 'auth_service'):
                        log.info(f"🔍 Auth service type: {type(self.session.auth_service).__name__}")
                        log.info(f"🔍 Auth service API URL: {getattr(self.session.auth_service, 'API_BASE_URL', 'N/A')}")
                        log.info(f"🔍 Auth service WebSocket URL: {getattr(self.session.auth_service, 'WEBSOCKET_URL', 'N/A')}")
                else:
                    log.error("❌ Failed to create authentication session")

        except Exception as e:
            from tools import log
            log.error(f"❌ Error during workbench initialization: {str(e)}")
            import traceback
            log.error(f"📋 Traceback: {traceback.format_exc()}")

    def initialize_project_context(self):
        """Initialize project context after successful authentication."""
        try:
            import tools.project_context as project_context
            from tools import log
            
            log.info("🏗️ Initializing project context...")
            
            if not self.session:
                log.error("❌ Cannot initialize project context: no active session")
                return
                
            log.info("✅ Session found, creating project context command...")
            project_context_command = project_context.ProjectContextCommand(self.session)
            FreeCADGui.addCommand("Archi_ProjectContext", project_context_command)
            log.info("✅ Project context command added to GUI")
            
            log.info("🚀 Activating project context...")
            project_context_command.Activated()
            log.info("✅ Project context activated successfully")
            
            # # Add commands to menu
            # self.appendContextMenu("Archi", ["Archi_ProjectContext", "Archi_Authentication"])
            # # Add commands to toolbars
            # self.appendToolbar("Archi tools", ["Archi_ProjectContext", "Archi_Authentication"])
                
        except Exception as e:
            from tools import log
            log.error(f"❌ Error initializing project context: {str(e)}")
            import traceback
            log.error(f"📋 Traceback: {traceback.format_exc()}")

    def Activated(self):
        from tools import log
        log.info("🎯 Archi workbench activated")
        self.initialize_project_context()
        
    def Deactivated(self):
        from tools import log
        log.info("🔒 Archi workbench deactivated")
        pass
    
    def GetClassName(self):
        return "Gui::PythonWorkbench"

class DocumentObserver:
    
    def __init__(self, workbench):
        self.workbench = workbench
        self.singleton = False
        
    def slotRelabelDocument(self, Doc):
        import tools.exporting as exporting
        import tools.log as log
        # rename folder by tools.exporting.rename_project()
        if FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.Name:
            exporting.rename_project(FreeCAD.ActiveDocument.Name)
            log.info("📝 Document relabeled, project renamed")

    def slotActivateDocument(self, Doc):
        import tools.log as log
        if FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.Name:
            log.info(f"📄 Project selected: {FreeCAD.ActiveDocument.Name}")
            self.workbench.Activated()
            self.singleton = True
    
    def slotCloseDocument(self, Doc):
        import tools.log as log
        log.info("📄 Document closed")
        
    def slotCloseTransaction(self, abort):
        import tools.log as log
        log.info("💾 Transaction closed")




# Initialize workbench
try:
    log.info("🚀 Starting Archi workbench initialization...")
    archi_workbench = ArchiWorkbench()
    log.info("✅ ArchiWorkbench instance created")
    
    FreeCADGui.addWorkbench(archi_workbench)
    log.info("✅ Workbench added to FreeCAD GUI")
    
    archi_workbench.Initialize()
    log.info("✅ Workbench initialization completed")
    
    observer = DocumentObserver(archi_workbench)
    FreeCADGui.addDocumentObserver(observer)
    log.info("✅ Document observer added")
    
    log.info("🎉 Archi workbench initialized successfully with TouchTopNotch authentication!")
except Exception as e:
    log.error(f"❌ Error creating workbench: {str(e)}")
    import traceback
    log.error(f"📋 Traceback: {traceback.format_exc()}")
