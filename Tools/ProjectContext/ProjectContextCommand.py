from typing import Dict, Any

import FreeCADGui
from PySide.QtWidgets import QDockWidget
from PySide.QtCore import Qt

from .ProjectContextWindow import ProjectContextWindow


class ProjectContextCommand:
    """
    Command to create and manage the Project Context window in FreeCAD.
    This command handles creating the dock widget, removing existing
    instances, and placing it in the interface.
    """
    
    def __init__(self, authenticatedSession):
        """
        Initialize the command with an authenticated session.
        
        Args:
            authenticatedSession: The authenticated session for API access
        """
        self.authenticatedSession = authenticatedSession

    def GetResources(self) -> Dict[str, Any]:
        """
        Define the command resources for the FreeCAD interface.
        
        Returns:
            Dictionary with menu text, tooltip and icon information
        """
        return {
            "MenuText": "Project Context",
            "ToolTip": "Initialize or manage project context",
            "Pixmap": "Archi_ProjectContext"
        }

    def Activated(self):
        """
        Called when the command is activated in the FreeCAD interface.
        Removes any existing Project Context windows and creates a new one.
        """
        mw = FreeCADGui.getMainWindow()
        self._close_existing_windows(mw)
        
        # Create and show new project context window
        projectContextWindow = ProjectContextWindow(self.authenticatedSession, mw)
        mw.addDockWidget(Qt.RightDockWidgetArea, projectContextWindow)
        projectContextWindow.show()

    def _close_existing_windows(self, main_window):
        """
        Close any existing Project Context related windows.
        
        Args:
            main_window: The FreeCAD main window
        """
        dock_widget_titles = ["Project Context", "Best Sketch", "Full View", "Полный просмотр"]
        
        for widget in main_window.findChildren(QDockWidget):
            if widget.windowTitle() in dock_widget_titles:
                main_window.removeDockWidget(widget)
                widget.close()

    def IsActive(self) -> bool:
        """
        Determine if the command is active and can be used.
        
        Returns:
            True if the command can be used, False otherwise
        """
        return True
    