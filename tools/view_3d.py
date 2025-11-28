from __future__ import annotations

"""3‑D viewer – *compatibility patch*

PySide 6 distributions differ in which symbols are re‑exported at the top level of each module.  In some builds
`Qt3DExtras.Qt3DWindow` is **not** present, while the class is still importable directly:

```python
from PySide6.Qt3DExtras import Qt3DWindow  # ✅ always available
```

This revision therefore:

* **imports `Qt3DWindow` explicitly** and subclasses it; we no longer access it as an attribute of the module.
* Keeps every other fix from the previous round (object-centric rotation, XZ grid).
"""

from pathlib import Path

from PySide.Qt3DCore import Qt3DCore
from PySide.Qt3DExtras import Qt3DExtras
from PySide.Qt3DRender import Qt3DRender  # type: ignore

from PySide.QtCore import (  # type: ignore
    Property,
    QObject,
    QPropertyAnimation,
    QUrl,
    Signal,
    QSize,
    QByteArray,
    Qt,
    QBuffer,
    QTimer,
)
import struct
from PySide.QtGui import (  # type: ignore
    QColor,
    QMatrix4x4,
    QQuaternion,
    QVector3D,
)
from pydantic import BaseModel, ConfigDict

# -----------------------------------------------------------------------------
# 1. User‑tweakable style / behaviour
# -----------------------------------------------------------------------------


class View3DStyle(BaseModel):
    """Tunables for the viewer at run time."""

    model_scale: float = 100.0
    model_position: QVector3D = QVector3D(0.0, 0.0, 0.0)
    should_rotate: bool = True
    rotation_speed: int = 10_000  # ms per revolution

    light_intensity: float = 1
    light_color: QColor = QColor.fromRgbF(1.0, 1.0, 1.0)
    light_direction: QVector3D = QVector3D(-1.0, -1.0, -1.0)

    camera_position: QVector3D = QVector3D(0.0, 1.0, 3.0)
    camera_view_center: QVector3D = QVector3D(0.0, 0.0, 0.0)
    camera_fov: int = 45
    camera_aspect_ratio: float = 16 / 9
    camera_near_plane: float = 0.1
    camera_far_plane: float = 1_000.0

    background_color: QColor = QColor(60, 60, 60)

    # grid
    grid_size: float = 50.0
    grid_divisions: int = 200
    grid_color: QColor = QColor(80, 80, 80)  # Bright white for better visibility

    model_config = ConfigDict(arbitrary_types_allowed=True)


# --- Pydantic forward‑ref patch ---------------------------------------------
# With ``from __future__ import annotations`` all type hints are strings.  Pydantic
# v2 therefore needs an explicit rebuild to resolve the Qt classes (QVector3D,
# QColor, …) that were forward‑referenced in the annotations.  Calling
# ``model_rebuild`` once right after the class definition fixes the error:
# "`View3DStyle` is not fully defined".

View3DStyle.model_rebuild()


# -----------------------------------------------------------------------------
# 2. Controller that rotates *the model*
# -----------------------------------------------------------------------------


class OrbitTransformController(QObject):
    """Rotates a target `QTransform` around the X and Y axes."""

    angleChanged = Signal()

    def __init__(self, target: Qt3DCore.QTransform | None = None):  # type: ignore[name-defined]
        super().__init__()
        self._target = target
        self._matrix = QMatrix4x4()
        self._angle_x: float = 0.0
        self._angle_y: float = 0.0
        self._target_angle_x: float = 0.0
        self._target_angle_y: float = 0.0
        self._lerp_factor: float = 0.1  # Adjust this value to control smoothness (0.1 = very smooth, 1.0 = instant)
        
        # Setup animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_rotation)
        self._timer.start(16)  # ~60 FPS
        
        self.update_matrix()

    def _update_rotation(self):
        # Smoothly interpolate current angles towards target angles
        if abs(self._angle_x - self._target_angle_x) > 0.001 or abs(self._angle_y - self._target_angle_y) > 0.001:
            self._angle_x = self._lerp(self._angle_x, self._target_angle_x, self._lerp_factor)
            self._angle_y = self._lerp(self._angle_y, self._target_angle_y, self._lerp_factor)
            self.update_matrix()
            self.angleChanged.emit()

    def _lerp(self, start: float, end: float, factor: float) -> float:
        return start + (end - start) * factor

    def setTargetAngleX(self, angle: float):
        self._target_angle_x = angle

    def setTargetAngleY(self, angle: float):
        self._target_angle_y = angle

    def getAngleX(self):
        return self._angle_x

    def getAngleY(self):
        return self._angle_y

    angle_x = Property(float, getAngleX)
    angle_y = Property(float, getAngleY)

    def update_matrix(self):
        self._matrix.setToIdentity()
        # Apply rotations in sequence - first Y (horizontal) then X (vertical)
        self._matrix.rotate(self._angle_y, QVector3D(0.0, 1.0, 0.0))
        self._matrix.rotate(self._angle_x, QVector3D(1.0, 0.0, 0.0))
        if self._target is not None:
            self._target.setMatrix(self._matrix)


# -----------------------------------------------------------------------------
# 3. Main window – now subclasses *Qt3DWindow* directly
# -----------------------------------------------------------------------------


class View3DWindow(Qt3DExtras.Qt3DWindow):
    """Lightweight Qt3D preview – object‑centric controls, grid helper."""

    def __init__(self, data, view_style: View3DStyle | None = None, parent=None):  # type: ignore[annotation-unreachable]
        super().__init__(parent)

        # data / style ----------------------------------------------------
        self.data = data
        self.style = view_style or View3DStyle()

        self.defaultFrameGraph().setClearColor(self.style.background_color)
        self.setTitle("3D Preview")
        
        # Create independent frame graph to prevent lighting conflicts between windows
        # This ensures each window maintains its own lighting state
        self._setupIndependentFrameGraph()

        # camera ----------------------------------------------------------
        cam = self.camera()
        cam.lens().setPerspectiveProjection(
            self.style.camera_fov,
            self.style.camera_aspect_ratio,
            self.style.camera_near_plane,
            self.style.camera_far_plane,
        )
        cam.setPosition(self.style.camera_position)
        cam.setViewCenter(self.style.camera_view_center)

        # root entity -----------------------------------------------------
        self.root = Qt3DCore.QEntity()  # type: ignore[name-defined]
        self.setRootEntity(self.root)

        # lighting --------------------------------------------------------
        # Create independent lighting for this window to prevent conflicts with other windows
        self.light_ent = Qt3DCore.QEntity(self.root)  # type: ignore[name-defined]
        self.light = Qt3DRender.QDirectionalLight(self.light_ent)  
        self.light.setWorldDirection(self.style.light_direction)
        self.light.setColor(self.style.light_color)
        self.light.setIntensity(self.style.light_intensity)
        
        # Ensure light stays active across multiple windows by setting it as enabled explicitly
        # This prevents the light from being disabled when new 3D windows are opened
        self.light.setEnabled(True)
        
        # Store reference to prevent garbage collection and maintain independent lighting
        self.light_ent.addComponent(self.light)

        # helpers ---------------------------------------------------------
        self._create_grid()

        # model -----------------------------------------------------------
        self.model_transform = Qt3DCore.QTransform()  # type: ignore[name-defined]
        self.model_transform.setScale3D(QVector3D(self.style.model_scale, self.style.model_scale, self.style.model_scale))
        self.model_transform.setTranslation(self.style.model_position)

        # Определяем формат файла и выбираем подходящий URL
        # GLB файлы содержат встроенные текстуры, OBJ требуют внешние текстуры
        model_file_path = self._get_model_file_path()
        self.model_file_format = self._detect_file_format(model_file_path)

        self.model_mesh = Qt3DRender.QMesh()  # type: ignore[attr-defined]
        self.model_mesh.setSource(QUrl.fromLocalFile(str(Path(model_file_path))))

        # Создаем материал в зависимости от формата файла
        self.model_material = self._create_material()

        self.model_entity = Qt3DCore.QEntity(self.root)  # type: ignore[name-defined]
        self.model_entity.addComponent(self.model_mesh)
        self.model_entity.addComponent(self.model_material)
        self.model_entity.addComponent(self.model_transform)

        # rotation controller --------------------------------------------
        self.controller = OrbitTransformController(self.model_transform)
        # if self.style.should_rotate:
        #     self._autorotate()

        # interaction -----------------------------------------------------
        self._drag_active = False
        self._last_pos = None  # type: ignore[assignment]

    # ── mouse events ─────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._last_pos = event.position()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_active and self._last_pos is not None:
            dx = event.position().x() - self._last_pos.x()
            dy = event.position().y() - self._last_pos.y()
            
            # Update target angles with increased force
            self.controller.setTargetAngleX(self.controller.getAngleX() + dy * 1.5)  # Increased from 0.5
            self.controller.setTargetAngleY(self.controller.getAngleY() + dx * 1.5)  # Increased from 0.5
            
            self._last_pos = event.position()
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = False
            event.accept()
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        # Zoom in/out with mouse wheel
        current_pos = self.camera().position()
        zoom_factor = 1.0 + (event.angleDelta().y() * 0.001)
        new_pos = current_pos * zoom_factor
        self.camera().setPosition(new_pos)
        event.accept()
        super().wheelEvent(event)

    # ── helpers ──────────────────────────────────────────────────────────

    def _setupIndependentFrameGraph(self):
        """Setup an independent frame graph to prevent lighting conflicts between multiple windows."""
        try:
            # Create a new frame graph root to isolate this window's rendering
            from PySide.Qt3DRender import Qt3DRender  # type: ignore
            
            frame_graph = Qt3DRender.QRenderSurfaceSelector()  # type: ignore[attr-defined]
            frame_graph.setSurface(self)
            
            # Create viewport
            viewport = Qt3DRender.QViewport(frame_graph)  # type: ignore[attr-defined]
            viewport.setNormalizedRect(Qt3DCore.QRectF(0.0, 0.0, 1.0, 1.0))  # type: ignore[name-defined]
            
            # Create camera selector
            camera_selector = Qt3DRender.QCameraSelector(viewport)  # type: ignore[attr-defined]
            camera_selector.setCamera(self.camera())
            
            # Create clear buffer
            clear_buffer = Qt3DRender.QClearBuffers(camera_selector)  # type: ignore[attr-defined]
            clear_buffer.setBuffers(Qt3DRender.QClearBuffers.ColorDepthBuffer)  # type: ignore[attr-defined]
            clear_buffer.setClearColor(self.style.background_color)
            
            # Set the custom frame graph
            self.setActiveFrameGraph(frame_graph)
            
        except (ImportError, AttributeError):
            # Fallback if frame graph setup fails - just use default
            pass

    def _get_model_file_path(self) -> str:
        """Определяет путь к файлу модели, предпочитая OBJ (т.к. GLB не поддерживается Qt3D)."""
        # Предпочитаем OBJ, так как GLB не поддерживается Qt3D на macOS
        if self.data.object.obj_url and Path(self.data.object.obj_url).exists():
            return self.data.object.obj_url
        elif self.data.object.fbx_url and Path(self.data.object.fbx_url).exists():
            return self.data.object.fbx_url
        elif self.data.object.glb_url and Path(self.data.object.glb_url).exists():
            return self.data.object.glb_url
        else:
            # Fallback к obj_url даже если файл не существует (для обработки ошибок)
            return self.data.object.obj_url or self.data.object.glb_url or ""
    
    def _detect_file_format(self, file_path: str) -> str:
        """Определяет формат файла по расширению."""
        if not file_path:
            return "unknown"
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext == ".glb":
            return "glb"
        elif ext == ".obj":
            return "obj"
        elif ext == ".fbx":
            return "fbx"
        elif ext == ".usdz":
            return "usdz"
        else:
            return "unknown"
    
    def _create_material(self):
        """Создает материал в зависимости от формата файла."""
        # GLB файлы содержат встроенные текстуры, поэтому используем простой материал
        if self.model_file_format == "glb":
            # Для GLB используем простой материал - текстуры уже встроены в файл
            material = Qt3DExtras.QPhongMaterial(self.root)
            material.setAmbient(QColor(200, 200, 200))
            material.setDiffuse(QColor(255, 255, 255))
            material.setShininess(0.0)
            return material
        
        # Для OBJ и других форматов ищем внешние текстуры
        base_color_path = None
        roughness_path = None
        
        # 1. Проверяем текстуры из данных модели
        if self.data.texture:
            if self.data.texture.base_color_url:
                base_color_path = Path(self.data.texture.base_color_url)
            if self.data.texture.roughness_url:
                roughness_path = Path(self.data.texture.roughness_url)
        
        # 2. Если текстуры не указаны, ищем base_color_texture.png в папке модели
        # (это стандартное имя после распаковки ZIP архива)
        if not base_color_path or not base_color_path.exists():
            model_path = self._get_model_file_path()
            if model_path:
                model_folder = Path(model_path).parent
                # Пробуем найти текстуру по стандартным именам
                possible_textures = [
                    model_folder / "base_color_texture.png",  # После распаковки ZIP
                    model_folder / "material_0.png",  # Оригинальное имя из ZIP
                    model_folder / "texture.png",
                    model_folder / "diffuse.png",
                ]
                for tex_path in possible_textures:
                    if tex_path.exists():
                        base_color_path = tex_path
                        break
        
        # Если текстуры всё ещё нет, используем простой материал
        if not base_color_path or not base_color_path.exists():
            material = Qt3DExtras.QPhongMaterial(self.root)
            material.setAmbient(QColor(200, 200, 200))
            material.setDiffuse(QColor(255, 255, 255))
            material.setShininess(0.0)
            return material
        
        # Создаем материал с текстурами
        material = Qt3DExtras.QDiffuseSpecularMapMaterial(self.root)
        
        # Загружаем диффузную текстуру (base color)
        diffuse_tex = Qt3DRender.QTextureLoader(material)  # type: ignore[attr-defined]
        diffuse_tex.setSource(QUrl.fromLocalFile(str(base_color_path)))
        material.setDiffuse(diffuse_tex)
        
        # Загружаем specular текстуру (roughness), если доступна
        # Если нет отдельной specular текстуры - используем base_color чтобы избежать предупреждения Qt3D
        if roughness_path and roughness_path.exists():
            specular_tex = Qt3DRender.QTextureLoader(material)  # type: ignore[attr-defined]
            specular_tex.setSource(QUrl.fromLocalFile(str(roughness_path)))
            material.setSpecular(specular_tex)
        else:
            # Используем base_color как specular чтобы избежать "specularTexture wasn't set"
            specular_tex = Qt3DRender.QTextureLoader(material)  # type: ignore[attr-defined]
            specular_tex.setSource(QUrl.fromLocalFile(str(base_color_path)))
            material.setSpecular(specular_tex)
        
        material.setShininess(0.0)
        return material

    def _create_grid(self):
        grid_ent = Qt3DCore.QEntity(self.root)

        # ------------------------------------------------------------------ vertices
        divs  = max(1, self.style.grid_divisions)
        half  = self.style.grid_size / 2.0
        step  = self.style.grid_size / divs

        verts = []
        for i in range(divs + 1):                    # X-direction lines
            z = -half + i * step
            verts.extend([-half, -0.2, z,  half, -0.2, z])
        for i in range(divs + 1):                    # Z-direction lines
            x = -half + i * step
            verts.extend([x, -0.2, -half, x, -0.2, half])

        # one normal per vertex, constant (0,1,0)
        norms = [0.0, 1.0, 0.0] * (len(verts) // 3)

        # ------------------------------------------------------------------ geometry
        geometry = Qt3DCore.QGeometry(grid_ent)

        # position buffer + attribute
        pos_buf = Qt3DCore.QBuffer(geometry)
        pos_buf.setData(QByteArray(struct.pack(f"{len(verts)}f", *verts)))

        pos_attr = Qt3DCore.QAttribute(geometry)
        pos_attr.setName(Qt3DCore.QAttribute.defaultPositionAttributeName())
        pos_attr.setVertexBaseType(Qt3DCore.QAttribute.VertexBaseType.Float)
        pos_attr.setVertexSize(3)
        pos_attr.setAttributeType(Qt3DCore.QAttribute.AttributeType.VertexAttribute)
        pos_attr.setBuffer(pos_buf)
        pos_attr.setByteStride(12)
        pos_attr.setCount(len(verts) // 3)
        geometry.addAttribute(pos_attr)

        # normal buffer + attribute  (dummy data!)
        nrm_buf = Qt3DCore.QBuffer(geometry)
        nrm_buf.setData(QByteArray(struct.pack(f"{len(norms)}f", *norms)))

        nrm_attr = Qt3DCore.QAttribute(geometry)
        nrm_attr.setName(Qt3DCore.QAttribute.defaultNormalAttributeName())  # "vertexNormal"
        nrm_attr.setVertexBaseType(Qt3DCore.QAttribute.VertexBaseType.Float)
        nrm_attr.setVertexSize(3)
        nrm_attr.setAttributeType(Qt3DCore.QAttribute.AttributeType.VertexAttribute)
        nrm_attr.setBuffer(nrm_buf)
        nrm_attr.setByteStride(12)
        nrm_attr.setCount(len(verts) // 3)
        geometry.addAttribute(nrm_attr)

        # ------------------------------------------------------------------ renderer
        renderer = Qt3DRender.QGeometryRenderer(grid_ent)
        renderer.setGeometry(geometry)
        renderer.setPrimitiveType(Qt3DRender.QGeometryRenderer.PrimitiveType.Lines)
        renderer.setVertexCount(len(verts) // 3)

        # ------------------------------------------------------------------ material
        material = Qt3DExtras.QDiffuseSpecularMaterial(grid_ent)
        material.setAmbient(self.style.grid_color)   # flat colour
        material.setDiffuse(self.style.grid_color)
        material.setShininess(0.0)

        # ------------------------------------------------------------------ entity
        grid_ent.addComponent(renderer)
        grid_ent.addComponent(material)

        xform = Qt3DCore.QTransform()
        xform.setTranslation(QVector3D(0.0, 0.1, 0.0))   # lift to avoid z-fight
        grid_ent.addComponent(xform)
    def _autorotate(self):
        self._anim = QPropertyAnimation(self.controller, b"angle", self)  # noqa: attribute-defined-outside-init
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(360.0)
        self._anim.setDuration(self.style.rotation_speed)
        self._anim.setLoopCount(-1)
        self._anim.start()

    # ── cleanup ─────────────────────────────────────────────────────────

    def ensureLightEnabled(self):
        """Ensure the directional light remains enabled - call this if light gets disabled."""
        if hasattr(self, 'light') and self.light:
            self.light.setEnabled(True)
    
    def closeEvent(self, event):  # noqa: D401 – Qt naming convention
        if hasattr(self, "_anim"):
            self._anim.stop()
            self._anim.deleteLater()
        
        # Clean up lighting components
        if hasattr(self, 'light'):
            self.light.deleteLater()
        if hasattr(self, 'light_ent'):
            self.light_ent.deleteLater()
            
        self.controller.deleteLater()
        super().closeEvent(event)
