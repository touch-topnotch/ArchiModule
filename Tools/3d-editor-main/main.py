import sys
from PySide6.QtWidgets import (QApplication)
import FreeCADGUi
from PySide6.QtWidgets import QMainWindow
# Create second window (not the main window)
mainWindow = QMainWindow()
mainWindow.setWindowTitle("3D Model Editor")
mainWindow.setGeometry(150, 150, 600, 400)
mainWindow.show()

print("yes")