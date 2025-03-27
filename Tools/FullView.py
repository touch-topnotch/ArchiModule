import FreeCADGui
from PySide.QtCore import Qt, QObject, Signal, QEvent
from PySide.QtGui import QPixmap, QPainter, QPainterPath, QWheelEvent
from PySide.QtWidgets import QWidget, QLabel, QVBoxLayout, QScrollArea, QFileDialog, QPushButton, QHBoxLayout, QDockWidget, QTabWidget

from PySide.QtCore import QTimer, QPoint
from PySide.QtCore import Qt
from Tools.View3d import View3DWindow
from Tools import Exporting
from Tools import Models
from Tools.ImageViewer import ImageViewer
from typing import List, Dict, Callable
from pydantic import BaseModel, ConfigDict, SkipValidation

class FullViewButtonData(BaseModel):
    name:str
    action: SkipValidation[Callable] = None
    model_config = ConfigDict(arbitrary_types_allowed=True)
     
class FullViewWindowData(BaseModel):
    interactable:QWidget
    buttons:List[FullViewButtonData]
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
class FullViewWindow(QDockWidget):
    def __init__(self, parent = None):
        
        super(FullViewWindow, self).__init__(parent)
        
        self.setWindowTitle("Полный просмотр")
        self.setWidget(QWidget())
        self.layout:QVBoxLayout = QVBoxLayout(self.widget())
        
        self.buttons:List[FullViewButtonData] = []
        self.interactable:QWidget = None
        self.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.button_container = QHBoxLayout()
        self.button_widgets = []
        
        
    def show(self, data:FullViewWindowData):
        if data is None:
            return
        self.interactable = data.interactable
        self.buttons = data.buttons
        
        self.layout.addWidget(self.interactable)
        
        self.layout.addLayout(self.button_container)
        for button in self.buttons:
            button_widget = QPushButton(button.name)
            button_widget.clicked.connect(button.action)
            self.button_widgets.append(button_widget)
            self.button_container.addWidget(button_widget)
        super().show()
        self.activate_full_view_tab()

    def activate_full_view_tab(self):
        parent = self.parent()
        if isinstance(parent, QTabWidget):
            index = parent.indexOf(self)
            if index != -1:
                parent.setCurrentIndex(index)
        else:
            self.raise_()
            self.activateWindow()
            
    def close(self):
        if(self.interactable):
            self.layout.removeWidget(self.interactable)
            self.interactable.deleteLater()
            self.interactable = None
        for button_widget in self.button_widgets:
            self.button_container.removeWidget(button_widget)
            button_widget.deleteLater()
        self.button_widgets.clear()
        self.layout.removeItem(self.button_container)
 
       
    
        super().hide()
        
class FullView3DInteractable(QWidget):
    def __init__(self, view3dData:Models.Gen2dResult, parent=None):
        super(FullView3DInteractable, self).__init__(parent)
        self.viewer = View3DWindow(view3dData)
        self.container = QWidget.createWindowContainer(self.viewer)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.container)
        self.setLayout(self.layout)
        self.viewer.show()
    
    def close(self):
        self.viewer.close()
        super().close()

    def resize(self, width):
        self.viewer.resize(width, width)
        super().resize(width)
    
class FullViewImageInteractable(QWidget):
    """Интерактивный просмотр изображений с зумом, как в Google Maps"""

    def __init__(self, path:str , parent=None):
        super(FullViewImageInteractable, self).__init__(parent)
        self.setWindowTitle("Полный просмотр")
        self.viewer = ImageViewer(path)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewer)
        self.setLayout(self.layout)
        self.viewer.show()
        