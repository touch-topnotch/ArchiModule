import base64
import datetime
import os
import time
from typing import List, Optional

import FreeCAD
import FreeCADGui


from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QWidget, QLabel, QVBoxLayout, 
                               QSlider, QLineEdit, QPushButton,
                               QGroupBox, QFormLayout, QScrollArea, QDockWidget, QHBoxLayout, QVBoxLayout,
                                QMessageBox,QGraphicsOpacityEffect, QGraphicsBlurEffect)
from Tools.Authentication import AuthenticatedSession
from Tools.MasterAPI import MasterAPI
from Tools.Models import Gen2dInput, Gen2dResult
from Tools.GalleryUtils import (ImageCell,AnimatedCell,View3DCell,
                                GalleryStyle,GalleryWidget, select_images)
from Tools.FullView import (FullViewWindow, FullViewImageInteractable,FullView3DInteractable,
                                FullViewButtonData,  FullViewWindowData)
from Tools import Exporting

class BestSketch(QDockWidget):
    def __init__(self, sketches:GalleryWidget, onApprove, parent=None):
        super(BestSketch, self).__init__(parent)
        self.onApprove = onApprove
        self.selected_sketch = None
        self.sketches = sketches
        self.formLayout = QFormLayout()
        self.model = Exporting.load()
        self.setWindowTitle("Best Sketch")
        # add form layout to dock widget
        self.setWidget(QWidget())
        self.widget().setLayout(self.formLayout)

        self.title = QLabel("Пожалуйста, выберите лучший скетч")
        self.title.setStyleSheet("font-size: 14pt; font-weight: bold;")

        self.subtitle = QLabel("По большей части от него будет произведена генерация рендеров")
        self.subtitle.setStyleSheet("font-size: 12pt;")
        self.title.setAlignment(Qt.AlignCenter)
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.formLayout.addRow(self.title)
        self.formLayout.addRow(self.subtitle)
        main_win = FreeCADGui.getMainWindow()
        mw_geo = main_win.geometry()
        new_width = int(mw_geo.width() * 0.6)
        new_height = int(mw_geo.height() * 0.6)
        style = GalleryStyle(number_of_cols=3, min_dock_height=int(new_height*0.3), max_dock_height=new_height, width_of_cell=int(new_width/3.2), gap=10)
        self.gallery = GalleryWidget(style)
        self.gallery.add_cells([cell.copy() for cell in self.sketches.cells])
        for cell in self.gallery.cells:
            cell.action.connect(lambda cell: self.selectBest(cell.index))
        self.formLayout.addRow(self.gallery)
        self.realism_slider = QSlider(Qt.Horizontal)
        self.realism_slider.setRange(0, 100)
        self.realism_slider.setValue(self.model.slider_value * 100)
        self.formLayout.setSpacing(10)
        self.formLayout.addRow("Сходство ", self.realism_slider)
        self.formLayout.setSpacing(10)
        self.prompt_label = QLabel("Контекст проекта")
        self.formLayout.addRow(self.prompt_label)
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setAlignment(Qt.AlignTop)
        self.prompt_edit.setText(self.model.prompt)
        self.formLayout.addRow(self.prompt_edit)
        self.formLayout.setSpacing(10)
        self.n_prompt_label = QLabel("Что вы не хотите видеть в рендере")
        self.formLayout.addRow(self.n_prompt_label)
        self.n_prompt_edit = QLineEdit()
        self.n_prompt_edit.setMinimumHeight(80)
        self.n_prompt_edit.setAlignment(Qt.AlignTop)
        self.n_prompt_edit.setText(self.model.negative_prompt)
        self.formLayout.addRow(self.n_prompt_edit)


        self.approve_button = QPushButton("Подтвердить")
        self.approve_button.clicked.connect(self.approve)
        self.formLayout.addRow(self.approve_button)
        # Center the dock widget at 40% of main window's dimensions

        
        new_x = int(mw_geo.x() + (mw_geo.width() - new_width) / 2)
        new_y = int(mw_geo.y() + (mw_geo.height() - new_height) / 2)
        self.setGeometry(new_x, new_y, new_width, new_height)

    def selectBest(self, id):
        self.selected_sketch = self.gallery.cells[id].image_path
        self.gallery.cells[id].label.setStyleSheet("border: 3px solid rgba(0, 160, 200, 0.9); border-radius: 15px;")
        for i in range(len(self.gallery.cells)):
            if i != id:
                effect = QGraphicsOpacityEffect(self.gallery.cells[i].label)
                effect.setOpacity(0.8)  # Set opacity to 50%
                blur_effect = QGraphicsBlurEffect(self.gallery.cells[i].label)
                blur_effect.setBlurRadius(50)
                # Apply blur effect on the image
                self.gallery.cells[i].label.setGraphicsEffect(blur_effect)
                # Also apply opacity by setting the widget's window opacity
                self.gallery.cells[i].label.setWindowOpacity(0.5)
                self.gallery.cells[i].label.setStyleSheet("border: 0px;")
            else:
                # remove blurcellst
                self.gallery.cells[i].label.setGraphicsEffect(None)
                self.gallery.cells[i].label.setWindowOpacity(1)

    def approve(self):
        '''
        Check if the user has selected a sketch
        Check if the user set prompt
        '''
        if self.selected_sketch is None:
            QMessageBox.warning(self, "Не выбран скетч", "Пожалуйста, выберите скетч для рендера")
            return
        if self.prompt_edit.text().strip() == "":
            QMessageBox.warning(self, "Нет контекста", "Опишите это здание. Добавьте информацию об окружении, ландшафте, истории, контексте здания")
            return
        # check, that text doesn't include any non-utf-8 characters
        try:
            converted_prompt = self.prompt_edit.text().strip().encode('ASCII')
            
            converted_neg_prompt = self.n_prompt_edit.text().strip().encode('ASCII')
        except UnicodeEncodeError:
            QMessageBox.warning(self, "Мы обязательно прикрутим переводчик!", "Сорян, зай🥺 Сейчас промпт должен быть только на английском")
            return
        # Further processing can be added here
        QMessageBox.information(self, "Готово", "Скоро рендеры будут готовы) Можете приступать к разработке проекта")
        sketch_path = self.selected_sketch
        with open(sketch_path, "rb") as f:
            image_bytes = base64.b64encode(f.read()).decode("ASCII")
        self.onApprove(
            Gen2dInput(
                image_base64=image_bytes,
                prompt=converted_prompt,
                control_strength=self.realism_slider.value()/100,
                negative_prompt=converted_neg_prompt,
                seed=int(time.time())%10000
            ))
        self.close()

class ArchiContextWindow(QDockWidget):
    masterApi: MasterAPI
    authSession: AuthenticatedSession
    def __init__(self, authSession, parent=None):

        print("ArchiContextWindow")

        # --- Set parameters ---
        self.mv = parent
        self.masterApi = authSession.masterAPI
        self.authSession = authSession
        
        # --- Initialize the dock widget ---
        
        super(ArchiContextWindow, self).__init__(parent)

        self.setWindowTitle("Project Context")
        central_widget = QWidget()
        self.setWidget(central_widget)
        scroll_area = QScrollArea(central_widget)
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_area.setWidget(scroll_content)
        main_layout = QVBoxLayout(scroll_content)
        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(scroll_area)
      
        # --- Header ---
        header_label = QLabel("Project Context")
        header_label.setStyleSheet("font-size: 18pt; font-weight: bold;")

        main_layout.addWidget(header_label)

        # --- Subheader: Parameters ---

        params_group = QGroupBox()
        form_layout = QFormLayout(params_group)
        main_layout.addWidget(params_group)

        # 1) Prompt (text field)
        prompt_label = QLabel("Контекст проекта")
        prompt_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setAlignment(Qt.AlignTop)
        self.prompt_edit.setPlaceholderText("Опишите это здание. Добавьте информацию об окружении, ландшафте, истории, контексте здания")
        self.prompt_edit.textChanged.connect(lambda: Exporting.save_prop("prompt", self.prompt_edit.text()))
        form_layout.addRow(prompt_label)
        form_layout.addRow(self.prompt_edit)

        # --- Subheader: Sketch Gallery ---
        side_gallery_style = GalleryStyle(
            number_of_cols=2,
            min_dock_height=300,
            max_dock_height=400,
            width_of_cell=200,
            gap=10
        )
        
        self.full_view = FullViewWindow()
        main_window = FreeCADGui.getMainWindow()
        # ✅ Ищем панель "Model" и добавляем рядом
        model_dock = None
        for dock in main_window.findChildren(QDockWidget):
            if "Модель" in dock.windowTitle() or "Задачи" in dock.windowTitle():  # Проверяем, есть ли "Model" в заголовке
                model_dock = dock
                break
        if model_dock:
            main_window.tabifyDockWidget(model_dock, self.full_view)
        else:
            main_window.addDockWidget(Qt.LeftDockWidgetArea, self.full_view)
        self.full_view.hide()
        
        
        sketch_group = QGroupBox()
        sketch_layout = QFormLayout(sketch_group)
        main_layout.addWidget(sketch_group)
    
        self.sketch_label = QLabel("Концепты")
        self.sketch_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        sketch_layout.addWidget(self.sketch_label)

        self.sketches = GalleryWidget(side_gallery_style)
        self.sk_button = QPushButton("Добавить")
        self.sk_button.clicked.connect(
            lambda: self.sketches.select_and_add_images("sketches", lambda cell:self.full_view.show(FullViewImageInteractable(cell.image_path))) )

        gen_renders_button = QPushButton("В рендеры!")
        gen_renders_button.clicked.connect(self.show_best_sketch)

        sketch_layout.addWidget(self.sketches)
        sketch_layout.addWidget(self.sk_button)
        main_layout.addWidget(gen_renders_button)

        # --- Subheader: Generations ---
        env_label = QLabel("AI Generations")
        env_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        main_layout.addWidget(env_label)
        self.gen2d = GalleryWidget(side_gallery_style)
        main_layout.addWidget(self.gen2d)
        
        # --- Subheader: Visualization ---
        viz_label = QLabel("Visualization")
        viz_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        main_layout.addWidget(viz_label)
        
        self.gen3dstyle = GalleryStyle(
            number_of_cols=2,
            min_dock_height=400,
            max_dock_height=400,
            width_of_cell = 200,
        )
        self.gen3d = GalleryWidget(self.gen3dstyle)
        main_layout.addWidget(self.gen3d)

        self.load_from_model(Exporting.load())
        
    def replace_full_image(self, index):
        path = select_images("sketches", True)
        if(path != None):
            cell = ImageCell(image_path=path)
            self.sketches.change_cell(index, cell)
            self.full_view.show(self.sketch_interactable(cell))
    def sketch_interactable(self, cell):
        print(isinstance(cell, ImageCell))
        if isinstance(cell, ImageCell):
            return FullViewWindowData(
                interactable=FullViewImageInteractable(cell.image_path),
                buttons=[   FullViewButtonData(name="Удалить", action=lambda: self.sketches.remove(cell.index)),
                            FullViewButtonData(name="Заменить", action=lambda: self.replace_full_image(cell.index)),
                            FullViewButtonData(name="Закрыть", action=lambda: self.full_view.close())
            ])
        return None
    
    def gen2d_interactable(self, cell):
        print(isinstance(cell, ImageCell))
        if isinstance(cell, ImageCell):
            return FullViewWindowData(
                interactable=FullViewImageInteractable(cell.image_path), 
                buttons=[   FullViewButtonData(name="Удалить", action=lambda: self.gen2d.remove(cell.index)),
                            FullViewButtonData(name="Закрыть", action=lambda: self.full_view.close())
            ])
        return None

    def gen3d_interactable(self, cell):
        print(isinstance(cell, View3DCell))
        if isinstance(cell, View3DCell):
            return FullViewWindowData(
                interactable=FullView3DInteractable(cell.view3dData),
                buttons=[   FullViewButtonData(name="Удалить", action=lambda: self.gen3d.remove(cell.index)),
                            FullViewButtonData(name="Закрыть", action=lambda: self.full_view.close())
            ])
        return None
    def load_from_model(self, model:Exporting.ProjectContextModel):
        self.prompt_edit.setText(model.prompt)
        self.sketches.add_cells([ImageCell(image_path=path) for i,path in enumerate(model.sketches)])
        for sketch_cell in self.sketches.cells:
            sketch_cell.action.connect(lambda cell: self.full_view.show(self.sketch_interactable(cell)))
        
        self.gen2d.add_cells([ImageCell(image_path=path) for i,path in enumerate(model.generations2d)])
        for gen2d_cell in self.gen2d.cells:
            gen2d_cell.action.connect(lambda cell: self.full_view.show(self.gen2d_interactable(cell)))
        
        
    def show_best_sketch(self):
        # Get sketches
        selectSketch = BestSketch(self.sketches, self.generate_render)
        FreeCADGui.getMainWindow().addDockWidget(Qt.LeftDockWidgetArea, selectSketch)
        selectSketch.setFloating(True)
        selectSketch.show()

    def generate_render(self, gen2dInput:Gen2dInput):
        # 1) Save the input
        Exporting.save_prop("prompt", gen2dInput.prompt)
        Exporting.save_prop("negative_prompt", gen2dInput.negative_prompt)
        Exporting.save_prop("slider_value", gen2dInput.control_strength)
        self.prompt_edit.setText(gen2dInput.prompt)

        # 2) Check authentication
        if not self.authSession or not self.authSession.token:
            complete = self.authSession.auto_login()
            if not complete:
                self.authSession.show_login()
        # 3) Show loading image in self.generations gallery
        cell = AnimatedCell(FreeCAD.getResourceDir() + "Mod/Archi/Resources/anims/Archi_Preloader.svg")
        self.gen2d.add_cell(cell)
        token = self.authSession.token.access_token
        self.masterApi.run_async_task(self.masterApi.generate_2d, self.on_image_generated, token=token, gen2dInput = gen2dInput)

    def on_image_generated(self, result: Optional[Gen2dResult], error: Optional[Exception]):
        
        if error:
            # show error message in box
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации изображения: " + str(error))
            # remove loading image from gallery
            self.gen2d.remove(len(self.gen2d.cells)-1)
            return
        if not result:
                # show error message in box
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации изображения: " + str(error))
            # remove loading image from gallery
            self.gen2d.remove(len(self.gen2d.cells)-1)
            return
        if not result.image_base64:
            QMessageBox.warning(self, "Ошибка", "Скорее всего вы ввели недопустимые символы в поле контекста")
            # remove loading image from gallery
            self.gen2d.remove(len(self.gen2d.cells)-1)
            return
        
        path = f"{Exporting.get_project_path()}/generations2d/{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
        if(not os.path.exists(f"{Exporting.get_project_path()}/generations2d")):
            os.makedirs(f"{Exporting.get_project_path()}/generations2d")

        with open(path, "wb") as f:
            f.write(base64.b64decode(result.image_base64))
            
        cell = ImageCell(image_path=path)
        self.gen2d.change_cell(len(self.gen2d.cells)-1, cell)
        cell.action.connect(lambda cell: self.full_view.show(self.gen2d_interactable(cell)))
        Exporting.save_arr_item("generations2d", path)
        # self.generations.show_full_view_window(cell.config.id)        
class Archi_ProjectContext_Command:
    def __init__(self, authenticatedSession):
        self.authenticatedSession = authenticatedSession

    def GetResources(self):
        return {
            "MenuText": "Project Context",
            "ToolTip": "Initialize or manage project context",
            "Pixmap": "Archi_ProjectContext"
        }

    def Activated(self):
        mw = FreeCADGui.getMainWindow()
        # find dock widgets with name Project Context
        dock_widgets = mw.findChildren(QDockWidget)
        for widget in dock_widgets:
            if widget.windowTitle() == "Project Context":
                widget.close()
            if widget.windowTitle() == "Best Sketch":
                widget.close()
            if widget.windowTitle() == "Full View":
                widget.close()
            if widget.windowTitle() == "Полный просмотр":
                widget.close()
            
		
        projectContextWindowInstance = ArchiContextWindow(self.authenticatedSession,mw)
        mw.addDockWidget(Qt.RightDockWidgetArea, projectContextWindowInstance)
        projectContextWindowInstance.show()

    def IsActive(self):
        return True
    
mw = FreeCADGui.getMainWindow()
# find dock widgets with name Project Context
dock_widgets = mw.findChildren(QDockWidget)
for widget in dock_widgets:
    if widget.windowTitle() in ["Project Context", "Best Sketch", "Full View"]:
        mw.removeDockWidget(widget
        )
        widget.close()

authenticatedSession = AuthenticatedSession(masterAPI=MasterAPI("http://89.169.36.93:8001"))
projectContextWindowInstance = ArchiContextWindow(authenticatedSession,mw)
mw.addDockWidget(Qt.RightDockWidgetArea, projectContextWindowInstance)
projectContextWindowInstance.show()