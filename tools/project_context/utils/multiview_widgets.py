from PySide.QtCore import Qt, Signal
from PySide.QtWidgets import QWidget
from PySide.QtGui import QPainter, QColor, QPixmap, QBrush, QFont
import tools.log as log


class MultiViewCell(QWidget):
    """A minimalistic square cell for displaying selected images in Multi-View generation."""
    
    clicked = Signal(str)  # Emits the view type when clicked
    
    def __init__(self, view_type: str, parent=None):
        super().__init__(parent)
        self.view_type = view_type
        self.image_path: str | None = None
        self.pixmap: QPixmap | None = None
        self._is_selected = False
        
        # Set minimum size to ensure it's square
        self.setMinimumSize(150, 150)
        self.setMaximumSize(300, 300)
    
    def _get_view_description(self):
        """Returns Russian description for each view type."""
        descriptions = {
            "front": "Вид спереди\n+",
            "left": "Вид слева\n+",
            "right": "Вид справа\n+",
            "back": "Вид сзади\n+",
            "other": "Другой ракурс\n+"
        }
        return descriptions.get(self.view_type, self.view_type.upper())
        
    def paintEvent(self, event):
        """Custom paint event to draw the cell."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get cell dimensions
        width = self.width()
        height = self.height()
        size = min(width, height)
        
        # Calculate position to center the square
        x_offset = (width - size) // 2
        y_offset = (height - size) // 2
        
        # Draw background
        if self._is_selected:
            bg_color = QColor(26, 58, 92)  # Selected blue tint
            border_color = QColor(0, 122, 204)  # Blue border
        else:
            bg_color = QColor(42, 42, 42)  # Dark gray
            border_color = QColor(68, 68, 68)  # Gray border
        
        # Fill background
        painter.setBrush(QBrush(bg_color))
        painter.setPen(border_color)
        painter.drawRoundedRect(x_offset, y_offset, size, size, 10, 10)
        
        # Draw image if available
        if self.pixmap:
            # Scale pixmap to fit in the square
            scaled_pixmap = self.pixmap.scaled(
                size - 4, size - 4,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Center the pixmap
            pixmap_x = x_offset + (size - scaled_pixmap.width()) // 2
            pixmap_y = y_offset + (size - scaled_pixmap.height()) // 2
            
            painter.drawPixmap(pixmap_x, pixmap_y, scaled_pixmap)
        
        # Draw semi-transparent text overlay
        if not self._is_selected or not self.pixmap:
            painter.setBrush(QBrush(QColor(0, 0, 0, 128)))  # Semi-transparent black
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x_offset, y_offset, size, size, 10, 10)
            
            # Draw text
            painter.setPen(QColor(255, 255, 255, 180))  # Semi-transparent white
            font = QFont()
            font.setPointSize(int(size / 12))
            font.setBold(True)
            painter.setFont(font)
            
            text = self._get_view_description()
            painter.drawText(x_offset, y_offset, size, size, Qt.AlignmentFlag.AlignCenter, text)
        
        painter.end()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.view_type)
        super().mousePressEvent(event)
    
    def set_image(self, image_path: str):
        """Set the image to display in the cell."""
        self.image_path = image_path
        try:
            self.pixmap = QPixmap(image_path)
            self.update()  # Trigger repaint
        except Exception as e:
            log.error(f"Failed to load image {image_path}: {e}")
            self.pixmap = None
    
    def set_selected(self, selected: bool):
        """Update the visual state when selected."""
        if self._is_selected != selected:
            self._is_selected = selected
            self.update()  # Trigger repaint
    
    def sizeHint(self):
        """Return preferred size for the cell."""
        # Prefer square aspect ratio
        min_side = self.minimumSize().width()
        return self.minimumSize()
