import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import FreeCADGui
import FreeCAD
from PySide.QtCore import (Qt, QObject, Signal, QEvent, QPropertyAnimation, QEasingCurve, QPoint, Property,
                           QSequentialAnimationGroup, QPauseAnimation, QRectF, QTimer)
from PySide.QtGui import (QPixmap, QPainter, QPainterPath, QWheelEvent, QPen, QColor, QLinearGradient, QFont,
                          QRadialGradient, QRegion)
from PySide.QtWidgets import (QWidget, QLabel, QVBoxLayout, QScrollArea, QFileDialog, QPushButton, QHBoxLayout,
                               QDockWidget, QStackedLayout, QSizePolicy)
from PySide.QtSvgWidgets import QSvgWidget

try:
    from PySide6.QtMultimedia import QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget
    HAS_QT6_MEDIA = True
    QMediaContent = None
except ImportError:
    try:
        from PySide.QtMultimedia import QMediaPlayer, QMediaContent
        from PySide.QtMultimediaWidgets import QVideoWidget
        HAS_QT6_MEDIA = False
    except ImportError:
        QMediaPlayer = None
        QVideoWidget = None
        QMediaContent = None
        HAS_QT6_MEDIA = False
from tools.view_3d import View3DWindow
import tools.exporting as exporting
from typing import List, Dict, Optional
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
        if event.button() == Qt.MouseButton.LeftButton:
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
            return View3DCell(self.view3dData, self.view_3d_style)
        elif isinstance(self, VideoCell):
            return VideoCell(self.video_path)
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
        pixmap = self.pixmap.scaled(target_width, target_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
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
        self.estimated_time = None  # Estimated time in seconds (None means not set)
        self.start_time = time.time()
        
        # Timer for updating estimated time display
        self.estimated_time_timer = QTimer()
        self.estimated_time_timer.timeout.connect(self._update_estimated_time_display)
        self.estimated_time_timer.start(1000)  # Update every second

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

    def update_progress(self, progress, estimated_time=None):
        """Update target loading progress (0-100) and optionally set estimated_time."""
        if(self.target_progress > progress):
            return
        self._target_progress = max(0, min(100, progress))
        # Update estimated_time if provided
        if estimated_time is not None:
            self.set_estimated_time(estimated_time)

    def _update_progress(self):
        """Update progress based on elapsed time."""
        if self.estimated_time is None:
            return  # Don't update progress if estimated_time is not set
        elapsed = time.time() - self.start_time
        progress = min(95, (elapsed / self.estimated_time) * 100)  # Cap at 95% until complete
        self.update_progress(progress)
    
    def _update_estimated_time_display(self):
        """Update the estimated time display text."""
        if self.estimated_time is not None:
            self.update()  # Trigger repaint to update estimated time text

    def set_estimated_time(self, seconds):
        """Set the estimated time for the operation."""
        self.estimated_time = seconds if seconds is not None and seconds > 0 else None
        self.start_time = time.time()
        self._update_progress()  # Initial update
        self.update()  # Trigger repaint to show estimated time

    def complete(self):
        """Mark the loading as complete."""
        self.progress_timer.stop()
        self.update_progress(100)  # Set to 100%

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
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
        
        # Draw estimated time text between circles and progress bar (if estimated_time is set)
        if self.estimated_time is not None and self.estimated_time > 0:
            elapsed = time.time() - self.start_time
            remaining = max(0, self.estimated_time - elapsed)
            
            # Format time
            if remaining == 0:
                time_text = "Еще чуть чуть.."
            else:
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                if minutes > 0:
                    time_text = f"⏱️  Осталось: {minutes}м {seconds}с"
                else:
                    time_text = f"⏱️  Осталось: {seconds}с"
            
            # Position text between circles (y ~135) and progress bar (y ~height()-15)
            # Place it at approximately y = 150
            text_y = 180
            
            # Create gradient for text (same colors as progress bar)
            start_color = QColor("#1088FF")
            end_color = QColor("#E93CF7")
            
            # Create text gradient (horizontal)
            text_gradient = QLinearGradient(
                self.width() // 2 - 50, text_y,  # x1
                self.width() // 2 + 50, text_y   # x2
            )
            text_gradient.setColorAt(0, start_color)
            text_gradient.setColorAt(1, end_color)
            
            # Draw text with gradient
            painter.setPen(QPen(text_gradient, 1))
            font = painter.font()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            
            # Center the text
            text_rect = painter.fontMetrics().boundingRect(time_text)
            text_x = (self.width() - text_rect.width()) // 2
            
            # Draw text with gradient (using QPainterPath for gradient text)
            path = QPainterPath()
            path.addText(text_x, text_y, font, time_text)
            painter.fillPath(path, text_gradient)
        
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
        
        # Stop estimated time timer
        if hasattr(self, 'estimated_time_timer'):
            self.estimated_time_timer.stop()
            self.estimated_time_timer.deleteLater()
            del self.estimated_time_timer

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
        self.view_3d_style = view_3d_style
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

class VideoCell(GalleryCell):
    """Interactive video preview cell with hover playback and vignette overlay."""

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent=parent)
        self.video_path = video_path
        self.preview_pixmap: Optional[QPixmap] = None
        self.preview_container: Optional[QWidget] = None
        self.overlay_label: Optional[QLabel] = None
        self.video_widget = None
        self.player = None
        self._video_dimensions: tuple[int, int] = (0, 0)
        self._base_size = 200
        self._hovered = False
        self._has_cpp_player = False
        self.is_boarding = False

        self._hover_leave_timer = QTimer(self)
        self._hover_leave_timer.setSingleShot(True)
        self._hover_leave_timer.timeout.connect(self._stop_preview_immediate)

        self._load_first_frame()
        self._probe_dimensions()
        self._initialize_view()
   
    def _load_first_frame(self):
        pixmap = self._extract_first_frame()
        if pixmap is None:
            pixmap = self._create_placeholder_pixmap(256)
        self.preview_pixmap = pixmap
        if pixmap and pixmap.width() > 0 and pixmap.height() > 0:
            self._video_dimensions = (pixmap.width(), pixmap.height())

    def _probe_dimensions(self):
        if self._video_dimensions != (0, 0):
            return
        ffprobe = shutil.which("ffprobe")
        if not ffprobe or not self.video_path or not os.path.exists(self.video_path):
            return
        cmd = [
            ffprobe,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            self.video_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            if output:
                width_str, height_str = output.split("x")
                self._video_dimensions = (int(width_str), int(height_str))
        except Exception:  # pylint: disable=broad-except
            pass

    def _initialize_view(self):
        from tools.video_player import VideoPlayerWidget, HAS_CPP_PLAYER

        if HAS_CPP_PLAYER:
            try:
                preview_path = self._ensure_preview_video()
                self._setup_cpp_player(VideoPlayerWidget, preview_path)
                self._has_cpp_player = True
                return
            except Exception as exc:  # pylint: disable=broad-except
                FreeCAD.Console.PrintWarning(f"VideoCell: failed to init C++ video preview: {exc}\n")

        self._setup_static_preview()

    def _setup_cpp_player(self, player_cls, preview_path: Optional[str]):
        self.preview_container = QWidget(self)
        self.preview_container.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.preview_container.setMouseTracking(True)
        self.preview_container.installEventFilter(self)

        self.video_widget = player_cls(preview_path or self.video_path, parent=self.preview_container)
        self.video_widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.video_widget.setMouseTracking(True)
        self.video_widget.installEventFilter(self)
        self.video_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        if hasattr(self.video_widget, "set_controls_visible"):
            self.video_widget.set_controls_visible(False)
        if hasattr(self.video_widget, "set_auto_loop"):
            self.video_widget.set_auto_loop(True)
        self._prime_cpp_preview()

        self.overlay_label = QLabel(self.preview_container)
        self.overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.overlay_label.setStyleSheet("background: transparent;")
        self.overlay_label.installEventFilter(self)

        stack = QStackedLayout(self.preview_container)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setStackingMode(QStackedLayout.StackAll)
        stack.addWidget(self.video_widget)
        stack.addWidget(self.overlay_label)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preview_container)
        self.setLayout(layout)
        self.resize(self._base_size)

    def _setup_static_preview(self):
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.label)
        self.setLayout(layout)
        self._render_static_preview(self._base_size)

    def _extract_first_frame(self) -> Optional[QPixmap]:
        if not self.video_path or not os.path.exists(self.video_path):
            return None
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            FreeCAD.Console.PrintWarning("ffmpeg not found, cannot create video thumbnails\n")
            return None
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_file = tmp.name
            cmd = [
                ffmpeg,
                "-loglevel", "error",
                "-y",
                "-i", self.video_path,
                "-frames:v", "1",
                temp_file,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pixmap = QPixmap(temp_file)
            if pixmap.isNull():
                return None
            return pixmap
        except Exception as exc:  # pylint: disable=broad-except
            FreeCAD.Console.PrintWarning(f"Failed to create video thumbnail: {exc}\n")
            return None
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    def _ensure_preview_video(self) -> Optional[str]:
        if not self.video_path or not os.path.exists(self.video_path):
            return None
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None

        original = Path(self.video_path)
        base_dir = original.parent.parent / "generations_video_preview"
        preview_name = f"{original.stem}_preview{original.suffix}"
        preview_path = base_dir / preview_name

        if preview_path.exists():
            return str(preview_path)

        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            width, height = self._video_dimensions
            if width <= 0 or height <= 0:
                width, height = 512, 512
            crop_size = min(width, height)
            crop_filter = "crop=min(iw\\,ih):min(iw\\,ih):(iw-ow)/2:(ih-oh)/2"
            cmd = [
                ffmpeg,
                "-loglevel",
                "error",
                "-y",
                "-i",
                self.video_path,
                "-vf",
                crop_filter,
                str(preview_path),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if preview_path.exists():
                return str(preview_path)
        except Exception as exc:  # pylint: disable=broad-except
            FreeCAD.Console.PrintWarning(f"Failed to generate preview video: {exc}\n")
        return None

    def _create_placeholder_pixmap(self, size: int) -> QPixmap:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, 10, 10)
        painter.fillPath(path, QColor("#2b2b2b"))
        painter.setPen(QPen(QColor("#444444"), 2))
        painter.drawPath(path)
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPointSize(int(size * 0.15))
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "VIDEO")
        painter.end()
        return pixmap

    def resize(self, width):
        self._base_size = width
        if self._has_cpp_player and self.preview_container:
            target_size = (width, width)
            self.preview_container.setFixedSize(*target_size)
            if self.video_widget:
                self.video_widget.setFixedSize(*target_size)
            self.setFixedSize(*target_size)
            self._apply_round_mask(*target_size)
            self._update_vignette(*target_size)
        else:
            self._render_static_preview(width)
        self.update()

    def _render_static_preview(self, width: int):
        if width <= 0:
            return
        source = self.preview_pixmap or self._create_placeholder_pixmap(width)
        scaled = source.scaled(width, width, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - width) // 2)
        square = scaled.copy(x, y, width, width)

        rounded = QPixmap(width, width)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        path = QPainterPath()
        path.addRoundedRect(0, 0, width, width, 10, 10)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, square)
        painter.end()

        if hasattr(self, "label"):
            self.label.setPixmap(rounded)
            self.label.setFixedSize(width, width)
        self.setFixedSize(width, width)

    def _prime_cpp_preview(self):
        if not self.video_widget:
            return
        if hasattr(self.video_widget, "play"):
            try:
                self.video_widget.play()

                def _pause():
                    if hasattr(self.video_widget, "pause"):
                        try:
                            self.video_widget.pause()
                        except Exception:
                            pass

                QTimer.singleShot(60, _pause)
            except Exception:
                pass

    def _apply_round_mask(self, width: int, height: int):
        if not self.preview_container:
            return
        path = QPainterPath()
        path.addRoundedRect(0, 0, width, height, 10, 10)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.preview_container.setMask(region)

    def _update_vignette(self, width: int, height: int):
        if not self.overlay_label:
            return
        vignette = QPixmap(width, height)
        vignette.fill(Qt.GlobalColor.transparent)
        painter = QPainter(vignette)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        gradient = QRadialGradient(width / 2, height / 2, max(width, height) * 0.65)
        gradient.setColorAt(0.55, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 170))
        painter.fillRect(0, 0, width, height, gradient)
        painter.end()
        self.overlay_label.setPixmap(vignette)
        self.overlay_label.setFixedSize(width, height)

    def eventFilter(self, obj, event):
        if obj == self.video_widget or obj == self.overlay_label:
            if event.type() == QEvent.Type.Enter:
                if not self.is_boarding:
                    self._start_preview()
                self.is_boarding = not self.is_boarding
            elif event.type() == QEvent.Type.Leave:
                if not self.is_boarding:
                    self._schedule_preview_stop()
        return super().eventFilter(obj, event)

    def _start_preview(self):
        if not self._has_cpp_player or not self.video_widget:
            return
        self._hovered = True
        if self._hover_leave_timer.isActive():
            self._hover_leave_timer.stop()
        if hasattr(self.video_widget, "play"):
            self.video_widget.play()

    def _schedule_preview_stop(self):
        if not self._has_cpp_player:
            return
        self._hovered = False
        self._hover_leave_timer.stop()
        self._hover_leave_timer.start(80)

    def _stop_preview_immediate(self):
        if not self._has_cpp_player or not self.video_widget:
            return
        if hasattr(self.video_widget, "pause"):
            self.video_widget.pause()
        if hasattr(self.video_widget, "stop"):
            self.video_widget.stop()

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
        horizontal_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        horizontal_layout.setContentsMargins(0, 0, 0, 0)
        horizontal_layout.setSpacing(self.galleryStyle.gap)

        self.v_layouts = []
        for _ in range(self.galleryStyle.number_of_cols):
            v_layout = QVBoxLayout()
            v_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
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
