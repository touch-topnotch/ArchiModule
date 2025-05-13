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
        self.__class__.Icon = FreeCAD.getResourceDir() + "Mod/ArchiModule/Resources/icons/Archi_Workbench.svg"
        self.__class__.MenuText = "Archi"
        self.__class__.ToolTip = "Archi workbench"
        FreeCAD.Console.PrintMessage("ArchiWorkbench initialized\n")

    def Initialize(self):
        
        if(FreeCAD.ActiveDocument == None):
            return False
        
        import Archi
        import ArchiGui
        import Tools.Authentication as Authentication
        import Tools.MasterAPI as MasterAPI
        import Tools.ProjectContext as ProjectContext
        
        masterAPI               = MasterAPI.MasterAPI("http://89.169.36.93:8001")
        auth_session_command    = Authentication.Archi_Authentication_Command(masterAPI=masterAPI)
        session                 = auth_session_command.session
        project_context_command = ProjectContext.ProjectContextCommand(session)
        
        FreeCADGui.addCommand("Archi_Authentication", auth_session_command)
        FreeCADGui.addCommand("Archi_ProjectContext", project_context_command)
    
        
        auth_session_command    .Activated()
        project_context_command .Activated()
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

    # def GetClassName(self):
    #     return "Gui::Workbench"


class DocumentObserver:
    
    def __init__(self, workbench):
        self.workbench = workbench


    # def slotCreatedDocument(self, Doc):
    #     print("On slotCreatedDocument called")

    # def slotDeletedDocument(self, Doc):
    #     print("On slotDeletedDocument called")

    def slotRelabelDocument(self, Doc):
        import Tools.Exporting as Exporting
        # rename folder by Tools.Exporting.RenameFolder()
        if(FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.Name):
            Exporting.rename_project(FreeCAD.ActiveDocument.Name)
            print("On slotRelabelDocument called")

    def slotActivateDocument(self, Doc):
        if FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.Name:
            print(f"Project selected: {FreeCAD.ActiveDocument.Name}")
            self.workbench.Initialize()
            self.singleton = True


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

    # def slotCloseTransaction(self, abort):
    #     print("On slotCloseTransaction called")

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



archi_workbench = ArchiWorkbench()
FreeCADGui.addWorkbench(archi_workbench)

observer = DocumentObserver(archi_workbench)
FreeCADGui.addDocumentObserver(observer)
print("Archi workbench initialized")
