import FreeCADGui
from PySide.QtCore import Qt, QObject, Signal, QEvent
from PySide.QtGui import QPixmap, QPainter, QPainterPath, QWheelEvent
from PySide.QtWidgets import (QWidget, QLabel, QVBoxLayout, QScrollArea, QFileDialog,
                              QPushButton, QHBoxLayout, QDockWidget, QTabWidget, QApplication, QSizePolicy) # Added QApplication

from PySide.QtCore import QTimer, QPoint
from PySide.QtCore import Qt
from tools.view_3d import View3DWindow
import tools.exporting as exporting
from tools.models import Gen2dResult
from tools.image_viewer import ImageViewer
from tools.video_player import VideoPlayerWidget
from typing import List, Dict, Callable, Optional
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
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            print("FullViewWindow: Creating new instance.")
            cls._instance = super().__new__(cls, *args, **kwargs)
        else:
            print("FullViewWindow: Returning existing instance.")
        return cls._instance

    def __init__(self, parent = None):
        if self._initialized:
            return # Prevent re-initialization for the singleton instance
        print("FullViewWindow: Initializing instance.")

        # Find main window as parent if None is provided explicitly
        actual_parent = parent or FreeCADGui.getMainWindow()
        super().__init__(actual_parent)

        self.setWindowTitle("Полный просмотр")
        self._setup_ui()

        # Initialize state variables
        self.buttons_data: List[FullViewButtonData] = []
        self.interactable: Optional[QWidget] = None
        self.button_widgets: List[QPushButton] = []

        # Set initial allowed area (can be changed later if needed)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        self.setFloating(False) # Usually starts docked
        
        # Set size policy to allow some flexibility but prevent excessive stretching
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
        # Set reasonable size limits
        self.setMinimumSize(400, 300)
        self.setMaximumSize(800, 600)

        self._initialized = True # Mark as initialized

    def _setup_ui(self):
        """Sets up the main widget and layout structure."""
        container_widget = QWidget()
        self.setWidget(container_widget)
        self.layout = QVBoxLayout(container_widget)
        self.layout.setContentsMargins(0, 0, 0, 0) # No margins for main layout

        # Placeholder for interactable content (added in show)
        # self.interactable_container = QWidget() # Or directly add interactable
        # self.layout.addWidget(self.interactable_container, 1) # Stretch factor 1

        # Layout for buttons
        self.button_container_widget = QWidget() # Use a widget container for the HBox
        self.button_container_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed) # Fixed height
        self.button_container_widget.setMaximumHeight(50) # Limit maximum height
        self.button_container_layout = QHBoxLayout(self.button_container_widget)
        self.button_container_layout.setContentsMargins(5, 5, 5, 5) # Some margins for buttons
        self.button_container_layout.setSpacing(5) # Add spacing between buttons
        self.layout.addWidget(self.button_container_widget, 0, Qt.AlignmentFlag.AlignBottom) # Stretch factor 0, align to bottom

    def _clear_content(self):
        """Removes the current interactable widget and buttons."""
        print("FullViewWindow: Clearing content.")
        # Remove interactable widget
        if self.interactable:
            self.layout.removeWidget(self.interactable)
            self.interactable.deleteLater()
            self.interactable = None

        # Remove buttons
        for button_widget in self.button_widgets:
            self.button_container_layout.removeWidget(button_widget)
            button_widget.deleteLater()
        self.button_widgets.clear()

        # Hide button container if it's empty (optional, keeps layout clean)
        self.button_container_widget.setVisible(False)

    def show(self, data: Optional[FullViewWindowData]):
        """Shows new content in the FullViewWindow, replacing existing content."""
        print(f"FullViewWindow: show called with data: {'Present' if data else 'None'}")
        self._clear_content() # Clear previous content first

        if data is None or data.interactable is None:
            print("FullViewWindow: No data or interactable provided, hiding window.")
            self.hide() # Hide the window if no valid data is given
            return

        self.interactable = data.interactable
        self.buttons_data = data.buttons if data.buttons else []

        # Add interactable widget first (takes all available space)
        self.layout.insertWidget(0, self.interactable, 1) # Index 0, stretch factor 1 - take all available space

        # Add buttons (at the bottom)
        if self.buttons_data:
            for button_data in self.buttons_data:
                button_widget = QPushButton(button_data.name)
                # Ensure action is callable before connecting
                if callable(button_data.action):
                     button_widget.clicked.connect(button_data.action)
                else:
                     print(f"Warning: Action for button '{button_data.name}' is not callable.")
                self.button_widgets.append(button_widget)
                self.button_container_layout.addWidget(button_widget)
            self.button_container_widget.setVisible(True) # Show button container
        else:
            self.button_container_widget.setVisible(False) # Hide if no buttons

        # Ensure the dock widget itself is visible
        if not self.isVisible():
            print("FullViewWindow: Widget was hidden, calling super().show().")
            super().show() # Make the dock widget visible if it was hidden

        self.activate_window_or_tab() # Bring it to front / activate tab

    def activate_window_or_tab(self):
        """Brings the window to the front or activates its tab if tabified."""
        print("FullViewWindow: Activating window/tab.")
        # First, ensure the dock widget itself is raised if floating
        if self.isFloating():
            self.raise_()
            self.activateWindow()

        # Check if it's part of a QTabWidget (tabified)
        parent = self.parentWidget()
        tab_widget = None

        # Search up the hierarchy for a QTabWidget that contains this dock widget
        while parent:
            # Check if the parent is a QTabBar - common case for tabified docks
            # This logic might need adjustment depending on specific FreeCAD versions/setups
            if isinstance(parent, QTabWidget):
                 tab_widget = parent
                 break
            # Check if parent contains a QTabBar that *might* control this dock
            # This is less reliable
            tab_bars = parent.findChildren(QTabWidget)
            for tb in tab_bars:
                 if tb.indexOf(self) != -1:
                      tab_widget = tb
                      break
            if tab_widget:
                break
            parent = parent.parentWidget()

        if tab_widget:
            index = tab_widget.indexOf(self)
            if index != -1:
                print(f"FullViewWindow: Found in tab widget, setting current index to {index}.")
                tab_widget.setCurrentIndex(index)
                # Also ensure the containing window is active
                top_level_window = self.window()
                if top_level_window:
                    top_level_window.raise_()
                    top_level_window.activateWindow()
                return # Activation handled by tab widget

        # If not in a tab or floating, just try to raise it
        print("FullViewWindow: Not in a tab widget or failed to find, raising.")
        self.raise_()
        self.activateWindow() # May not work perfectly for docked widgets, but best effort

    def close(self):
        """Hides the FullViewWindow. Content is cleared on next show()."""
        print("FullViewWindow: Hiding window via close().")
        # Note: We don't clear content here anymore, it's cleared by show()
        super().hide()

    def closeEvent(self, event):
        """Overrides close event to hide instead of potentially deleting."""
        print("FullViewWindow: closeEvent triggered.")
        self.hide()
        event.ignore() # Prevent the default close behavior (which might delete the widget)

        
class FullView3DInteractable(QWidget):
    def __init__(self, view3dData:Gen2dResult, parent=None):
        super(FullView3DInteractable, self).__init__(parent)
        self.viewer = View3DWindow(view3dData)
        self.container = QWidget.createWindowContainer(self.viewer)
        
        # Set size policy to prevent stretching
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set reasonable size limits
        self.setMinimumSize(400, 300)
        self.setMaximumSize(800, 600)
        
        # Set initial size
        self.resize(500, 400)
        
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
        
        # Set size policy to prevent stretching
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set reasonable size limits
        self.setMinimumSize(400, 300)
        self.setMaximumSize(800, 600)
        
        # Set initial size
        self.resize(500, 400)
        
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.viewer)
        self.setLayout(self.layout)
        self.viewer.show()
        
        # Принудительно обновляем размеры и центрирование после показа
        QTimer.singleShot(100, self._update_viewer_layout)
    
    def _update_viewer_layout(self):
        """Обновляет размеры и центрирование ImageViewer после показа."""
        if self.viewer:
            self.viewer.resizeEvent(None)  # Принудительно вызываем resizeEvent


class FullViewVideoInteractable(QWidget):
    """Интерактивный просмотр видео с плеером"""
    
    def __init__(self, video_path: str, on_frame_added: Optional[Callable[[str], None]] = None, parent=None):
        super(FullViewVideoInteractable, self).__init__(parent)
        self.setWindowTitle("Видео")
        self.on_frame_added = on_frame_added
        
        self.player = VideoPlayerWidget(video_path, on_frame_added=on_frame_added, parent=self)
        
        # Set size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set reasonable size limits
        self.setMinimumSize(400, 300)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.player)
        self.setLayout(self.layout)
        self.player.show()
    
    def closeEvent(self, event):
        """Cleanup on close."""
        if hasattr(self, 'player'):
            self.player.closeEvent(event)
        super().closeEvent(event)

    def capture_current_frame(self) -> Optional[str]:
        """Capture current frame and notify callback."""
        if not hasattr(self, 'player'):
            return None
        frame_path = self.player.capture_frame()
        if frame_path and self.on_frame_added:
            self.on_frame_added(frame_path)
        return frame_path


