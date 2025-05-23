import FreeCADGui
import FreeCAD
from PySide.QtCore import Qt, QObject, Signal, QEvent, QPropertyAnimation, QEasingCurve, QPoint, Property, QSequentialAnimationGroup, QPauseAnimation
from PySide.QtGui import QPixmap, QPainter, QPainterPath, QWheelEvent, QPen, QColor, QLinearGradient
from PySide.QtWidgets import QWidget, QLabel, QVBoxLayout, QScrollArea, QFileDialog, QPushButton, QHBoxLayout, QDockWidget
from PySide.QtSvgWidgets import QSvgWidget
from PySide.QtCore import QTimer
from tools.view_3d import View3DWindow
import tools.exporting as exporting
from typing import List, Dict
from pydantic import BaseModel, ConfigDict
from tools.models import Gen3dSaved
from tools.master_api import MasterAPI
from tools.view_3d import View3DStyle
import time
import tools.log as log
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

    def paintEvent(self, event):
        super().paintEvent(event)
        if hasattr(self, 'svg_widget') and self.svg_widget:
            # Keep background transparent
            self.svg_widget.setStyleSheet("""
                QSvgWidget {
                    background: transparent;
                }
            """)

class LoadingCell(GalleryCell):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._target_progress = 0
        self._current_progress = 0
        self._is_closing = False
        self.setMinimumSize(200, 200)
        self.setMaximumSize(200, 200)
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        
        # Animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(16)  # ~60 FPS

        # Progress update timer
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._update_progress)
        self.progress_timer.start(2000)  # Update every 600 milliseconds
        self.estimated_time = 1000  # Estimated time in seconds
        self.start_time = time.time()

        # Create animations for each circle
        self._circle_positions = [0, 0, 0]  # Current positions of circles
        self.circle_animations = []
        
        # Create three animations with different speeds
        speeds = [3000, 2800, 2700]  # Duration in milliseconds (slower for first circle)
        for i in range(3):
            # Create animation group
            group = QSequentialAnimationGroup()
            
            # Create the movement animation
            anim = QPropertyAnimation(self, f"circle{i}_position".encode())
            anim.setDuration(speeds[i])  # Different duration for each circle
            anim.setStartValue(0)
            anim.setEndValue(70)
            anim.setEasingCurve(QEasingCurve.InOutQuad)  # Smooth ease in/out
            group.addAnimation(anim)
            
            # Create the return animation
            return_anim = QPropertyAnimation(self, f"circle{i}_position".encode())
            return_anim.setDuration(speeds[i])  # Same duration for return
            return_anim.setStartValue(70)
            return_anim.setEndValue(0)
            return_anim.setEasingCurve(QEasingCurve.InOutQuad)  # Smooth ease in/out
            group.addAnimation(return_anim)
            
            group.setLoopCount(-1)  # Infinite loop
            group.start()
            
            self.circle_animations.append(group)

    def _reset_circle_position(self, index):
        """Reset circle position when animation finishes."""
        self._circle_positions[index] = 0
        self.update()

    def _get_circle0_position(self):
        return self._circle_positions[0]
    def _set_circle0_position(self, value):
        self._circle_positions[0] = value
        self.update()
    circle0_position = Property(float, _get_circle0_position, _set_circle0_position)

    def _get_circle1_position(self):
        return self._circle_positions[1]
    def _set_circle1_position(self, value):
        self._circle_positions[1] = value
        self.update()
    circle1_position = Property(float, _get_circle1_position, _set_circle1_position)

    def _get_circle2_position(self):
        return self._circle_positions[2]
    def _set_circle2_position(self, value):
        self._circle_positions[2] = value
        self.update()
    circle2_position = Property(float, _get_circle2_position, _set_circle2_position)

    def _get_target_progress(self):
        return self._target_progress
    def _set_target_progress(self, value):
        self._target_progress = value
        self.update()
    target_progress = Property(float, _get_target_progress, _set_target_progress)

    def _get_current_progress(self):
        return self._current_progress
    def _set_current_progress(self, value):
        self._current_progress = value
        self.update()
    current_progress = Property(float, _get_current_progress, _set_current_progress)

    def _update_animation(self):
        """Update animation frame with linear interpolation."""
        if self._is_closing:
            return  # Skip interpolation during closing animation
            
        if abs(self._current_progress - self._target_progress) > 0.1:
            # Linear interpolation
            self._current_progress += (self._target_progress - self._current_progress) * 0.1
            # Ensure progress stays within bounds
            self._current_progress = max(0, min(100, self._current_progress))
            self.update()
        elif self._current_progress != self._target_progress:
            self._current_progress = self._target_progress
            self.update()

    def update_progress(self, progress):
        """Update target loading progress (0-100)."""
        if(self.target_progress > progress):
            return
        self._target_progress = max(0, min(100, progress))

    def _update_progress(self):
        """Update progress based on elapsed time."""
        elapsed = time.time() - self.start_time
        progress = min(95, (elapsed / self.estimated_time) * 100)  # Cap at 95% until complete
        self.update_progress(progress)

    def set_estimated_time(self, seconds):
        """Set the estimated time for the operation."""
        self.estimated_time = seconds
        self.start_time = time.time()
        self._update_progress()  # Initial update

    def complete(self):
        """Mark the loading as complete."""
        self.progress_timer.stop()
        self.update_progress(100)  # Set to 100%

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw animated circles
        circle_colors = [QColor("#1088FF"), QColor("#7B3CF7"), QColor("#E93CF7")]
        circle_positions = [40, 100, 160]  # x positions
        
        # Calculate transparency for each circle based on progress
        transparencies = [
            min(1, self._current_progress/100*0.9 + 0.4),  # First circle
            min(1, self._current_progress/100*0.8 + 0.2),  # Second circle
            min(1, self._current_progress/100)         # Third circle
        ]
        
        for i in range(3):
            painter.setPen(Qt.NoPen)
            color = circle_colors[i]
            # Set alpha based on progress
            color.setAlphaF(transparencies[i])
            painter.setBrush(color)
            painter.drawEllipse(
                QPoint(circle_positions[i], 65 + self._circle_positions[i]),
                20, 20
            )
        
        if self._current_progress > 0:
            # Calculate bar parameters
            margin = 10  # Margin from edges
            bar_width = self.width() - (2 * margin)
            progress_width = int((bar_width * self._current_progress) / 100)
            bar_height = 10  # Height of the progress bar
            radius = bar_height / 2  # Radius for rounded corners
            
            # Create gradient
            gradient = QLinearGradient(
                margin,  # x1
                self.height() - 10,  # y1
                self.width() - margin,  # x2
                self.height() - 10  # y2
            )
            
            # Set gradient colors based on progress
            start_color = QColor("#1088FF")
            end_color = QColor("#E93CF7")
            
            # Interpolate colors based on progress
            r = start_color.red() + (end_color.red() - start_color.red()) * (self._current_progress / 100)
            g = start_color.green() + (end_color.green() - start_color.green()) * (self._current_progress / 100)
            b = start_color.blue() + (end_color.blue() - start_color.blue()) * (self._current_progress / 100)
            mid_color = QColor(int(r), int(g), int(b))
            
            gradient.setColorAt(0, start_color)
            gradient.setColorAt(0.5, mid_color)
            gradient.setColorAt(1, end_color)
            
            # Create rounded rectangle path
            path = QPainterPath()
            y = self.height() - 10 - bar_height/2  # Center vertically
            
            # Start with rounded left end
            path.moveTo(margin + radius, y)
            path.arcTo(margin, y, radius * 2, bar_height, 90, 180)
            
            # Draw the main rectangle
            path.lineTo(margin + progress_width - radius, y + bar_height)
            path.lineTo(margin + progress_width - radius, y)
            
            # Add rounded right end
            path.arcTo(margin + progress_width - radius * 2, y, radius * 2, bar_height, 270, 180)
            path.closeSubpath()
            
            # Draw the rounded progress bar with gradient
            painter.fillPath(path, gradient)

    def close(self):
        # Stop progress timer
        if hasattr(self, 'progress_timer'):
            self.progress_timer.stop()
            self.progress_timer.deleteLater()
            del self.progress_timer

        # Stop animation timer
        if hasattr(self, 'animation_timer'):
            self.animation_timer.stop()
            self.animation_timer.deleteLater()
            del self.animation_timer

        # Stop and clean up circle animations
        if hasattr(self, 'circle_animations'):
            for anim in self.circle_animations:
                if anim:
                    anim.stop()
                    anim.deleteLater()
            self.circle_animations.clear()
            del self.circle_animations

        # Clear circle positions
        if hasattr(self, '_circle_positions'):
            self._circle_positions.clear()
            del self._circle_positions

        # Call parent close
        super().close()

    def show_max_progress_and_close(self, callback=None, duration=1000):
        """Animate to max progress and close the cell.
        
        Args:
            callback: Optional callback to call after closing
            duration: Duration of the animation in milliseconds
        """
        self._set_target_progress(100)
        # subscribe callback to the close event
        if callback:
            self.progress_timer.timeout.connect(lambda: self._check_progress_and_close(callback))
        else:
            self.progress_timer.timeout.connect(lambda: self._check_progress_and_close(None))

    def _check_progress_and_close(self, callback):
        """Check if progress is complete and close if it is."""
        if self._current_progress >= 100:
            self.progress_timer.stop()
            if callback:
                self._close_with_callback(callback)
            else:
                self.close()

    def _close_with_callback(self, callback):
        """Close the cell and call the callback."""
        self.close()
        callback()

class View3DCell(GalleryCell):
    view3dData:Gen3dSaved = None
    def __init__(self, view3dData:Gen3dSaved, view_3d_style:View3DStyle, parent=None):
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
        if not folder:
            return
        
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
        path = exporting.save_source(folder, file)
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
            path = exporting.save_source(folder, files[i])
            paths.append(path)
        return paths