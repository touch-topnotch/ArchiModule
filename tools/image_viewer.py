import FreeCADGui
from pathlib import Path
from PySide.QtCore import Qt, QEvent
from PySide.QtGui import QPixmap, QWheelEvent, QPainter, QMouseEvent
from PySide.QtWidgets import QWidget
from PySide.QtCore import Qt, QTimer, QPointF, QSize

class ImageViewer(QWidget):
    """
    Просмотрщик изображений с плавным (lerp) управлением.
    • Колёсико — зум к курсору.
    • ЛКМ — панорама.
    • Изображение центрируется в окне, если целиком умещается по оси.
    Минимальный масштаб = 0.5 × вписанный при запуске.
    """

    # ─────────────────────────── init ──────────────────────────────
    def __init__(self, image_path: str | Path, parent: QWidget | None = None):
        super().__init__(parent)

        # ── картинка ----------------------------------------------------
        self._pix_orig = QPixmap(str(image_path))
        if self._pix_orig.isNull():
            raise ValueError(f"Не удалось загрузить изображение: {image_path}")

        # ── параметры масштаба/позиции ---------------------------------
        self._base_scale   = 1.0           # пересчитается в resizeEvent
        self._scale        = 1.0
        self._target_scale = 1.0
        self._offset       = QPointF(0, 0)
        self._target_off   = QPointF(0, 0)

        # кеш масштабированного изображения
        self._scaled = self._pix_orig

        # drag
        self._last_mouse = QPointF()

        # плавность
        self._lerp_speed = 0.18
        self._timer = QTimer(self, timeout=self._tick)
        self._timer.start(16)             # ≈ 60 FPS

        # фон = системный
        self.setAutoFillBackground(True)
        
        self.setMinimumSize(100, self._scaled.height())
        

    # ───────────────────── геометрия и центрирование ──────────────────
    def _fit_scale(self) -> float:
        "Вписываем оригинал в текущее окно, сохраняем пропорции."
        if self.width() == 0 or self.height() == 0:
            return 1.0
        return min(self.width() / self._pix_orig.width(),
                   self.height() / self._pix_orig.height(),
                   1.0)

    def _clamp_target_offset(self) -> None:
        """
        Ограничить / центрировать _target_off так, чтобы:
        • картинка не вышла за границу, если она больше окна;
        • картинка была по центру, если она меньше окна по данной оси.
        """
        pw, ph = self._pix_orig.width() * self._target_scale, \
                 self._pix_orig.height() * self._target_scale
        cw, ch = self.width(), self.height()

        # по X
        if pw <= cw:                                     # картинка уже окна
            self._target_off.setX((cw - pw) * 0.5)       # центр
        else:
            min_x = cw - pw
            self._target_off.setX(max(min_x, min(self._target_off.x(), 0)))

        # по Y
        if ph <= ch:
            self._target_off.setY((ch - ph) * 0.5)
        else:
            min_y = ch - ph
            self._target_off.setY(max(min_y, min(self._target_off.y(), 0)))

    # ────────────────────────── события ──────────────────────────────
    def wheelEvent(self, ev: QWheelEvent) -> None:
        if ev.angleDelta().y() == 0:
            return
        factor = 1.03 if ev.angleDelta().y() > 0 else 0.8
        new_tscale = self._target_scale * factor

        min_scale = self._base_scale * 0.9
        max_scale = self._base_scale * 10
        if not (min_scale <= new_tscale <= max_scale):
            return

        cursor = ev.position()
        self._target_off = self._target_off - (cursor - self._target_off) * (factor - 1)
        self._target_scale = new_tscale
        self._clamp_target_offset()

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._last_mouse = ev.position()

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        if ev.buttons() & Qt.MouseButton.LeftButton:
            delta = ev.position() - self._last_mouse
            self._target_off += delta
            self._last_mouse = ev.position()
            self._clamp_target_offset()

    def resizeEvent(self, _) -> None:
        "Обновить базовый масштаб и центрировать."
        old_base = self._base_scale
        self._base_scale = self._fit_scale()
        if old_base:
            coef = self._base_scale / old_base
            self._scale        *= coef
            self._target_scale *= coef
        self._update_scaled()
        self._clamp_target_offset()

    # ───────────────────── анимация (lerp) ───────────────────────────
    def _lerp(self, a: float, b: float) -> float:
        return a + (b - a) * self._lerp_speed

    def _tick(self) -> None:
        # масштаб
        if abs(self._scale - self._target_scale) > 1e-4:
            self._scale = self._lerp(self._scale, self._target_scale)
            self._update_scaled()
        # позиция
        if (self._offset - self._target_off).manhattanLength() > 0.5:
            self._offset.setX(self._lerp(self._offset.x(), self._target_off.x()))
            self._offset.setY(self._lerp(self._offset.y(), self._target_off.y()))
        self.update()

    # ─────────────────── обновление масштабированного PM ─────────────
    def _update_scaled(self) -> None:
        size = self._pix_orig.size() * self._scale
        self._scaled = self._pix_orig.scaled(
            size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # изменение размера могло поменять центрирование
        self._clamp_target_offset()

    # ───────────────────────── paintEvent ────────────────────────────
    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), self.palette().window())
        p.drawPixmap(self._offset, self._scaled)

# import FreeCADGui
# from tools.full_view import FullViewWindowData
# mv = FreeCADGui.getMainWindow()
# dock = FullViewWindow()
# mv.addDockWidget(Qt.LeftDockWidgetArea, dock)
# mv.show()
# full_view_image_interactable = ImageViewer("/Users/dmitry057/Pictures/the-game-location-that-looks-like-neural-connections-.png")
# fd = FullViewWindowData(
#     interactable=full_view_image_interactable,
#     buttons = [
#     ]
# )
# dock.show(fd)