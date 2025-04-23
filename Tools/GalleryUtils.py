import FreeCADGui
import FreeCAD
from PySide.QtCore import Qt, QObject, Signal, QEvent
from PySide.QtGui import QPixmap, QPainter, QPainterPath, QWheelEvent
from PySide.QtWidgets import QWidget, QLabel, QVBoxLayout, QScrollArea, QFileDialog, QPushButton, QHBoxLayout, QDockWidget
from PySide.QtSvgWidgets import QSvgWidget
from PySide.QtCore import QTimer, QPoint
from PySide.QtCore import Qt
from Tools.View3d import View3DWindow
from Tools import Exporting
from typing import List, Dict
from pydantic import BaseModel, ConfigDict
from Tools import Models
from Tools.MasterAPI import MasterAPI
from Tools.View3d import View3DStyle

class GalleryCell(QWidget):

    action = Signal(QWidget)

    def __init__(self, parent:QObject=None):
        super().__init__(parent)
        self.index = None

    def trigger(self):
        if self.index is None:
            raise Exception("Index is not set")
        self.action.emit(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.trigger()
        super().mousePressEvent(event)
        
    def getHeight(self):
        return self.sizeHint().height()
        
    def close(self):
        self.setParent(None)
        self.deleteLater()
        
    def resize(self, width):
        self.setFixedSize(width, width)
        self.update()
    
    def copy(self):
        if isinstance(self, ImageCell):
            return ImageCell(self.image_path)
        elif isinstance(self, AnimatedCell):
            return AnimatedCell(self.svg_path)
        elif isinstance(self, View3DCell):
            return View3DCell(self.view3dData)
        else:
            return GalleryCell()

class ImageCell(GalleryCell):
    def __init__(self, image_path:str, parent=None):
        super().__init__( parent=parent)
        self.image_path = image_path
        self.pixmap = QPixmap(image_path)
        if self.pixmap.isNull():
            raise Exception(f"Image {image_path} is not valid")
        self.label = QLabel(self)
        self.label.setPixmap(self.pixmap)
        self.label.setParent(self)
        self.label.show()

    def resize(self, width):
        self.make_round(width)
        self.label.setPixmap(self.pixmap)
        self.label.show()
        self.update()
           
    def make_round(self, width):
        target_width = width
        
        scale_factor = target_width / self.pixmap.width()
        target_height = int(self.pixmap.height() * scale_factor)
        pixmap = self.pixmap.scaled(target_width, target_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        path = QPainterPath()
        path.addRoundedRect(0, 0, target_width, target_height, 10, 10)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        self.label.setFixedSize(target_width, target_height)
        self.setFixedSize(target_width, target_height)
        self.pixmap = rounded
        
class AnimatedCell(GalleryCell):

    def __init__(self, svg_path, frame_duration: int = 100, parent=None):
        super().__init__(parent=parent)
        self.svg_path = svg_path

        # Background label with pixmap
        self.background = QLabel(self)
        self.background.setScaledContents(True)
        self.background.show()

        # SVG animation in front
        self.svg_widget = QSvgWidget(self)
        self.svg_widget.load(self.svg_path)
        self.svg_widget.show()

        self.frame_duration = frame_duration
        self.frame = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.svg_widget.update)
        self.timer.start(800)

    def setBackground(self, url, effect = None):
        self.background.setPixmap(QPixmap(url))
        if(effect):
            self.background.setGraphicsEffect(effect)
        self.background.show()
        self.update()

    def close(self):
        self.timer.stop()
        super().close()

    def resize(self, width):
        size = self.svg_widget.sizeHint()
        height = size.height() * width / size.width()

        # Fill the background as well
        self.background.setFixedSize(width, height)
        self.svg_widget.setFixedSize(width, height)

        self.setFixedSize(width, height)
        self.update()
class LoadingCell(AnimatedCell):
    def __init__(self, svg_path = None, parent=None):
        if not svg_path:
            svg_path = FreeCAD.getResourceDir() + "Mod/ArchiModule/Resources/anims/Archi_Preloader.svg"
        super().__init__(svg_path, frame_duration=100, parent=parent)

    def update_progress(self, progress):
        print("Progress: ", progress)

class View3DCell(GalleryCell):
    view3dData:Models.Gen3dSaved = None
    def __init__(self, view3dData:Models.Gen3dSaved, view_3d_style:View3DStyle, parent=None):
        super().__init__(parent=parent)
        self.view3dData = view3dData
        self.viewer = View3DWindow(self.view3dData.local, view_3d_style)
        self.container = QWidget.createWindowContainer(self.viewer)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.container)
        self.setLayout(self.layout)
   
    def close(self):
        self.viewer.close()
        super().close()

    def resize(self, width):
        self.viewer.resize(width, width)
        super().resize(width)

class GalleryStyle(BaseModel):
    number_of_cols: int = 3
    min_dock_height: int = 200
    max_dock_height: int = 300
    width_of_cell: int = 200
    gap: int = 10
    styleSheet: str = None
    model_config = ConfigDict(arbitrary_types_allowed=True)

class GalleryWidget(QWidget):
    def __init__(self, gallery_style: GalleryStyle):
        super(GalleryWidget, self).__init__()
        self.galleryStyle = gallery_style
        self.cells:List[GalleryCell] = []
        # --- Subheader: Sketches ---
        content = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setWidget(content)
        scroll_area.setMinimumHeight(self.galleryStyle.min_dock_height)
        scroll_area.setMaximumHeight(self.galleryStyle.max_dock_height)
        
        if self.galleryStyle.styleSheet:
            scroll_area.setStyleSheet(self.galleryStyle.styleSheet)
        else:
            parent_widget = self.parent() if self.parent() is not None else self
            # scroll_area.setStyleSheet(f"background-color: {parent_widget.palette().color(parent_widget.backgroundRole()).name()};")
            scroll_area.setStyleSheet(f"background-color: #222222;");



        self.heights = [0] * self.galleryStyle.number_of_cols
        # Create a horizontal layout to hold the vertical layouts
        horizontal_layout = QHBoxLayout(content)
        horizontal_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        horizontal_layout.setContentsMargins(0, 0, 0, 0)
        horizontal_layout.setSpacing(self.galleryStyle.gap)

        self.v_layouts = []
        for _ in range(self.galleryStyle.number_of_cols):
            v_layout = QVBoxLayout()
            v_layout.setAlignment(Qt.AlignTop)
            v_layout.setSpacing(self.galleryStyle.gap)
            self.v_layouts.append(v_layout)
            horizontal_layout.addLayout(v_layout)

        horizontal_layout.setSpacing(self.galleryStyle.gap)
        content.setLayout(horizontal_layout)

        # # Main layout for the GalleryWidget
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(scroll_area)
    
    def add_cell(self, cell:GalleryCell) -> int:
        cell.resize(self.galleryStyle.width_of_cell)
        y = self.heights.index(min(self.heights))
        self.heights[y] += cell.getHeight() + self.galleryStyle.gap
        self.v_layouts[y].addWidget(cell)

        cell.index = len(self.cells)
        self.cells.append(cell)

        self.replace_nice()
        return len(self.cells) - 1
        
    def add_cells(self, cells:List[GalleryCell]):
        for cell in cells:
            cell.resize(self.galleryStyle.width_of_cell)
            y = self.heights.index(min(self.heights))
            self.v_layouts[y].addWidget(cell)
            
            self.heights[y] += cell.getHeight() + self.galleryStyle.gap
            cell.index = len(self.cells)
            self.cells.append(cell)
            cell.show()
            
        self.replace_nice()
    
    def remove(self, index:int):
        if index >= len(self.cells):
            index = len(self.cells) - 1
        self.cells[index].close()
        self.cells.pop(index)
        self.replace_nice()
        
    def replace_nice(self):
        self.heights = [0] * self.galleryStyle.number_of_cols
        for i in range(len(self.cells)):
            y = self.heights.index(min(self.heights))
            self.v_layouts[y].insertWidget(0, self.cells[i])
            self.heights[y] += self.cells[i].getHeight() + self.galleryStyle.gap
            
    def change_cell(self, index:int, new_cell:GalleryCell):
        new_cell.resize(self.galleryStyle.width_of_cell)
        new_cell.index = index
        self.cells[index].close()
        self.cells[index] = new_cell
        self.replace_nice()
        
    def select_and_add_images(self, folder, action):
        paths = select_images(folder)
        for path in paths:
            self.add_cell(ImageCell(path))
            self.cells[-1].action.connect(action)




def select_images(folder, single=False):
    """
    Open a file dialog to let the user pick one or more image files.
    Then create thumbnails and add them to the sketches_layout.
    """
    # Open file dialog. On macOS, this will use the native Finder dialog.
    if single:
        file, _ = QFileDialog.getOpenFileName(
            None,
            "Select an image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not file:
            return  # user canceled
        path = Exporting.save_source(folder, file)
        return path
    else:
        files, _ = QFileDialog.getOpenFileNames(
            None,
            "Select one or more images",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not files:
            return  # user canceled
        paths = []
        for i in range(len(files)):
            path = Exporting.save_source(folder, files[i])
            paths.append(path)
        return paths