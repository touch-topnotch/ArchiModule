import FreeCADGui
from PySide.QtWidgets import QDockWidget, QFormLayout, QWidget
from PySide.QtCore import Qt
from typing import Optional
import FreeCAD # Import for PrintMessage
from tools import log
class FormWindow(QDockWidget):
    """
    Base class for dockable windows with a QFormLayout,
    automatically sized and centered relative to the FreeCAD main window.
    """
    def __init__(self, title: str = "Form Window", parent: Optional[QWidget] = None, width_ratio: float = 0.6, height_ratio: float = 0.8):
        """
        Initializes the FormWindow.

        Args:
            title: The title for the window.
            parent: The parent widget.
            width_ratio: The desired width as a fraction of the main window width.
            height_ratio: The desired height as a fraction of the main window height.
        """
        try:
            super().__init__(title, parent) # *** Just call the base QDockWidget init ***
        except Exception as e:
            FreeCAD.Console.PrintError(f"FormWindow.__init__: Error in super().__init__: {e}\n")
            raise

        self.setWindowTitle(title)
        
        self.central_widget = QWidget()
        self.formLayout = QFormLayout()
        self.central_widget.setLayout(self.formLayout)
        self.setWidget(self.central_widget)
        
        self.advisable_width = 0
        self.advisable_height = 0
        try:
            self._calculate_and_set_geometry(width_ratio, height_ratio)
        except Exception as e:
             FreeCAD.Console.PrintError(f"FormWindow.__init__: Error calling _calculate_and_set_geometry: {e}\n")
             raise

    def _calculate_and_set_geometry(self, width_ratio: float, height_ratio: float):
        """Calculates the window size and position and applies it."""
        # This method is currently not called from the simplified __init__
        try:
            main_win = FreeCADGui.getMainWindow()
            if not main_win:
                self.resize(600, 500)
                log.info("FormWindow._calculate_and_set_geometry: Resized to default 600x500")
                return

            mw_geo = main_win.geometry()
            self.advisable_width = int(mw_geo.width() * width_ratio)
            self.advisable_height = int(mw_geo.height() * height_ratio)

            new_x = int(mw_geo.x() + (mw_geo.width() - self.advisable_width) / 2)
            new_y = int(mw_geo.y() + (mw_geo.height() - self.advisable_height) / 2)
            self.setGeometry(new_x, new_y, self.advisable_width, self.advisable_height)
            
        except Exception as e:
            FreeCAD.Console.PrintError(f"FormWindow._calculate_and_set_geometry: Error: {e}\n")
            self.resize(600, 500)
            log.info("FormWindow._calculate_and_set_geometry: Resized to default 600x500 due to error")
            raise

    # Optionally, add a method to easily add rows to the form layout
    def addRow(self, label: str | QWidget, field: Optional[QWidget] = None):
        """Convenience method to add a row to the internal formLayout."""
        # Need to check if formLayout exists if we are bypassing init steps
        if not hasattr(self, 'formLayout') or not self.formLayout:
             FreeCAD.Console.PrintError("FormWindow.addRow: formLayout not initialized!")
             return

        if field is None:
            self.formLayout.addRow(label)  # type: ignore[arg-type]
        else:
            self.formLayout.addRow(label, field)  # type: ignore[arg-type] 