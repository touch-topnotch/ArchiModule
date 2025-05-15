from PySide.Qt3DCore import (Qt3DCore)
from PySide.Qt3DExtras import (Qt3DExtras)
from PySide.Qt3DRender import (Qt3DRender)
from PySide.QtCore import (Property, QObject, QPropertyAnimation, Signal, QUrl)
from PySide.QtGui import (QMatrix4x4)
from PySide.QtGui import QVector3D, QColor
from pydantic import BaseModel, ConfigDict
from tools.models import Gen3dResult, Gen3dSaved

class View3DStyle(BaseModel):
    model_scale: float = 100
    model_position: QVector3D = QVector3D(0, 0, 0)
    should_rotate: bool = True
    rotation_speed: int = 10000
    light_intensity: int = 1
    light_color: QColor = QColor.fromRgbF(1.0, 1.0, 0.7)
    light_direction: QVector3D = QVector3D(0, 0, 0)
    camera_position: QVector3D = QVector3D(0, 15, 40)
    camera_view_center: QVector3D = QVector3D(0, 0, 0)
    camera_fov: int = 45
    camera_aspect_ratio: float = 16 / 9
    camera_near_plane: float = 0.1
    camera_far_plane: float = 1000
    camera_linear_speed: int = 50
    camera_look_speed: int = 180
    background_color: QColor = QColor(140, 140, 140)
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
class OrbitTransformController(QObject):
    def __init__(self, parent):
        super(OrbitTransformController, self).__init__(parent)
        self._target = None
        self._matrix = QMatrix4x4()
        self._angle = 0

    def setTarget(self, t):
        self._target = t

    def getTarget(self):
        return self._target

    def setAngle(self, angle):
        if self._angle != angle:
            self._angle = angle
            self.updateMatrix()
            self.angleChanged.emit()

    def getAngle(self):
        return self._angle

    def updateMatrix(self):
        self._matrix.setToIdentity()
        self._matrix.rotate(self._angle, QVector3D(0, 1, 0))
        if self._target is not None:
            self._target.setMatrix(self._matrix)

    angleChanged = Signal()
    angle = Property(float, getAngle, setAngle, notify=angleChanged)

class View3DWindow(Qt3DExtras.Qt3DWindow):
    data: Gen3dResult
    
    def __init__(self, data:Gen3dResult, view_3d_style: View3DStyle = None, parent=None):
        super(View3DWindow, self).__init__(parent)
        
        self.data = data
        if(view_3d_style is None):
            view_3d_style = View3DStyle()
        self.view_3d_style = view_3d_style

        # ✅ Set up Frame Graph
        self.frameGraph = self.activeFrameGraph()

        self.frameGraph.setClearColor(self.view_3d_style.background_color)
        self.create_scene(self.data)
         
    def create_scene(self, data: Gen3dResult):
        # Create Root Entity
        self.rootEntity = Qt3DCore.QEntity()

        # Камера
        self.camera().lens().setPerspectiveProjection(self.view_3d_style.camera_fov, self.view_3d_style.camera_aspect_ratio, self.view_3d_style.camera_near_plane, self.view_3d_style.camera_far_plane)
        self.camera().setPosition(self.view_3d_style.camera_position)
        self.camera().setViewCenter(self.view_3d_style.camera_view_center)

        # Add mouse interaction for rotation
        self.mouseController = Qt3DExtras.QOrbitCameraController(self.rootEntity)
        self.mouseController.setCamera(self.camera())
        self.mouseController.setLinearSpeed(self.view_3d_style.camera_linear_speed)
        self.mouseController.setLookSpeed(self.view_3d_style.camera_look_speed)
        self.mouseController.setAcceleration(10.0)
        self.mouseController.setDeceleration(1.0)
        self.mouseController.setZoomInLimit(1.0)
        
        # Освещение
        lightEntity = Qt3DCore.QEntity(self.rootEntity)
        light = Qt3DRender.QDirectionalLight(lightEntity)
        light.setWorldDirection(self.view_3d_style.light_direction)
        light.setColor(self.view_3d_style.light_color)
        light.setIntensity(self.view_3d_style.light_intensity)
        lightEntity.addComponent(light)

        lightTransform = Qt3DCore.QTransform(lightEntity)
        lightEntity.addComponent(lightTransform)

        # Устанавливаем корневую сущность в 3D-окно
        self.setRootEntity(self.rootEntity)

        # home
        # ✅ Load .obj Model
        self.objEntity = Qt3DCore.QEntity(self.rootEntity)
        self.objMesh = Qt3DRender.QMesh()
        self.objMesh.setSource(QUrl.fromLocalFile(data.object.obj_url))
        self.objTransform = Qt3DCore.QTransform()
        self.objTransform.setScale3D(QVector3D(self.view_3d_style.model_scale, self.view_3d_style.model_scale, self.view_3d_style.model_scale))  # Adjust the scale if needed
        self.objTransform.setTranslation(self.view_3d_style.model_position)  # Adjust the position if needed
    
        # Material
        self.objMaterial = Qt3DExtras.QDiffuseSpecularMapMaterial(self.rootEntity)

        # Diffuse texture (base color)
        diffuse = Qt3DRender.QTextureLoader(self.objMaterial)
        diffuse.setSource(QUrl.fromLocalFile(data.texture.base_color_url))
        specular = Qt3DRender.QTextureLoader(self.objMaterial)
        specular.setSource(QUrl.fromLocalFile(data.texture.roughness_url))
        self.objMaterial.setDiffuse(diffuse)
        self.objMaterial.setSpecular(specular)
        # Shininess (scalar value)
        self.objMaterial.setShininess(0.0)  # 0 = dull, 128 = very shiny

        # # Load and set the normal texture
        # normal_texture = Qt3DRender.QTextureLoader(self.objMaterial)
        # normal_texture.setSource(QUrl.fromLocalFile(self.data.texture.normal_url))
        # self.objMaterial.setNormal(normal_texture)

        # # Load and set the roughness texture
        # roughness_texture = Qt3DRender.QTextureLoader(self.objMaterial)
        # roughness_texture.setSource(QUrl.fromLocalFile(self.data.texture.roughness_url))
        # self.objMaterial.setRoughness(roughness_texture)

        # # Load and set the metallic texture
        # metallic_texture = Qt3DRender.QTextureLoader(self.objMaterial)
        # metallic_texture.setSource(QUrl.fromLocalFile(self.data.texture.metallic_url))
        # self.objMaterial.setMetalness(metallic_texture)
        

        
        # Attach components to entity
        self.objEntity.addComponent(self.objMesh)
        self.objEntity.addComponent(self.objMaterial)
        self.objEntity.addComponent(self.objTransform)
        
        # Attach components to entity
        self.controller = OrbitTransformController(self.objTransform)
        self.controller.setTarget(self.objTransform)
        
        if(self.view_3d_style.should_rotate):
            self.objRotateTransformAnimation = QPropertyAnimation(self.objTransform)
            self.objRotateTransformAnimation.setTargetObject(self.controller)
            self.objRotateTransformAnimation.setPropertyName(b"angle")
            self.objRotateTransformAnimation.setStartValue(0)
            self.objRotateTransformAnimation.setEndValue(360)
            self.objRotateTransformAnimation.setDuration(self.view_3d_style.rotation_speed)
            self.objRotateTransformAnimation.setLoopCount(-1)
            self.objRotateTransformAnimation.start()
            
    def close(self):
        self.objRotateTransformAnimation.stop()
        self.objRotateTransformAnimation.deleteLater()
        self.controller.deleteLater()
        self.objMaterial.deleteLater()
        self.objTransform.deleteLater()
        self.objMesh.deleteLater()
        self.objEntity.deleteLater()
        self.camController.deleteLater()
        self.rootEntity.deleteLater()
        self.deleteLater()
        super().close()