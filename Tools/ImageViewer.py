import FreeCADGui
from PySide.QtCore import Qt, QEvent
from PySide.QtGui import QPixmap, QWheelEvent, QPainter
from PySide.QtWidgets import QWidget, QLabel, QVBoxLayout, QScrollArea, QFileDialog, QPushButton, QHBoxLayout, QDockWidget

from PySide.QtCore import QPoint
from PySide.QtCore import Qt


class ImageViewer(QWidget):
    """Интерактивный просмотр изображений с зумом, как в Google Maps"""

    def __init__(self, path: str, parent=None):
        super(ImageViewer, self).__init__(parent)

        # ✅ QLabel для отображения изображения
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)

        # ✅ Лейаут
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.label)
        
        self.setLayout(self.layout)

        main_window = FreeCADGui.getMainWindow()
        width = int(main_window.width() * 0.3)
        height = int(main_window.height() * 0.7)
        self.setMaximumWidth(width)
        self.setMaximumHeight(height)
        self.setFixedSize(width, height)  # Блокируем изменение размера виджета

        # ✅ Переменные для зума и перемещения
        self.scale_factor = 1
        self.pixmap = QPixmap(path)
        pixmap_width = self.pixmap.size().width()
        pixmap_height = self.pixmap.size().height()
        if pixmap_width >= pixmap_height:
            self.pixmap = self.pixmap.scaled(width, width * pixmap_height / pixmap_width, Qt.KeepAspectRatio)
        else:
            self.pixmap = self.pixmap.scaled(height * pixmap_width / pixmap_height, height, Qt.KeepAspectRatio)
        
        self.label.setPixmap(self.pixmap)
        self.original_pixmap = self.pixmap.copy()  # Сохраняем оригинальное изображение для сброса
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
            cursor_pos = event.position().toPoint()
            center = self.label.rect().center()
            delta_x = (cursor_pos.x() - center.x())*100
            delta_y = (cursor_pos.y() - center.y())*100
            # Сдвиг смещения в зависимости от изменения масштаба
            self.offset = QPoint(
                delta_x * (1 - zoom_factor) + self.offset.x(),
                delta_y * (1 - zoom_factor) + self.offset.y()
            )
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
        if(self.scale_factor > 1):
            pass
        else:
            # ✅ Сброс смещения при масштабе меньше 1
            self.offset = QPoint(0, 0)
        changed_pixmap = self.original_pixmap.scaled(self.original_pixmap.size() * self.scale_factor, Qt.KeepAspectRatio)
        # changed_pixmap = changed_pixmap.copy(self.offset.x(), self.offset.y(), changed_pixmap.width(), changed_pixmap.height())
        
        
        self.label.setPixmap(changed_pixmap)
  

