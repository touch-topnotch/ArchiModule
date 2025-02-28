from PySide2.Qt3DCore import (Qt3DCore)
from PySide2.Qt3DExtras import (Qt3DExtras)
from PySide2.Qt3DRender import (Qt3DRender)
from PySide2.QtCore import (Property, QObject, QPropertyAnimation, Signal, QUrl)
from PySide2.QtGui import (QMatrix4x4)
from PySide2.QtGui import QVector3D, QColor
from pydantic import BaseModel, ConfigDict

class View3DData(BaseModel):
    obj_path: QUrl|str
    texture_diffuse_path: QUrl|str=None
    texture_normal_path: QUrl|str=None
    texture_specular_path: QUrl|str=None
    scale: QVector3D = QVector3D(1, 1, 1)
    position: QVector3D = QVector3D(0, 0, 0)
    rotation: QVector3D = QVector3D(0, 0, 0)
    
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

    def __init__(self, data:View3DData, parent=None):
        super(View3DWindow, self).__init__(parent)
        
        self.data = data

        # ✅ Set up Frame Graph
        self.frameGraph = self.activeFrameGraph()

        self.frameGraph.setClearColor(QColor(20, 20, 20))
        self.create_scene(data)
        
    def create_scene(self, data: View3DData):
        # Create Root Entity
        self.rootEntity = Qt3DCore.QEntity()

        # Камера
        self.camera().lens().setPerspectiveProjection(45, 16 / 9, 0.1, 1000)
        self.camera().setPosition(QVector3D(0, 15, 40))
        self.camera().setViewCenter(QVector3D(0, 0, 0))

        # Контроллер камеры
        self.camController = Qt3DExtras.QOrbitCameraController(self.rootEntity)
        self.camController.setLinearSpeed(50)
        self.camController.setLookSpeed(180)
        self.camController.setCamera(self.camera())

        # Освещение
        lightEntity = Qt3DCore.QEntity(self.rootEntity)
        light = Qt3DRender.QPointLight(lightEntity)
        light.setColor(QColor.fromRgbF(1.0, 1.0, 0.7))
        light.setIntensity(1)
        lightEntity.addComponent(light)

        lightTransform = Qt3DCore.QTransform(lightEntity)
        lightTransform.setTranslation(self.camera().position())
        lightEntity.addComponent(lightTransform)

        # Устанавливаем корневую сущность в 3D-окно
        self.setRootEntity(self.rootEntity)

        # home
        # ✅ Load .obj Model
        self.objEntity = Qt3DCore.QEntity(self.rootEntity)
        self.objMesh = Qt3DRender.QMesh()
        self.objMesh.setSource(data.obj_path)  # ✅ Change this to your .obj file path

        self.objTransform = Qt3DCore.QTransform()
        self.objTransform.setScale3D(QVector3D(1, 1, 1))  # Adjust the scale if needed
        self.objTransform.setTranslation(QVector3D(0, 0, 0))  # Adjust position if needed
        # set parent of offset to entity
        # ✅ Apply Material
        self.objMaterial = Qt3DExtras.QDiffuseSpecularMaterial(self.rootEntity)
        self.objMaterial.setDiffuse(QVector3D(1.0,  1, 1))  # Orange color (change as needed)
        self.objMaterial.setShininess(0)  # Adjust shininess as needed
        self.objMaterial.setSpecular(QVector3D(0.3, 0.3, 0.3))  # Adjust specular as needed

        if(data.texture_diffuse_path):
            # ✅ Load Texture (if .mat file contains a texture)
            self.texture = Qt3DRender.QTexture2D()
            self.textureImage = Qt3DRender.QTextureImage()
            self.textureImage.setSource(data.texture_diffuse_path)  # ✅ Replace with actual texture path
            self.texture.addTextureImage(self.textureImage)
            self.objMaterial.setDiffuse(self.texture)

        # Attach components to entity
        self.objEntity.addComponent(self.objMesh)
        self.objEntity.addComponent(self.objTransform)
        self.objEntity.addComponent(self.objMaterial)

        self.controller = OrbitTransformController(self.objTransform)
        self.controller.setTarget(self.objTransform)
        self.controller.setRadius(0)

        self.objRotateTransformAnimation = QPropertyAnimation(self.objTransform)
        self.objRotateTransformAnimation.setTargetObject(self.controller)
        self.objRotateTransformAnimation.setPropertyName(b"angle")
        self.objRotateTransformAnimation.setStartValue(0)
        self.objRotateTransformAnimation.setEndValue(360)
        self.objRotateTransformAnimation.setDuration(10000)
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
