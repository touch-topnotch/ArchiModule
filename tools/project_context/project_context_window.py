from typing import List, Optional, Callable, Dict, Any
import os
import shutil
import datetime

import FreeCAD
import FreeCADGui

from PySide.QtGui import QVector3D
from PySide.QtWidgets import (QWidget, QLabel, QVBoxLayout, QTextEdit, QPushButton,
                              QGroupBox, QFormLayout, QScrollArea, QDockWidget, QMessageBox)
from PySide.QtCore import Qt

from tools.view_3d import View3DStyle
from tools.authentication.authentication import AuthenticatedSession
from tools.master_api import MasterAPI
from tools.models import Gen3dId, Gen3dSaved
from tools.project_context.utils.gallery_utils import (ImageCell, View3DCell, VideoCell,
                                GalleryStyle, GalleryWidget, select_images)
from tools.full_view import (FullViewWindow, FullViewImageInteractable, FullView3DInteractable,
                            FullViewVideoInteractable, FullViewButtonData, FullViewWindowData)
import tools.exporting as exporting
import tools.log as log
from tools.project_context.utils.project_behaviour_base import ProjectBehaviour
from tools.project_context.pipelines.gen_2d import PrepareFor2dGen, Generate2dBehaviour
from tools.project_context.pipelines.gen_3d import PrepareFor3dGen, Generate3dBehaviour
from tools.project_context.pipelines.gen_video import GenerateVideoBehaviour

# Backward compatibility alias
DownloadModelBehaviour = Generate3dBehaviour


# UI Constants
class UIStrings:
    WINDOW_TITLE = "Project Context"
    HEADER = "Project Context"
    PROJECT_CONTEXT = "Контекст проекта"
    PROJECT_PROMPT_PLACEHOLDER = "Опишите это здание. Добавьте информацию об окружении, ландшафте, истории, контексте здания"
    CONCEPTS = "Концепты"
    ADD_BUTTON = "Добавить"
    AI_2D = "AI 2D"
    TO_RENDERS = "В рендеры!"
    TO_3D_MODELS = "В 3D Модели!"
    AI_3D = "AI 3D"
    AI_VIDEO = "AI Видео"
    TO_VIDEO = "Создать видео"
    DELETE = "Удалить"
    REPLACE = "Заменить"
    CLOSE = "Закрыть"
    ADD_FRAME = "Добавить кадр"


class UIStyles:
    HEADER_STYLE = "font-size: 18pt; font-weight: bold;"
    SUBHEADER_STYLE = "font-size: 14pt; font-weight: bold;"
    
    @staticmethod
    def get_gallery_style(cols=2, min_height=300, max_height=400, cell_width=200, gap=10):
        return GalleryStyle(
            number_of_cols=cols,
            min_dock_height=min_height,
            max_dock_height=max_height,
            width_of_cell=cell_width,
            gap=gap
        )
    
    @staticmethod
    def get_3d_view_style():
        return View3DStyle(
            model_scale=1,
            light_intensity=1,
            light_direction=QVector3D(-90, -45, 70),
            camera_position=QVector3D(3, 0.5, 0),
        )


class ProjectContextWindow(QDockWidget):
    """
    A dock widget that manages project context, including:
    - Project description
    - Sketch galleries
    - 2D AI generation
    - 3D model generation
    """
    masterApi: MasterAPI
    authSession: AuthenticatedSession
    behaviours: List[ProjectBehaviour] = []
    
    def __init__(self, authSession, parent=None):
        """Initialize the ProjectContextWindow with the given auth session."""
        # --- Set parameters ---
        super(ProjectContextWindow, self).__init__(parent)
        self.mv = parent
        self.masterApi = authSession.masterAPI
        self.authSession = authSession
        
        # --- Setup UI components ---
        self._setup_main_ui()
        self._setup_context_section()
        self._setup_sketches_section()
        self._setup_2d_generation_section()
        self._setup_video_generation_section()
        self._setup_3d_generation_section()
        
        # --- Load saved data ---
        self.load_from_model(exporting.load())
    
    def _setup_main_ui(self):
        """Set up the main UI container and layout."""
        self.setWindowTitle(UIStrings.WINDOW_TITLE)
        
        # Create central widget with scroll area
        central_widget = QWidget()
        self.setWidget(central_widget)
        
        scroll_area = QScrollArea(central_widget)
        scroll_area.setWidgetResizable(True)
        
        scroll_content = QWidget()
        scroll_area.setWidget(scroll_content)
        
        self.main_layout = QVBoxLayout(scroll_content)
        central_layout = QVBoxLayout(central_widget)
        central_layout.addWidget(scroll_area)
        
        # Add header
        header_label = QLabel(UIStrings.HEADER)
        header_label.setStyleSheet(UIStyles.HEADER_STYLE)
        self.main_layout.addWidget(header_label)
        
        # Initialize full view window
        self._setup_full_view()
    
    def _setup_full_view(self):
        """Initialize and position the full view window."""
        self.full_view = FullViewWindow()
        main_window = FreeCADGui.getMainWindow()
        
        # Find model panel and add next to it
        model_dock = None
        for dock in main_window.findChildren(QDockWidget):
            if "Модель" in dock.windowTitle() or "Задачи" in dock.windowTitle():
                model_dock = dock
                break
                
        if model_dock:
            main_window.tabifyDockWidget(model_dock, self.full_view)
        else:
            main_window.addDockWidget(Qt.LeftDockWidgetArea, self.full_view)
            
        self.full_view.hide()
    
    def _setup_context_section(self):
        """Set up the project context section with text input."""
        params_group = QGroupBox()
        form_layout = QFormLayout(params_group)
        self.main_layout.addWidget(params_group)
        
        # Project context prompt field
        prompt_label = QLabel(UIStrings.PROJECT_CONTEXT)
        prompt_label.setStyleSheet(UIStyles.SUBHEADER_STYLE)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setPlaceholderText(UIStrings.PROJECT_PROMPT_PLACEHOLDER)
        self.prompt_edit.textChanged.connect(
            lambda: exporting.save_prop("prompt", self.prompt_edit.toPlainText())
        )
        
        form_layout.addRow(prompt_label)
        form_layout.addRow(self.prompt_edit)
    
    def _setup_sketches_section(self):
        """Set up the sketches gallery section."""
        sketch_group = QGroupBox()
        sketch_layout = QFormLayout(sketch_group)
        self.main_layout.addWidget(sketch_group)
        
        # Section header
        self.sketch_label = QLabel(UIStrings.CONCEPTS)
        self.sketch_label.setStyleSheet(UIStyles.SUBHEADER_STYLE)
        sketch_layout.addWidget(self.sketch_label)
        
        # Gallery
        side_gallery_style = UIStyles.get_gallery_style()
        self.sketches = GalleryWidget(side_gallery_style)
        
        # Add button
        self.sk_button = QPushButton(UIStrings.ADD_BUTTON)
        self.sk_button.clicked.connect(
            lambda: self.sketches.select_and_add_images(
                "sketches", 
                lambda cell: self.full_view.show(FullViewImageInteractable(cell.image_path)) if cell else None
            )
        )
        
        sketch_layout.addWidget(self.sketches)
        sketch_layout.addWidget(self.sk_button)
    
    def _setup_2d_generation_section(self):
        """Set up the 2D AI generation section."""
        # Section header
        env_label = QLabel(UIStrings.AI_2D)
        env_label.setStyleSheet(UIStyles.SUBHEADER_STYLE)
        self.main_layout.addWidget(env_label)
        
        # Gallery
        side_gallery_style = UIStyles.get_gallery_style()
        self.gen2d = GalleryWidget(side_gallery_style)
        # Generation button
        gen_renders_button = QPushButton(UIStrings.TO_RENDERS)
        gen_renders_button.clicked.connect(self._start_2d_generation)
        
        self.main_layout.addWidget(gen_renders_button)
        self.main_layout.addWidget(self.gen2d)
        
        # 3D generation button
        self.gen3d_renders_button = QPushButton(UIStrings.TO_3D_MODELS)
        self.gen3d_renders_button.clicked.connect(self.show_best_render)
        self.main_layout.addWidget(self.gen3d_renders_button)
    
    def _start_2d_generation(self):
        """Start the 2D generation process."""
        # Create and start the 2D generation behaviour
        # The behaviour will show UI to select sketches and handle generation
        behaviour = Generate2dBehaviour(
            self.authSession,
            self.masterApi,
            self.sketches,
            self.gen2d,
            self.full_view,
            self.prompt_edit
        )
        
        # Store the behaviour to prevent garbage collection
        self.behaviours.append(behaviour)
    
    def _setup_3d_generation_section(self):
        """Set up the 3D AI generation section."""
        # Section header
        three_d_env_label = QLabel(UIStrings.AI_3D)
        three_d_env_label.setStyleSheet(UIStyles.SUBHEADER_STYLE)
        self.main_layout.addWidget(three_d_env_label)
        
        # Gallery styles
        self.gen3dstyle = UIStyles.get_gallery_style(
            cols = 2,
            min_height = 400,
            gap = 10
            
        )
        self.view_3d_style = UIStyles.get_3d_view_style()
        
        # Gallery
        self.gen3d = GalleryWidget(self.gen3dstyle)
        self.main_layout.addWidget(self.gen3d)
    
    def _setup_video_generation_section(self):
        """Set up the video generation section."""
        # Section header
        video_label = QLabel(UIStrings.AI_VIDEO)
        video_label.setStyleSheet(UIStyles.SUBHEADER_STYLE)
        self.main_layout.addWidget(video_label)
        
        # Gallery
        video_gallery_style = UIStyles.get_gallery_style()
        self.gen_video = GalleryWidget(video_gallery_style)
        
        # Generation button
        gen_video_button = QPushButton(UIStrings.TO_VIDEO)
        gen_video_button.clicked.connect(self._start_video_generation)
        
        self.main_layout.addWidget(gen_video_button)
        self.main_layout.addWidget(self.gen_video)
    
    def _start_video_generation(self):
        """Start the video generation process."""
        behaviour = GenerateVideoBehaviour(
            self.authSession,
            self.masterApi,
            self.sketches,
            self.gen2d,
            self.gen_video
        )
        
        # Set callback to connect video cell actions
        def connect_video_cell_action(video_cell):
            video_cell.action.connect(
                lambda: self.full_view.show(self.gen_video_interactable(video_cell))
            )
        behaviour.on_video_cell_created = connect_video_cell_action
        
        self.behaviours.append(behaviour)
    
    def replace_full_image(self, index):
        """Replace an image at the given index with a newly selected one."""
        path = select_images("sketches", True)
        if path is not None:
            cell = ImageCell(image_path=path)
            self.sketches.change_cell(index, cell)
            self.full_view.show(self.sketch_interactable(cell))
    
    def gallery_on_delete_cell(self, gallery, item_name, cell):
        """Handle deletion of a cell from a gallery."""
        gallery.remove(cell.index)
        # Handle different cell types
        if isinstance(cell, ImageCell):
            exporting.remove_arr_item(item_name, cell.image_path)
        elif isinstance(cell, VideoCell):
            exporting.remove_arr_item(item_name, cell.video_path)
        elif isinstance(cell, View3DCell):
            exporting.remove_arr_item(item_name, cell.view3dData.model_dump())
        self.full_view.close()
    
    def sketch_interactable(self, cell):
        """Create a FullViewWindowData for a sketch cell."""
        if isinstance(cell, ImageCell):
            return FullViewWindowData(
                interactable=FullViewImageInteractable(cell.image_path),
                buttons=[
                    FullViewButtonData(
                        name=UIStrings.DELETE, 
                        action=lambda: self.gallery_on_delete_cell(self.sketches, "sketches", cell)
                    ),
                    FullViewButtonData(
                        name=UIStrings.REPLACE, 
                        action=lambda: self.replace_full_image(cell.index)
                    ),
                    FullViewButtonData(
                        name=UIStrings.CLOSE, 
                        action=lambda: self.full_view.close()
                    )
                ]
            )
        return None
    
    def gen2d_interactable(self, cell):
        """Create a FullViewWindowData for a 2D generation cell."""
        if isinstance(cell, ImageCell):
            return FullViewWindowData(
                interactable=FullViewImageInteractable(cell.image_path),
                buttons=[
                    FullViewButtonData(
                        name=UIStrings.DELETE, 
                        action=lambda: self.gallery_on_delete_cell(self.gen2d, "generations2d", cell)
                    ),
                    FullViewButtonData(
                        name=UIStrings.CLOSE, 
                        action=lambda: self.full_view.close()
                    )
                ]
            )
        return None
    
    def gen3d_interactable(self, cell):
        """Create a FullViewWindowData for a 3D generation cell."""
        if isinstance(cell, View3DCell):
            return FullViewWindowData(
                interactable=FullView3DInteractable(cell.view3dData),
                buttons=[
                    FullViewButtonData(
                        name=UIStrings.DELETE, 
                        action=lambda: self.gallery_on_delete_cell(self.gen3d, "generations3d", cell)
                    ),
                    FullViewButtonData(
                        name=UIStrings.CLOSE, 
                        action=lambda: self.full_view.close()
                    )
                ]
            )
        return None
    
    def gen_video_interactable(self, cell):
        """Create a FullViewWindowData for a video generation cell."""
        if isinstance(cell, VideoCell):
            def on_frame_added(frame_path: str):
                """Handle frame extraction - add to 2D generations."""
                try:
                    saved_path = self._save_video_frame_to_gen2d(frame_path)
                    if not saved_path:
                        raise RuntimeError("Файл кадра не найден")
                    QMessageBox.information(
                        FreeCADGui.getMainWindow(),
                        "Успешно",
                        "Кадр добавлен в 2D генерации"
                    )
                except Exception as e:
                    log.error(f"Failed to add frame to 2D generations: {e}")
                    QMessageBox.warning(
                        FreeCADGui.getMainWindow(),
                        "Ошибка",
                        f"Не удалось добавить кадр: {e}"
                    )
                finally:
                    try:
                        if frame_path and os.path.exists(frame_path):
                            os.remove(frame_path)
                    except Exception:
                        pass
            
            return FullViewWindowData(
                interactable=FullViewVideoInteractable(
                    cell.video_path,
                    on_frame_added=on_frame_added
                ),
                buttons=[
                    FullViewButtonData(
                        name=UIStrings.ADD_FRAME,
                        action=self._handle_add_video_frame
                    ),
                    FullViewButtonData(
                        name=UIStrings.DELETE,
                        action=lambda: self.gallery_on_delete_cell(self.gen_video, "generations_video", cell)
                    ),
                    FullViewButtonData(
                        name=UIStrings.CLOSE,
                        action=lambda: self.full_view.close()
                    )
                ]
            )
        return None
    
    def load_from_model(self, model: exporting.ProjectContextModel):
        """Load data from a saved project model."""
        # Load project prompt
        self.prompt_edit.setPlainText(model.prompt)
        
        # Load sketches
        self._load_gallery_cells(
            self.sketches, 
            [ImageCell(image_path=path) for path in model.sketches],
            self.sketch_interactable
        )
        
        # Load 2D generations
        self._load_gallery_cells(
            self.gen2d, 
            [ImageCell(image_path=path) for path in model.generations2d],
            self.gen2d_interactable
        )
    
        # Load video generations
        video_paths = getattr(model, 'generations_video', [])
        self._load_gallery_cells(
            self.gen_video,
            [VideoCell(path) for path in video_paths],
            self.gen_video_interactable
        )
        
        # Load 3D generations
        self._load_gallery_cells(
            self.gen3d, 
            [View3DCell(data, self.view_3d_style) for data in model.generations3d if data.local is not None],
            self.gen3d_interactable
        )
        
      
    
    def _load_gallery_cells(self, gallery, cells, interactable_func):
        """Helper method to load cells into a gallery with proper event connections."""
        gallery.add_cells(cells)
        for cell in gallery.cells:
            cell.action.connect(
                lambda cell=cell: self.full_view.show(interactable_func(cell))
            )

    def _save_video_frame_to_gen2d(self, frame_path: str) -> Optional[str]:
        """Copy extracted frame into generations2d and update gallery."""
        if not frame_path or not os.path.exists(frame_path):
            return None
        project_path = exporting.get_project_path()
        gen_dir = os.path.join(project_path, "generations2d")
        os.makedirs(gen_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')
        dest_path = os.path.join(gen_dir, f"video_frame_{timestamp}.jpg")
        shutil.copy(frame_path, dest_path)

        frame_cell = ImageCell(image_path=dest_path)
        self.gen2d.add_cell(frame_cell)
        frame_cell.action.connect(lambda cell=frame_cell: self.full_view.show(self.gen2d_interactable(cell)))
        exporting.save_arr_item("generations2d", dest_path)
        return dest_path

    def _handle_add_video_frame(self):
        """Capture current video frame and add it to 2D generations."""
        interactable = getattr(self.full_view, "interactable", None)
        if not isinstance(interactable, FullViewVideoInteractable):
            QMessageBox.warning(
                FreeCADGui.getMainWindow(),
                "Нет видео",
                "Сейчас не открыт просмотр видео."
            )
            return

        frame_path = interactable.capture_current_frame()
        if not frame_path:
            QMessageBox.warning(
                FreeCADGui.getMainWindow(),
                "Ошибка",
                "Не удалось получить кадр."
            )
    
    def show_best_render(self):
        """Show UI for creating 3D model from 2D renders."""
        self.create3dModel = PrepareFor3dGen(
            self.gen2d, 
            self.authSession, 
            self.on_obj_id_generated
        )
        main_window = FreeCADGui.getMainWindow()
        main_window.addDockWidget(Qt.LeftDockWidgetArea, self.create3dModel) # Add to UI
        self.create3dModel.setFloating(True) # Optional: Make it float
        self.create3dModel.show()              # Make it visible
    
    def on_obj_id_generated(self, result: Optional[Gen3dId], error: Optional[Exception]):
        """Handle callback when a 3D model ID is generated."""
        if error or result is None:
            return
        
        # Используем get_id() для получения task_id или obj_id (API returns task_id, not obj_id)
        task_id = result.get_id()
        if not task_id:
            log.warning("on_obj_id_generated: No task_id or obj_id in result")
            return
            
        saved = Gen3dSaved(
            local=None,
            online=None,
            obj_id=task_id  # Используем get_id() результат (task_id из API)
        )
        
        exporting.save_arr_item("generations3d", saved.model_dump())
        
        # Add download behavior to track model downloading
        status_callback = lambda x: print("Status of loading model - ", x)
        self.behaviours.append(
            DownloadModelBehaviour(
                status_callback,
                self.gen3d,
                result,
                self.view_3d_style,
                self.authSession
            )
        )
