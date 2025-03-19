from PySide2.Qt3DCore import (Qt3DCore)
from PySide2.Qt3DExtras import (Qt3DExtras)
from PySide2.Qt3DRender import (Qt3DRender)
from PySide2.QtCore import (Property, QObject, QPropertyAnimation, Signal, QUrl)
from PySide2.QtGui import (QMatrix4x4)
from PySide2.QtGui import QVector3D, QColor
from pydantic import BaseModel, ConfigDict
from Tools import Models


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
        self._radius = 1
        self._angle = 0

    def setTarget(self, t):
        self._target = t

    def getTarget(self):
        return self._target

    def setRadius(self, radius):
        if self._radius != radius:
            self._radius = radius
            self.updateMatrix()
            self.radiusChanged.emit()

    def getRadius(self):
        return self._radius

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
        self._matrix.translate(self._radius, 0, 0)
        if self._target is not None:
            self._target.setMatrix(self._matrix)

    angleChanged = Signal()
    radiusChanged = Signal()
    angle = Property(float, getAngle, setAngle, notify=angleChanged)
    radius = Property(float, getRadius, setRadius, notify=radiusChanged)

class View3DWindow(Qt3DExtras.Qt3DWindow):
    data: Models.Gen3dResult
    
    def __init__(self, data:Models.Gen3dResult, view_3d_style: View3DStyle = None, parent=None):
        super(View3DWindow, self).__init__(parent)
        
        self.data = data
        if(view_3d_style is None):
            view_3d_style = View3DStyle()
        self.view_3d_style = view_3d_style

        # ✅ Set up Frame Graph
        self.frameGraph = self.activeFrameGraph()

        self.frameGraph.setClearColor(self.view_3d_style.background_color)
        self.create_scene(data)
        
    def create_scene(self, data: Models.Gen3dResult):
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

  

        self.objMaterial = Qt3DExtras.QDiffuseSpecularMaterial(self.rootEntity)
        self.objMaterial.setDiffuse(QVector3D(1.0,  1, 1))  # Orange color (change as needed)
        self.objMaterial.setShininess(1)  # Adjust shininess as needed
        self.objMaterial.setSpecular(QVector3D(0.9, 0.9, 0.9))  # Adjust specular as needed
        

        
        # ✅ Load Texture (if .mat file contains a texture)
        self.alphaTexture = Qt3DRender.QTexture2D()
        self.alphaTextureImage = Qt3DRender.QTextureImage()
        self.alphaTextureImage.setSource(QUrl.fromLocalFile(self.data.texture.base_color_url))  # ✅ Replace with actual texture path
        self.alphaTexture.setFormat(Qt3DRender.QAbstractTexture.RGBA8_UNorm)
        self.alphaTexture.addTextureImage(self.alphaTextureImage)
        self.objMaterial.setDiffuse(self.alphaTexture)
        self.objMaterial.setShininess(0.0)


        # self.normalTexture = Qt3DRender.QTexture2D()
        # self.normalTextureImage = Qt3DRender.QTextureImage()
        # self.normalTextureImage.setSource(QUrl.fromLocalFile(self.data.texture.normal_url))  # ✅ Replace with actual texture path
        # self.normalTexture.setFormat(Qt3DRender.QAbstractTexture.RGBA8_UNorm)
        # self.normalTexture.addTextureImage(self.normalTextureImage)
        # self.objMaterial.setNormal(self.normalTexture)
        
        # self.roughnessTexture = Qt3DRender.QTexture2D()
        # self.roughnessTextureImage = Qt3DRender.QTextureImage()
        # self.roughnessTextureImage.setSource(QUrl.fromLocalFile(self.data.texture.roughness_url))  # ✅ Replace with actual texture path
        # self.roughnessTexture.setFormat(Qt3DRender.QAbstractTexture.RGBA8_UNorm)
        # self.roughnessTexture.addTextureImage(self.roughnessTextureImage)
        # self.objMaterial.setRoughness(self.roughnessTexture)
        
        # self.metallicTexture = Qt3DRender.QTexture2D()
        # self.metallicTextureImage = Qt3DRender.QTextureImage()
        # self.metallicTextureImage.setSource(QUrl.fromLocalFile(self.data.texture.metallic_url))  # ✅ Replace with actual texture path
        # self.metallicTexture.setFormat(Qt3DRender.QAbstractTexture.RGBA8_UNorm)
        # self.metallicTexture.addTextureImage(self.metallicTextureImage)
        # self.objMaterial.setMetallic(self.metallicTexture)

        # Attach components to entity
        self.objEntity.addComponent(self.objMesh)
        self.objEntity.addComponent(self.objMaterial)
        self.objEntity.addComponent(self.objTransform)
        
         # Attach components to entity
        self.controller = OrbitTransformController(self.objTransform)
        self.controller.setTarget(self.objTransform)
        self.controller.setRadius(0)

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
