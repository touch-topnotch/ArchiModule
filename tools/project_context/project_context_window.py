from typing import List, Optional, Callable, Dict, Any

import FreeCAD
import FreeCADGui

from PySide.QtGui import QVector3D
from PySide.QtWidgets import (QWidget, QLabel, QVBoxLayout, QTextEdit, QPushButton,
                              QGroupBox, QFormLayout, QScrollArea, QDockWidget)
from PySide.QtCore import Qt

from tools.view_3d import View3DStyle
from tools.authentication.authentication import AuthenticatedSession
from tools.master_api import MasterAPI
from tools.models import Gen3dId, Gen3dSaved
from tools.gallery_utils import (ImageCell, View3DCell, 
                                GalleryStyle, GalleryWidget, select_images)
from tools.full_view import (FullViewWindow, FullViewImageInteractable, FullView3DInteractable,
                            FullViewButtonData, FullViewWindowData)
import tools.exporting as exporting
from tools.project_context.utils.project_behaviour_base import ProjectBehaviour
from tools.project_context.pipelines.prepare_for_3d_gen import PrepareFor3dGen
from tools.project_context.pipelines.download_model_behaviour import DownloadModelBehaviour
from tools.project_context.pipelines.prepare_for_2d_gen import PrepareFor2dGen
from tools.project_context.pipelines.gen_2d_behaviour import Generate2dBehaviour


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
    DELETE = "Удалить"
    REPLACE = "Заменить"
    CLOSE = "Закрыть"


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
        exporting.remove_arr_item(item_name, cell.image_path)
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
            
        saved = Gen3dSaved(
            local=None,
            online=None,
            obj_id=result.obj_id
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
