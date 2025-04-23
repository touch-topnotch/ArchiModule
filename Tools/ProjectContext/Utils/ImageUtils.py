                    
import numpy as np
from PySide.QtGui import QImage, QPixmap, QPainter, QGraphicsScene, QGraphicsPixmapItem, QGraphicsBlurEffect
from PySide.QtCore import Qt

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

