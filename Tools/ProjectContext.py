import base64
import datetime
import os
import time
from typing import List, Optional, Tuple

import FreeCAD
import FreeCADGui

from PySide2.QtGui import QPixmap, QImage, QIcon, QPainter, QPen, QBrush, QColor, QVector3D
from PySide2.QtCore import Qt, QTimer
from PySide2.QtWidgets import (QWidget, QLabel, QVBoxLayout, 
                               QSlider, QLineEdit, QPushButton, QRadioButton,
                               QGroupBox, QFormLayout, QScrollArea, QDockWidget, QHBoxLayout, QVBoxLayout,
                                QMessageBox,QGraphicsOpacityEffect, QGraphicsBlurEffect, QFileDialog, QFormLayout, QStackedLayout, QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect)
from PySide2.QtSvg import QSvgWidget
from Tools.View3d import View3DStyle
from Tools.Authentication import AuthenticatedSession
from Tools.MasterAPI import MasterAPI
from Tools import Models
from Tools.GalleryUtils import (ImageCell,View3DCell, AnimatedCell, LoadingCell,
                                GalleryStyle,GalleryWidget, select_images, GalleryCell)
from Tools.FullView import (FullViewWindow, FullViewImageInteractable,FullView3DInteractable,
                                FullViewButtonData,  FullViewWindowData)
from Tools import Exporting
from PySide2.QtWidgets import QLabel, QVBoxLayout, QStackedLayout
from PySide2.QtWidgets import QLabel
from PySide2.QtCore import Signal, QPoint, Qt, QSize
from PySide2.QtGui import QPixmap, QMouseEvent
import numpy as np
import Archi
import ArchiGui
from enum import Enum, auto
from PySide2.QtCore import QByteArray, QBuffer
import requests
import asyncio

class MyRadioButton(QRadioButton):
            def __init__(self, parent=None):
                super(MyRadioButton, self).__init__(parent)
                self.toggled.connect(self.on_toggled)
               
                self.activate_blur()
                # Hide the radio button indicator circle and prevent focus/selection outlines
                self.setStyleSheet("""
                    QRadioButton::indicator {
                        width: 0;
                        height: 0;
                        margin: 0;
                    }
                    QRadioButton {
                        outline: none;
                        border: none;
                    }
                    QRadioButton:focus {
                        outline: none;
                        border: none;
                    }
                """)
                
            def activate_blur(self):
                self.blur_effect = QGraphicsBlurEffect()
                self.blur_effect.setBlurRadius(5)
                self.setGraphicsEffect(self.blur_effect)
                self.setWindowOpacity(0.5)
                
            def on_toggled(self, checked):
                if checked:
                    self.setGraphicsEffect(None)
                else:
                    self.activate_blur()
            def toggle_sim(self):
                self.setChecked(not self.isChecked())
                self.on_toggled(self.isChecked())
                    
def blend_images(blurred_image: QImage, given_image: QImage) -> QImage:
    """Replace transparent pixels (alpha=0) of given_image with darkened blurred_image (50% RGB, full alpha)."""

    # Convert QImages to NumPy arrays
    given_array = image_to_array(given_image).copy()  # ✅ Ensure writable
    blurred_array = image_to_array(blurred_image)

    # Darken RGB of blurred_image by 50%
    blurred_array[:, :, :3] = (blurred_array[:, :, :3] * 0.5).astype(np.uint8)

    # Keep Alpha Channel of blurred_image fully opaque
    blurred_array[:, :, 3] = 255  # ✅ Set alpha to fully opaque

    # Extract alpha mask of given_image
    alpha_channel = given_array[:, :, 3]  # Alpha channel (transparency)

    # Apply mask: If alpha == 0 in given_image, replace it with modified blurred_image
    mask = alpha_channel == 0
    given_array[mask] = blurred_array[mask]

    # Convert back to QImage
    return array_to_qimage(given_array)

def image_to_array(image: QImage) -> np.ndarray:
    """Convert QImage to NumPy array (RGBA format)."""
    image = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = image.width(), image.height()
    ptr = image.bits()
    return np.array(np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 4)), copy=True)  # ✅ Ensure writable

def array_to_qimage(array: np.ndarray) -> QImage:
    """Convert NumPy array (RGBA) to QImage."""
    height, width, channels = array.shape
    bytes_per_line = width * 4
    return QImage(array.data, width, height, bytes_per_line, QImage.Format_RGBA8888)

def apply_blur_effect(pixmap: QPixmap, radius: int = 80) -> QImage:
    """Applies a blur effect to a pixmap and returns the resulting QImage."""
    # Create a QGraphicsScene
    scene = QGraphicsScene()
    
    # Create a QGraphicsPixmapItem and apply the blur effect
    item = QGraphicsPixmapItem(pixmap)
    blur_effect = QGraphicsBlurEffect()
    blur_effect.setBlurRadius(radius)
    item.setGraphicsEffect(blur_effect)
    
    # Add item to the scene
    scene.addItem(item)
    
    # Create an output pixmap with the same size
    blurred_pixmap = QPixmap(pixmap.size())
    blurred_pixmap.fill(Qt.transparent)  # Ensure transparency is handled
    
    # Render scene to the new pixmap
    painter = QPainter(blurred_pixmap)
    scene.render(painter)
    painter.end()
    
    return blurred_pixmap.toImage()

class PrepareWindow(QDockWidget):
    def __init__(self, title=None, parent=None):
        super(PrepareWindow, self).__init__(parent)
        self.formLayout = QFormLayout()
        if(title):
            self.setWindowTitle(title)
        # add form layout to dock widget
        self.setWidget(QWidget())
        self.widget().setLayout(self.formLayout)
        main_win = FreeCADGui.getMainWindow()
        mw_geo = main_win.geometry()
        self.advisable_width = int(mw_geo.width() * 0.6)
        self.advisable_height = int(mw_geo.height() * 0.8)
        self.gallery_style = GalleryStyle(
            number_of_cols=3,
            min_dock_height=int(self.advisable_height*0.3),
            max_dock_height=self.advisable_height,
            width_of_cell=int(self.advisable_width /3.2),
            gap=10)
        new_x = int(mw_geo.x() + (mw_geo.width() - self.advisable_width) / 2)
        new_y = int(mw_geo.y() + (mw_geo.height() - self.advisable_height) / 2)
        self.setGeometry(new_x, new_y, self.advisable_width, self.advisable_height)

class PrepareFor3dGen(PrepareWindow):
    
    class ToolType(Enum):
        PEN = 0
        ERASER = 1
        NONE = 2
        
    selected_tool:ToolType = ToolType.NONE
    def __init__(self, generations:GalleryWidget, auth_session:AuthenticatedSession, onObjIdReceived, parent=None):
        super(PrepareFor3dGen, self).__init__("Prepare for 3D generation", parent)
        self.onObjIdReceived = onObjIdReceived
        self.selected_render = None
        self.sketches = generations
        self.model = Exporting.load()
        self.selectSketchView()
        self.pen_points  = []
        self.erased_points = []
        self.paths_stack = []
        self.auth_session = auth_session

    def selectSketchView(self):
        title = QLabel("Пожалуйста, выберите лучший рендер")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        subtitle = QLabel("По большей части от него будет произведена генерация 3d моделей")
        subtitle.setStyleSheet("font-size: 12pt;")
        title.setAlignment(Qt.AlignCenter)
        subtitle.setAlignment(Qt.AlignCenter)
        self.formLayout.addRow(title)
        self.formLayout.addRow(subtitle)
        self.gallery = GalleryWidget(self.gallery_style)
        self.gallery.add_cells([cell.copy() for cell in self.sketches.cells])
        for cell in self.gallery.cells:
            cell.action.connect(lambda cell: self.onChoiseBest(cell.index))
        self.formLayout.addRow(self.gallery)
        prompt_label = QLabel("Контекст проекта")
        self.formLayout.addRow(prompt_label)
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setAlignment(Qt.AlignTop)
        self.prompt_edit.setText(self.model.prompt)
        self.formLayout.addRow(self.prompt_edit)
        self.formLayout.setSpacing(10)
        approve_button = QPushButton("Подтвердить")
        approve_button.clicked.connect(self.approve_render)
        self.formLayout.addRow(approve_button)

    def onChoiseBest(self, id):
        self.selected_render = self.gallery.cells[id].image_path
        self.gallery.cells[id].label.setStyleSheet("border: 3px solid rgba(0, 160, 200, 0.9); border-radius: 15px;")
        for i in range(len(self.gallery.cells)):
            if i != id:
                effect = QGraphicsOpacityEffect(self.gallery.cells[i].label)
                effect.setOpacity(0.8)  # Set opacity to 50%
                blur_effect = QGraphicsBlurEffect(self.gallery.cells[i].label)
                blur_effect.setBlurRadius(5)
                # Apply blur effect on the image
                self.gallery.cells[i].label.setGraphicsEffect(blur_effect)
                # Also apply opacity by setting the widget's window opacity
                self.gallery.cells[i].label.setWindowOpacity(0.5)
                self.gallery.cells[i].label.setStyleSheet("border: 0px;")
            else:
                # remove blurcellst
                self.gallery.cells[i].label.setGraphicsEffect(None)
                self.gallery.cells[i].label.setWindowOpacity(1)
                
    def removeBackground(self, image_path):
        # Clear existing form layout
        for i in reversed(range(self.formLayout.rowCount())):
            self.formLayout.removeRow(i)
        class ClickableLabel(QLabel):
            clicked = Signal(QPoint)
            def mousePressEvent(self, event: QMouseEvent):
                if event.button() == Qt.LeftButton:
                    self.clicked.emit(event.pos())
                super().mousePressEvent(event)

        title = QLabel("Нужно удалить все лишнее, чтобы модель сгенерировалась максимально качественно!")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        subtitle = QLabel("Карандаш - для восстановления деталей, Ластик - для удаления лишних элементов")
        subtitle.setStyleSheet("font-size: 12pt;")
        title.setAlignment(Qt.AlignCenter)
        subtitle.setAlignment(Qt.AlignCenter)
        self.formLayout.addRow(title)
        self.formLayout.addRow(subtitle)
       
        btn_container = QHBoxLayout()
        btn_container.setAlignment(Qt.AlignRight)
        pen_button = MyRadioButton()
        pen_button.setIcon(QIcon(":/icons/Archi_Pencil"))
        pen_button.setIconSize(QSize(70, 30))  # Increase icon size by 5x
        pen_button.toggled.connect(lambda checked: setattr(self, 'selected_tool', self.ToolType.PEN) if checked else None)
        btn_container.addWidget(pen_button)

        easier_button = MyRadioButton()
        easier_button.setIcon(QIcon(":/icons/Archi_Easier"))
        easier_button.setIconSize(QSize(70, 30))  # Increase icon size by 5x
        easier_button.toggled.connect(lambda checked: setattr(self, 'selected_tool', self.ToolType.ERASER) if checked else None)
        easier_button.toggle_sim()
        btn_container.addWidget(easier_button)

        self.formLayout.addRow(btn_container)

        self.image = ClickableLabel()
        self.paths_stack.append(image_path)
        pixmap = QPixmap(image_path)
        height = self.advisable_height * 0.9
        width = pixmap.width() * height / pixmap.height()
        self.original_width = pixmap.width()
        self.original_height = pixmap.height()
        self.x_stratch =self.original_width / width
        self.y_stratch = self.original_height / height
        self.original = pixmap.scaled(width, height, Qt.KeepAspectRatio)
         # Create blurred pixmap from paths_stack[0]
        
        self.blurred_image = apply_blur_effect(self.original.copy(), 10)
        
        self.pixmap = self.original.copy()
        self.image.setPixmap(self.pixmap)
        self.image.setAlignment(Qt.AlignCenter)
        self.image.mousePressEvent = lambda event: self.onMousePress(event)
        self.image.mouseMoveEvent = lambda event: self.onMousePress(event)
        # self.image.mouseReleaseEvent = lambda event: self.onMouseRelease(event)
        self.formLayout.addRow(self.image)
        self.option_buttons = QHBoxLayout()
        self.formLayout.addRow(self.option_buttons)
        self.rem_back_button = QPushButton("Удалить фон")
        self.rem_back_button.clicked.connect(self.remove_background)
        self.option_buttons.addWidget(self.rem_back_button)
        self.undo_button = QPushButton("Назад")
        self.undo_button.clicked.connect(self.undo_remove_background)
        self.option_buttons.addWidget(self.undo_button)
        self.undo_button.hide()
        self.approve_button = QPushButton("Подтвердить")
        self.approve_button.clicked.connect(self.approve_model)
        self.formLayout.addRow(self.approve_button)
        self.last_pos = None
        
    def setPixmap(self, pixmap:QPixmap):
        pixmap = pixmap.scaled(self.original.width(), self.original.height(), Qt.KeepAspectRatio)
        if(pixmap.isNull()):
            raise Exception("Image is not valid")
        given_image = pixmap.toImage()
        result_image = blend_images(self.blurred_image, given_image)
        self.pixmap = QPixmap.fromImage(result_image)
        self.image.setPixmap(self.pixmap)
    
    def clickDistance(self, p1, p2):
        if(p1 == None):
            return 99999
        return ((p1.x() - p2.x())**2 + (p1.y() - p2.y())**2)**0.5
    
    def onMousePress(self, pos):
        # distance between last_pos and pos > delta, return
        delta = 90
        
        if self.clickDistance(self.last_pos, pos) < delta:
            return
        
        self.last_pos = QPoint(pos.x(), pos.y())
        ps = self.image.pixmap().size()
        ws = self.image.size()
        x =((ps.width() - ws.width())/2 + pos.x())*self.x_stratch
        y = pos.y()*self.y_stratch
        if(x < 0 or x > self.original_width or y < 0 or y > self.original_height):
            return
        if(self.selected_tool == self.ToolType.NONE):
            QMessageBox.warning(self, "Не выбран инструмент", "Пожалуйста, выберите инструмент для работы с изображением")
            return
        if(self.selected_tool == self.ToolType.PEN):
            self.pixmap = self.pixmap.copy()
            painter = QPainter(self.pixmap)
            # Use default composition mode (SourceOver) instead of Clear
            painter.setPen(QPen(Qt.cyan, 30, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setOpacity(0.5)
            painter.drawPoint(pos.x(), pos.y())
            self.image.setPixmap(self.pixmap)
            self.pen_points.append((int(x), int(y)))

        if(self.selected_tool == self.ToolType.ERASER):
            self.pixmap = self.pixmap.copy()
            painter = QPainter(self.pixmap)
            # Use default composition mode (SourceOver) instead of Clear
            painter.setPen(QPen(Qt.red, 30, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setOpacity(0.5)
            painter.drawPoint(pos.x(), pos.y())
            self.image.setPixmap(self.pixmap)
            self.erased_points.append((int(x), int(y)))

    def approve_render(self):
        '''
        Check if the user has selected a sketch
        Check if the user set prompt
        '''
        if self.selected_render is None:
            QMessageBox.warning(self, "Не выбран скетч", "Пожалуйста, выберите скетч для рендера")
            return
        
        self.removeBackground(self.selected_render)
        return

    def remove_background(self):
        last_image = self.paths_stack[-1]
        with open(last_image, "rb") as f:
            image_bytes = base64.b64encode(f.read())
                 
        rb_input = Models.RemoveBackgroundInput(
            image_base64=image_bytes,
            remove_coords=self.erased_points,
            keep_coords=self.pen_points
        )

        self.auth_session.auto_login()
        if(not self.auth_session.token):
            self.auth_session.show_login()
            return
        token = self.auth_session.token
        self.messWait = QMessageBox(QMessageBox.Information, "Удаление фона", "Пожалуйста, подождите, идет удаление фона")
        self.messWait.setStandardButtons(QMessageBox.NoButton)
        self.messWait.setWindowModality(Qt.ApplicationModal)
        self.messWait.show()
        self.auth_session.masterAPI.run_async_task(self.auth_session.masterAPI.remove_background, self.on_background_removed, token=token, removeBackgroundInput=rb_input)
        
    def undo_remove_background(self):
        if(len(self.paths_stack) == 1):
            return
        self.paths_stack.pop()
        self.setPixmap(QPixmap(self.paths_stack[-1]))
    
    def on_background_removed(self, result: Optional[str], error: Optional[Exception]):

        if error:
            self.messWait.accept()
            # QMessageBox.warning(self, "Ошибка", "Ошибка при удалении фона: " + str(error))
            s = str(error)
            if(len(s) > 800):
                s = s[:400] + "..." + s[-400:]
            print(str(s))
            return
        if not result:
            self.messWait.accept()
            print(str("no result"))
            return
   
        token = self.auth_session.token
        image_base64 = result.image_base64
        if(not os.path.exists(f"{Exporting.get_project_path()}/background_removed")):
            os.makedirs(f"{Exporting.get_project_path()}/background_removed")
        path = f"{Exporting.get_project_path()}/background_removed/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_removed.png"
        
        with open(path, "wb") as f:
           f.write(base64.b64decode(image_base64))
           
        self.paths_stack.append(path)
        self.setPixmap(QPixmap(path))
  
        rb_input = Models.ClearBackgroundInput(
            image_base64=image_base64)
       
        self.auth_session.masterAPI.run_async_task(self.auth_session.masterAPI.clear_background, self.on_background_cleared, token=token, clearBackgroundInput=rb_input)
        
    def on_background_cleared(self, result: Optional[str], error: Optional[Exception]):

        if error:
            print(error)
            self.messWait.accept()
            QMessageBox.warning(self, "Ошибка", "Ошибка при удалении фона: " + str(error))
            return
        if not result:
            self.messWait.accept()
            QMessageBox.warning(self, "Ошибка", "Ошибка при удалении фона: " + str(error))
            return
        
        image_base64 = result.image_base64
        if(not os.path.exists(f"{Exporting.get_project_path()}/background_removed")):
            os.makedirs(f"{Exporting.get_project_path()}/background_removed")
        path = f"{Exporting.get_project_path()}/background_removed/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_cleared.png"
       
        with open(path, "wb") as f:
            f.write(base64.b64decode(image_base64.encode('utf-8')))
       
        self.paths_stack.append(path)
        self.setPixmap(QPixmap(path))
        self.messWait.accept()
        if(len(self.paths_stack) > 1):
            self.undo_button.show()
        else:
            self.undo_button.hide()

    def approve_model(self):
        if(len(self.paths_stack) < 1):
            QMessageBox.error(self, "Ошибка", "Не выбрано изображение, повторите процесс")
            self.close()
            return
        if not("cleared" or "removed" in self.paths_stack[-1]):
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, удалите фон перед подтверждением, чтобы модель была качественной")
            return

        Exporting.save_arr_item("cleaned_image", self.paths_stack[-1])
        
        with open(self.paths_stack[-1], "rb") as f:
            image_bytes = base64.b64encode(f.read()).decode()
        self.messWait = QMessageBox(QMessageBox.Information, "Генерация 3d модели", "Пожалуйста, подождите, идет генерация 3d модели")
        self.messWait.setStandardButtons(QMessageBox.NoButton)
        self.messWait.setWindowModality(Qt.ApplicationModal)
        self.messWait.show()
        self.auth_session.masterAPI.run_async_task(self.auth_session.masterAPI.generate_3d, self.on_generated_3d, token=self.auth_session.token, gen3dInput=Models.Gen3dInput(image_base64=image_bytes))

    def on_generated_3d(self, result: Optional[str], error: Optional[Exception]):
        if error:
            self.messWait.accept()
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации 3d модели: " + str(error))
            self.onObjIdReceived(None, error)
            return
        if not result:
            self.ibself.messWait.accept()
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации 3d модели: No result")
            self.onObjIdReceived(None, "No result")
            return
        self.messWait.accept()
        QMessageBox.information(self, "Успешно", "3d модель успешно сгенерирована")
        
        self.onObjIdReceived(result, None)
        self.close()

class PrepareFor2dGen(QDockWidget):
    def __init__(self, sketches:GalleryWidget, onApprove, parent=None):
        super(PrepareFor2dGen, self).__init__(parent)
        self.onApprove = onApprove
        self.selected_sketch = None
        self.sketches = sketches
        self.formLayout = QFormLayout()
        self.model = Exporting.load()
        self.setWindowTitle("Best Sketch")
        # add form layout to dock widget
        self.setWidget(QWidget())
        self.widget().setLayout(self.formLayout)

        self.title = QLabel("Пожалуйста, выберите лучший скетч")
        self.title.setStyleSheet("font-size: 14pt; font-weight: bold;")

        self.subtitle = QLabel("По большей части от него будет произведена генерация рендеров")
        self.subtitle.setStyleSheet("font-size: 12pt;")
        self.title.setAlignment(Qt.AlignCenter)
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.formLayout.addRow(self.title)
        self.formLayout.addRow(self.subtitle)
        main_win = FreeCADGui.getMainWindow()
        mw_geo = main_win.geometry()
        new_width = int(mw_geo.width() * 0.6)
        new_height = int(mw_geo.height() * 0.8)
        style = GalleryStyle(number_of_cols=3, min_dock_height=int(new_height*0.3), max_dock_height=new_height, width_of_cell=int(new_width/3.2), gap=10)
        self.gallery = GalleryWidget(style)
        self.gallery.add_cells([cell.copy() for cell in self.sketches.cells])
        for cell in self.gallery.cells:
            cell.action.connect(lambda cell: self.selectBest(cell.index))
        self.formLayout.addRow(self.gallery)
        self.realism_slider = QSlider(Qt.Horizontal)
        self.realism_slider.setRange(0, 100)
        self.realism_slider.setValue(self.model.slider_value * 100)
        self.formLayout.setSpacing(10)
        self.formLayout.addRow("Сходство ", self.realism_slider)
        self.formLayout.setSpacing(10)
        self.prompt_label = QLabel("Контекст проекта")
        self.formLayout.addRow(self.prompt_label)
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setAlignment(Qt.AlignTop)
        self.prompt_edit.setText(self.model.prompt)
        self.formLayout.addRow(self.prompt_edit)
        self.formLayout.setSpacing(10)
        self.n_prompt_label = QLabel("Что вы не хотите видеть в рендере")
        self.formLayout.addRow(self.n_prompt_label)
        self.n_prompt_edit = QLineEdit()
        self.n_prompt_edit.setMinimumHeight(80)
        self.n_prompt_edit.setAlignment(Qt.AlignTop)
        self.n_prompt_edit.setText(self.model.negative_prompt)
        self.formLayout.addRow(self.n_prompt_edit)


        self.approve_button = QPushButton("Подтвердить")
        self.approve_button.clicked.connect(self.approve)
        self.formLayout.addRow(self.approve_button)
        # Center the dock widget at 40% of main window's dimensions

        new_x = int(mw_geo.x() + (mw_geo.width() - new_width) / 2)
        new_y = int(mw_geo.y() + (mw_geo.height() - new_height) / 2)
        self.setGeometry(new_x, new_y, new_width, new_height)

    def selectBest(self, id):
        self.selected_sketch = self.gallery.cells[id].image_path
        self.gallery.cells[id].label.setStyleSheet("border: 3px solid rgba(0, 160, 200, 0.9); border-radius: 15px;")
        for i in range(len(self.gallery.cells)):
            if i != id:
                effect = QGraphicsOpacityEffect(self.gallery.cells[i].label)
                effect.setOpacity(0.8)  # Set opacity to 50%
                blur_effect = QGraphicsBlurEffect(self.gallery.cells[i].label)
                blur_effect.setBlurRadius(50)
                # Apply blur effect on the image
                self.gallery.cells[i].label.setGraphicsEffect(blur_effect)
                # Also apply opacity by setting the widget's window opacity
                self.gallery.cells[i].label.setWindowOpacity(0.5)
                self.gallery.cells[i].label.setStyleSheet("border: 0px;")
            else:
                # remove blurcellst
                self.gallery.cells[i].label.setGraphicsEffect(None)
                self.gallery.cells[i].label.setWindowOpacity(1)

    def approve(self):
        '''
        Check if the user has selected a sketch
        Check if the user set prompt
        '''
        if self.selected_sketch is None:
            QMessageBox.warning(self, "Не выбран скетч", "Пожалуйста, выберите скетч для рендера")
            return
        if self.prompt_edit.text().strip() == "":
            QMessageBox.warning(self, "Нет контекста", "Опишите это здание. Добавьте информацию об окружении, ландшафте, истории, контексте здания")
            return
        # check, that text doesn't include any non-utf-8 characters
        try:
            converted_prompt = self.prompt_edit.text().strip().encode('utf-8')
            
            converted_neg_prompt = self.n_prompt_edit.text().strip().encode('utf-8')
        except UnicodeEncodeError:
            # find non-utf-8 characters
            symbols = [ char for char in self.prompt_edit.text().strip() if ord(char) > 127]
            QMessageBox.warning(self, "Неккоректная запись", "Некорректные запись: " + str(symbols))
            return
        # Further processing can be added here
        QMessageBox.information(self, "Готово", "Скоро рендеры будут готовы) Можете приступать к разработке проекта")
        sketch_path = self.selected_sketch
        with open(sketch_path, "rb") as f:
            image_bytes = base64.b64encode(f.read())
        self.onApprove(
            Models.Gen2dInput(
                image_base64=image_bytes,
                prompt=converted_prompt,
                control_strength=self.realism_slider.value()/100,
                negative_prompt=converted_neg_prompt,
                seed=int(time.time())%10000
            ))
        self.close()
class ProjectBehaviour:

    class Status(Enum):
        NOT_STARTED = auto()
        RUNNING = auto()
        INTERRUPTED = auto()
        COMPLETED = auto()

    status: Status = None
    def __init__(self, on_complete):
        self.on_complete = on_complete
        self.status = self.Status.NOT_STARTED
    def stop(self):
        pass
    def complete(self):
        self.on_complete(status=self.Status.COMPLETED)
    def interrupt(self):
        self.on_complete(status=self.Status.INTERRUPTED)

class DownloadModelBehaviour(ProjectBehaviour):
    obj_id: Models.Gen3dId = None
    auth_session:AuthenticatedSession = None
    view_3d_data: Models.Gen3dSaved = None
    gallery: GalleryWidget = None
    index: int = None
    is_loading = True
    update_rate = 2
    
    def __init__(self, on_complete, gallery: GalleryWidget, obj_id: Models.Gen3dId, view_3d_style:View3DStyle, auth_session:AuthenticatedSession):
        super().__init__(on_complete)
        self.gallery = gallery
        self.obj_id = obj_id
        self.auth_session = auth_session
        self.view_3d_style = view_3d_style

        loading_cell = LoadingCell()
        loading_cell.update_progress(0)
        self.index = self.gallery.add_cell(loading_cell)
        self.is_loading = True
        self.auth_session.masterAPI.run_async_task(self.__intervaled_responce, self.on_files_download)
        
    async def __intervaled_responce(self):
        while self.is_loading:
            await self.__get_response()
            await asyncio.sleep(self.update_rate)
        
    async def __get_response(self):
        token = self.auth_session.get_token()
        if not token:
            return

        try:
            result = await self.auth_session.masterAPI.get_3d_obj(token=token, obj_id=self.obj_id)
        except Exception as e:
            print(f"Failed to get 3D object: {e}")
            self.is_loading = False
            return

        if not result:
            self.is_loading = False
            print("no result")
            return

        if result.object:
            
            # result should be exactly Gen3dResult type
           
            try:
                self.view_3d_data = Models.Gen3dSaved(local=None, online=result.model_dump(), obj_id=self.obj_id.obj_id)
            except Exception as e:
                print(f"Failed to parse 3D object: {e}")
                self.is_loading = False
                return
            
            await self.__download_files(
                root_folder=f"{Exporting.get_project_path()}/generations3d",
                name=self.obj_id.obj_id
            )

            self.is_loading = False
        else:
            print("is loading")
            print(result)

    async def __download_files(self, root_folder, name):
        try:
            gen_3d_result = self.view_3d_data.online
            obj_url = gen_3d_result.object.obj_url
            fbx_url = gen_3d_result.object.fbx_url
            usdz_url = gen_3d_result.object.usdz_url
            glb_url = gen_3d_result.object.glb_url

            base_color_url = gen_3d_result.texture.base_color_url
            metallic_url = gen_3d_result.texture.metallic_url
            roughness_url = gen_3d_result.texture.roughness_url
            normal_url = gen_3d_result.texture.normal_url
            folder = f"{root_folder}/{name}"
            if not os.path.exists(folder):
                os.makedirs(folder)
            from_to_source = [
                (obj_url, f"{folder}/{name}.obj"),
                (fbx_url, f"{folder}/{name}.fbx"),
                (usdz_url, f"{folder}/{name}.usdz"),
                (glb_url, f"{folder}/{name}.glb"),
                (base_color_url, f"{folder}/{name}_base_color.png"),
                (metallic_url, f"{folder}/{name}_metallic.png"),
                (roughness_url, f"{folder}/{name}_roughness.png"),
                (normal_url, f"{folder}/{name}_normal.png")
            ]

            self.view_3d_data = Models.Gen3dSaved(
                local=Models.Gen3dResult(
                    progress=100,
                    object=Models.Gen3dModel(
                        obj_url=from_to_source[0][1],
                        fbx_url=from_to_source[1][1],
                        usdz_url=from_to_source[2][1],
                        glb_url=from_to_source[3][1]
                    ),
                    texture=Models.Gen3dTexture(
                        base_color_url=from_to_source[4][1],
                        metallic_url=from_to_source[5][1],
                        roughness_url=from_to_source[6][1],
                        normal_url=from_to_source[7][1]
                    )
                ),
                online=gen_3d_result,
                obj_id=self.obj_id.obj_id
            )
            response = await self.auth_session.masterAPI.download_files(from_to_source)
            Exporting.save_arr_item("generations3d", self.view_3d_data.model_dump())
        
        except Exception as e:
            print(f"Failed to download files: {e}")
        
    def on_files_download(self, result, error):
        if error:
            # QMessageBox.warning(self, "Ошибка", "Ошибка при загрузке файлов: " + str(error))
            print(f"Failed to download files: {error}")
            # self.interrupt()
            return
        print(self.view_3d_data)
        self.gallery.change_cell(self.index, View3DCell(self.view_3d_data, self.view_3d_style))
     
class Generate2dBehaviour(ProjectBehaviour):
    def __init__(self,
                 authSession: AuthenticatedSession,
                 masterApi: MasterAPI,
                 sketches: GalleryWidget,
                 gen2d: GalleryWidget,
                 full_view: FullViewWindow,
                 prompt_edit:QLineEdit):
        super().__init__(lambda status: None)
        self.status = self.Status.RUNNING
        self.authSession = authSession
        self.masterApi = masterApi
        self.sketches = sketches
        self.gen2d = gen2d
        self.prompt_edit = prompt_edit
        self.full_view = full_view
        self.selectBestSketch = None
        self.gen_stack = []
        
    
        self.selectBestSketch = PrepareFor2dGen(self.sketches, self.generate_render)
        FreeCADGui.getMainWindow().addDockWidget(Qt.LeftDockWidgetArea, self.selectBestSketch)
        self.selectBestSketch.setFloating(True)
        self.selectBestSketch.show()
        
    
    def generate_render(self, gen2dInput:Models.Gen2dInput):
        # 1) Save the input
        Exporting.save_prop("prompt", gen2dInput.prompt)
        Exporting.save_prop("negative_prompt", gen2dInput.negative_prompt)
        Exporting.save_prop("slider_value", gen2dInput.control_strength)
        
        self.prompt_edit.setText(gen2dInput.prompt)

        # 2) Check authentication
        if not self.authSession or not self.authSession.token:
            complete = self.authSession.auto_login()
            if not complete:
                self.authSession.show_login()
        # 3) Show loading image in self.generations gallery
        cell = AnimatedCell(FreeCAD.getResourceDir() + "Mod/Archi/Resources/anims/Archi_Preloader.svg")
        cell.setBackground(self.selectBestSketch.selected_sketch)
        gen_2d_id = self.gen2d.add_cell(cell)
        self.gen_stack.append(gen_2d_id)
        token = self.authSession.token.access_token
        self.masterApi.run_async_task(self.masterApi.generate_2d, self.on_image_generated, token=token, gen2dInput = gen2dInput)
    
    def on_image_generated(self, result: Optional[Models.Gen2dResult], error: Optional[Exception]):
        
        if error:
            # show error message in box
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации изображения: " + str(error))
            # remove loading image from gallery
            self.gen2d.remove(self.gen_stack.pop())
            return
        if not result:
                # show error message in box
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации изображения: " + str(error))
            # remove loading image from gallery
            self.gen2d.remove(self.gen_stack.pop())
            return
        if not result.image_base64:
            QMessageBox.warning(self, "Ошибка", "Скорее всего вы ввели недопустимые символы в поле контекста")
            # remove loading image from gallery
            self.gen2d.remove(self.gen_stack.pop())
            return
        
        path = f"{Exporting.get_project_path()}/generations2d/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
        if(not os.path.exists(f"{Exporting.get_project_path()}/generations2d")):
            os.makedirs(f"{Exporting.get_project_path()}/generations2d")

        with open(path, "wb") as f:
            f.write(base64.b64decode(result.image_base64))

        cell = ImageCell(image_path=path)
        self.gen2d.change_cell(self.gen_stack.pop(), cell)
        cell.action.connect(lambda cell: self.full_view.show(self.gen2d_interactable(cell)))
        Exporting.save_arr_item("generations2d", path)
        # self.generations.show_full_view_window(cell.config.id)        
    
    def gallery_on_delete_cell(self, gallery, item_name, cell):
        gallery.remove(cell.index)
        Exporting.remove_arr_item(item_name, cell.image_path)
        self.full_view.close()
        
    def gen2d_interactable(self, cell):

        if isinstance(cell, ImageCell):
            return FullViewWindowData(
                interactable=FullViewImageInteractable(cell.image_path), 
                buttons=[   FullViewButtonData(name="Удалить", action=lambda: self.gallery_on_delete_cell(self.gen2d, "generations2d", cell)),
                            FullViewButtonData(name="Закрыть", action=lambda: self.full_view.close())
            ])
        return None
    
class ArchiContextWindow(QDockWidget):
    masterApi: MasterAPI
    authSession: AuthenticatedSession
    behaviours: List[ProjectBehaviour] = []
    def __init__(self, authSession, parent=None):
        # --- Set parameters ---
        self.mv = parent
        self.masterApi = authSession.masterAPI
        self.authSession = authSession
        
        # --- Initialize the dock widget ---
        
        super(ArchiContextWindow, self).__init__(parent)

        self.setWindowTitle("Project Context")
        central_widget = QWidget()
        self.setWidget(central_widget)
        scroll_area = QScrollArea(central_widget)
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_area.setWidget(scroll_content)
        main_layout = QVBoxLayout(scroll_content)
        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(scroll_area)
      
        # --- Header ---
        header_label = QLabel("Project Context")
        header_label.setStyleSheet("font-size: 18pt; font-weight: bold;")

        main_layout.addWidget(header_label)

        # --- Subheader: Parameters ---

        params_group = QGroupBox()
        form_layout = QFormLayout(params_group)
        main_layout.addWidget(params_group)

        # 1) Prompt (text field)
        prompt_label = QLabel("Контекст проекта")
        prompt_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setAlignment(Qt.AlignTop)
        self.prompt_edit.setPlaceholderText("Опишите это здание. Добавьте информацию об окружении, ландшафте, истории, контексте здания")
        self.prompt_edit.textChanged.connect(lambda: Exporting.save_prop("prompt", self.prompt_edit.text()))
        form_layout.addRow(prompt_label)
        form_layout.addRow(self.prompt_edit)

        # --- Subheader: Sketch Gallery ---
        side_gallery_style = GalleryStyle(
            number_of_cols=2,
            min_dock_height=300,
            max_dock_height=400,
            width_of_cell=200,
            gap=10
        )
        
        self.full_view = FullViewWindow()
        main_window = FreeCADGui.getMainWindow()
        # ✅ Ищем панель "Model" и добавляем рядом
        model_dock = None
        for dock in main_window.findChildren(QDockWidget):
            if "Модель" in dock.windowTitle() or "Задачи" in dock.windowTitle():  # Проверяем, есть ли "Model" в заголовке
                model_dock = dock
                break
        if model_dock:
            main_window.tabifyDockWidget(model_dock, self.full_view)
        else:
            main_window.addDockWidget(Qt.LeftDockWidgetArea, self.full_view)
        self.full_view.hide()
        
        
        sketch_group = QGroupBox()
        sketch_layout = QFormLayout(sketch_group)
        main_layout.addWidget(sketch_group)
    
        self.sketch_label = QLabel("Концепты")
        self.sketch_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        sketch_layout.addWidget(self.sketch_label)

        self.sketches = GalleryWidget(side_gallery_style)
        self.sk_button = QPushButton("Добавить")
        self.sk_button.clicked.connect(
            lambda: self.sketches.select_and_add_images("sketches", lambda cell:self.full_view.show(FullViewImageInteractable(cell.image_path))) )
        
     
        sketch_layout.addWidget(self.sketches)
        sketch_layout.addWidget(self.sk_button)
        
    

        # --- Subheader: Generations ---
        env_label = QLabel("AI 2D")
        env_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        main_layout.addWidget(env_label)
        self.gen2d = GalleryWidget(side_gallery_style)
        gen_renders_button = QPushButton("В рендеры!")
        gen_renders_button.clicked.connect(lambda: Generate2dBehaviour(self.authSession, self.masterApi, self.sketches, self.gen2d, self.full_view, self.prompt_edit))
        main_layout.addWidget(gen_renders_button)
        main_layout.addWidget(self.gen2d)

        self.gen3d_renders_button = QPushButton("В 3D Модели!")
        self.gen3d_renders_button.clicked.connect(self.show_best_render)
        main_layout.addWidget(self.gen3d_renders_button)
        # --- Subheader: Visualization ---
        three_d_env_label = QLabel("AI 3D")
        three_d_env_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        main_layout.addWidget(three_d_env_label)
        
        self.gen3dstyle = GalleryStyle(
            number_of_cols=2,
            min_dock_height=400,
            max_dock_height=400,
            width_of_cell = 200,
        )
        self.view_3d_style = View3DStyle(
            model_scale=1,
            light_intensity=1,
            light_direction=QVector3D(-90, -45, 70),
            camera_position=QVector3D(3, 0.5, 0),
        )
        self.gen3d = GalleryWidget(self.gen3dstyle)
        main_layout.addWidget(self.gen3d)
        self.load_from_model(Exporting.load())
        
    
    def replace_full_image(self, index):
        path = select_images("sketches", True)
        if(path != None):
            cell = ImageCell(image_path=path)
            self.sketches.change_cell(index, cell)
            self.full_view.show(self.sketch_interactable(cell))
            
    def gallery_on_delete_cell(self, gallery, item_name, cell):
        gallery.remove(cell.index)
        Exporting.remove_arr_item(item_name, cell.image_path)
        self.full_view.close()
        
    def sketch_interactable(self, cell):

        if isinstance(cell, ImageCell):
            return FullViewWindowData(
                interactable=FullViewImageInteractable(cell.image_path),
                buttons=[   FullViewButtonData(name="Удалить", action= lambda: self.gallery_on_delete_cell(self.sketches, "sketches", cell)),
                            FullViewButtonData(name="Заменить", action=lambda: self.replace_full_image(cell.index)),
                            FullViewButtonData(name="Закрыть", action=lambda: self.full_view.close())
            ])
        return None
    
    def gen2d_interactable(self, cell):
        
        if isinstance(cell, ImageCell):
            return FullViewWindowData(
                interactable=FullViewImageInteractable(cell.image_path), 
                buttons=[   FullViewButtonData(name="Удалить", action=lambda: self.gallery_on_delete_cell(self.gen2d, "generations2d", cell)),
                            FullViewButtonData(name="Закрыть", action=lambda: self.full_view.close())
            ])
        return None

    def gen3d_interactable(self, cell):
        if isinstance(cell, View3DCell):
            return FullViewWindowData(
                interactable=FullView3DInteractable(cell.view3dData),
                buttons=[   FullViewButtonData(name="Удалить", action=lambda: self.gallery_on_delete_cell(self.gen3d, "generations3d", cell)),
                            FullViewButtonData(name="Закрыть", action=lambda: self.full_view.close())
            ])
        return None
    
    def load_from_model(self, model:Exporting.ProjectContextModel):
        self.prompt_edit.setText(model.prompt)
        self.sketches.add_cells([ImageCell(image_path=path) for i,path in enumerate(model.sketches)])
        for sketch_cell in self.sketches.cells:
            sketch_cell.action.connect(lambda cell: self.full_view.show(self.sketch_interactable(cell)))
        
        self.gen2d.add_cells([ImageCell(image_path=path) for i,path in enumerate(model.generations2d)])
        for gen2d_cell in self.gen2d.cells:
            gen2d_cell.action.connect(lambda cell: self.full_view.show(self.gen2d_interactable(cell)))
        
        self.gen3d.add_cells([View3DCell(data, self.view_3d_style) for i,data in enumerate(model.generations3d) if data.local is not None])
        for gen3d_cell in self.gen3d.cells:
            gen3d_cell.action.connect(lambda cell: self.full_view.show(self.gen3d_interactable(cell)))
        
       
    def show_best_render(self):
        # Get sketches
        self.create3dModel = PrepareFor3dGen(self.gen2d, self.authSession, self.on_obj_id_generated)
        FreeCADGui.getMainWindow().addDockWidget(Qt.LeftDockWidgetArea, self.create3dModel)
        self.create3dModel.setFloating(True)
        self.create3dModel.show()
        
    def on_obj_id_generated(self, result: Optional[Models.Gen3dId], error: Optional[Exception]):
        if(error or result is None):
            return
        saved= Models.Gen3dSaved(
            local=None,
            online=None,
            obj_id=result.obj_id
        )
        Exporting.save_arr_item("generations3d", saved.model_dump())
        self.behaviours.append(DownloadModelBehaviour(lambda x: print("Status of loading model - ",x),  self.gen3d, result, self.view_3d_style, self.authSession))

class Archi_ProjectContext_Command:
    def __init__(self, authenticatedSession):
        self.authenticatedSession = authenticatedSession

    def GetResources(self):
        return {
            "MenuText": "Project Context",
            "ToolTip": "Initialize or manage project context",
            "Pixmap": "Archi_ProjectContext"
        }

    def Activated(self):
        mw = FreeCADGui.getMainWindow()
        # find dock widgets with name Project Context
        dock_widgets = mw.findChildren(QDockWidget)
        for widget in dock_widgets:
            if widget.windowTitle() == "Project Context":
                widget.close()
            if widget.windowTitle() == "Best Sketch":
                widget.close()
            if widget.windowTitle() == "Full View":
                widget.close()
            if widget.windowTitle() == "Полный просмотр":
                widget.close()
            
		
        projectContextWindowInstance = ArchiContextWindow(self.authenticatedSession,mw)
        mw.addDockWidget(Qt.RightDockWidgetArea, projectContextWindowInstance)
        projectContextWindowInstance.show()

    def IsActive(self):
        return True
    
mw = FreeCADGui.getMainWindow()
# find dock widgets with name Project Context
dock_widgets = mw.findChildren(QDockWidget)
for widget in dock_widgets:
    if widget.windowTitle() in ["Project Context", "Best Sketch", "Full View"]:
        mw.removeDockWidget(widget
        )
        widget.close()

authenticatedSession = AuthenticatedSession(masterAPI=MasterAPI("http://89.169.36.93:8001"))
projectContextWindowInstance = ArchiContextWindow(authenticatedSession,mw)
mw.addDockWidget(Qt.RightDockWidgetArea, projectContextWindowInstance)
projectContextWindowInstance.show()