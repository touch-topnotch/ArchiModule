import FreeCADGui
from PySide2.QtCore import Qt, QObject, Signal, QEvent
from PySide2.QtGui import QPixmap, QPainter, QPainterPath, QWheelEvent
from PySide2.QtWidgets import QWidget, QLabel, QVBoxLayout, QScrollArea, QFileDialog, QPushButton, QHBoxLayout, QDockWidget
from PySide2.QtSvg import QSvgWidget
from PySide2.QtCore import QTimer, QPoint
from PySide2.QtCore import Qt
from Tools.View3d import View3DWindow, View3DData
from Tools import Exporting
from typing import List, Dict
from pydantic import BaseModel, ConfigDict

class FullViewButtonData(BaseModel):
    name:str
    action: callable = None
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
        self.close()
        print([button.name for button in data.buttons])
        self.interactable = data.interactable
        self.buttons = data.buttons
        
        self.layout.addWidget(self.interactable)
        
        dock_width = self.width()
        dock_height = self.height()
        # self.interactable.setFixedSize(dock_width, dock_height*0.8)
        self.layout.addLayout(self.button_container)
        for button in self.buttons:
            button_widget = QPushButton(button.name)
            button_widget.clicked.connect(button.action)
            self.button_widgets.append(button_widget)
            self.button_container.addWidget(button_widget)
        super().show()
        
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
    def __init__(self, view3dData:View3DData, parent=None):
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

        # ✅ QLabel для отображения изображения
        self.label = QLabel(self)
    
        self.label.setAlignment(Qt.AlignCenter)
        # ✅ Лейаут
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)
        main_window = FreeCADGui.getMainWindow()
        width = int(main_window.width()*0.3) 
        height = int(main_window.height()*0.7)
        self.setMaximumWidth(width)
        self.setMaximumHeight(height)
        # ✅ Переменные для зума и перемещения
        self.scale_factor = 1
        self.pixmap = QPixmap(path)
        pixmap_width = self.pixmap.size().width()
        pixmap_height = self.pixmap.size().height()
        if(pixmap_width >= pixmap_height):
            self.pixmap = self.pixmap.scaled(width, width*pixmap_height/pixmap_width, Qt.KeepAspectRatio)
        else:
            self.pixmap = self.pixmap.scaled(height*pixmap_width/pixmap_height, height, Qt.KeepAspectRatio)
        self.label.setPixmap(self.pixmap)
        # self.label.setMaximumSize(self.pixmap.size())
        
        self.offset = QPoint(0, 0)  # Смещение
        self.last_mouse_pos = QPoint()  # Последняя позиция мыши

        # ✅ Устанавливаем фильтр событий
        self.label.installEventFilter(self)
        self.label.setMouseTracking(True)  # Отслеживание мыши
    
    def eventFilter(self, source, event):
        """Фильтр событий для обработки колеса мыши и перемещения"""
        if event.type() == QEvent.Wheel:
            self.handle_zoom(event)
            return True

        elif event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self.last_mouse_pos = event.pos()
                return True

        elif event.type() == QEvent.MouseMove:
            if event.buttons() & Qt.LeftButton:
                self.handle_pan(event)
                return True

        return super().eventFilter(source, event)

    def handle_zoom(self, event: QWheelEvent):
        """Масштабирование изображения с центрированием в точке курсора"""
        zoom_factor = 1.01 if event.angleDelta().y() > 0 else 0.99
        if(abs(event.angleDelta().y()) < 10):
            zoom_factor = 1.001 if event.angleDelta().y() > 0 else 0.999
        new_scale = self.scale_factor * zoom_factor

        # Ограничение масштаба (0.1x - 5x)
        if 0.1 <= new_scale <= 10:
            cursor_pos = event.pos()
            
            # ✅ Коррекция смещения (центрирование в точке курсора)
            delta_x = (cursor_pos.x() - self.offset.x()) * (zoom_factor - 1)
            delta_y = (cursor_pos.y() - self.offset.y()) * (zoom_factor - 1)
            self.offset -= QPoint(delta_x, delta_y)

            self.scale_factor = new_scale
            self.update_image()

    def handle_pan(self, event):
        """Перемещение изображения"""
        delta = event.pos() - self.last_mouse_pos
        self.offset += delta
        self.last_mouse_pos = event.pos()
        self.update_image()

    def update_image(self):
        """Обновление изображения с учетом масштаба и позиции"""
        scaled_pixmap = self.pixmap.scaled(
            self.pixmap.size() * self.scale_factor,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.label.setPixmap(scaled_pixmap)
        self.label.move(self.offset)

