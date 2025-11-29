"""
Gen 2D Behaviour Module.

This module handles the complete 2D generation pipeline:
- Shows sketch selection UI (uses prepare.py)
- Initiates API calls for generation
- Processes API responses
- Saves generated images to disk
- Updates gallery with results
"""
import base64
import datetime
import os
from typing import Optional, List

import FreeCAD
import FreeCADGui
from PySide.QtCore import Qt, QObject
from PySide.QtWidgets import QMessageBox, QWidget

from tools.authentication import AuthenticatedSession
from tools.master_api import MasterAPI
from tools import models as Models
from tools import exporting
from tools.models import AsyncResponse
from tools.project_context.utils.gallery_utils import GalleryWidget, ImageCell, LoadingCell
from tools.full_view import (
    FullViewWindow, FullViewWindowData, 
    FullViewImageInteractable, FullViewButtonData
)
from tools.project_context.utils.project_behaviour_base import ProjectBehaviour
from tools.project_context.pipelines.gen_2d.prepare import PrepareFor2dGen
import tools.log as log


class UIStrings:
    """Constant strings used in the UI."""
    DELETE_BUTTON = "Удалить"
    CLOSE_BUTTON = "Закрыть"
    
    # Error messages
    ERROR_TITLE = "Ошибка"
    IMAGE_GEN_ERROR = "Ошибка при генерации изображения: "
    INVALID_CHARS_ERROR = "Скорее всего вы ввели недопустимые символы в поле контекста"
    
    # Warnings
    NO_SKETCHES_TITLE = "Нет скетчей"
    NO_SKETCHES_TEXT = "Пожалуйста, добавьте скетчи в раздел 'Концепты' перед генерацией."
    AUTH_ERROR_TITLE = "Ошибка авторизации"
    AUTH_ERROR_TEXT = "Не удалось авторизоваться. Пожалуйста, проверьте ваш email и пароль."
    INIT_ERROR_TITLE = "Ошибка инициализации"
    DISPLAY_ERROR_TITLE = "Ошибка отображения"


class PromptEnhancements:
    """Additional prompts for better generation quality."""
    
    POSITIVE = """
    Single isolated futuristic tower in the center of the frame.
The same unique sculptural building on all views.

The building is made of white matte panels with sharp angular folded shapes, 
almost like origami. Clean continuous planes, no visible floor slabs.

In the middle of the facade there is ONE tall vertical panoramic window,
a continuous glass slot running from the ground floor to the roof.
Almost no other windows, only small details inside this central glass slot.

Minimalist architectural concept style:
white building, white floor, white or very light grey background,
soft neutral lighting, very clean lines, almost like a sketch or model render.
No reflections of a city on the glass.

The scene is empty: no other buildings close to it, no trees, no grass,
no cars, no people, no street furniture, no text, no logos.
Focus only on the geometry of this single tower.
High clarity, sharp edges, perfect symmetry where visible.
Suitable as reference for 3D reconstruction.
    """
    
    NEGATIVE = """
    generic modern office tower, typical 2010s skyscraper, 
curtain wall glass tower, blue mirrored glass, strong reflections,
dense city background, skyline, other high-rises,
trees, grass, park, cars, buses, people, crowd, street lights, benches,
billboards, text, logos, advertisements,
complex shadows, dramatic lighting, fog, haze, film grain, dirt, damage
    """


class Generate2dBehaviour(ProjectBehaviour):
    """
    Behavior for generating 2D renders from sketches.
    
    Handles the complete 2D generation pipeline:
    1. Shows sketch selection UI (PrepareFor2dGen)
    2. Initiates API calls for generation
    3. Processes API responses
    4. Saves generated images to disk
    5. Updates gallery with results
    """
    
    ESTIMATED_GENERATION_TIME_SECONDS: int = 25
    GENERATIONS_DIR = "generations2d"
    
    def __init__(
        self,
        authSession: AuthenticatedSession,
        masterApi: MasterAPI,
        sketches: GalleryWidget,
        gen2d: GalleryWidget,
        full_view: FullViewWindow,
        prompt_edit: QWidget,
        parent: QObject = None
    ):
        """
        Initialize the Generate2dBehaviour.
        
        Args:
            authSession: The authenticated session
            masterApi: API for generating 2D renders
            sketches: Gallery widget containing sketch images
            gen2d: Gallery widget to display generated 2D renders
            full_view: Full view window for displaying images
            prompt_edit: Line edit for prompt text
            parent: Optional parent QObject
        """
        super().__init__(parent)
        
        # Set properties
        self.status = self.Status.RUNNING
        self.authSession = authSession
        self.masterApi = masterApi
        self.sketches = sketches
        self.gen2d = gen2d
        self.prompt_edit = prompt_edit
        self.full_view = full_view
        
        # Stack for tracking loading cells
        self.gen_stack: List[int] = []
        
        # Dialog reference
        self.selectBestSketch: Optional[PrepareFor2dGen] = None
        
        # Create and show sketch selection dialog
        self._show_sketch_selector()
    
    # ==================== UI Management ====================
    
    def _show_sketch_selector(self):
        """Create and display the sketch selection dialog."""
        if not self.sketches or not self.sketches.cells:
            QMessageBox.warning(None, UIStrings.NO_SKETCHES_TITLE, UIStrings.NO_SKETCHES_TEXT)
            self.deleteLater()
            return

        try:
            self.selectBestSketch = PrepareFor2dGen(
                sketches=self.sketches,
                onApprove=self.generate_render
            )
        except Exception as e:
            FreeCAD.Console.PrintError(
                f"Gen2dBehaviour._show_sketch_selector: CRITICAL ERROR: {e}\n"
            )
            import traceback
            FreeCAD.Console.PrintError(traceback.format_exc() + "\n")
            QMessageBox.critical(None, UIStrings.INIT_ERROR_TITLE, f"Не удалось создать окно подготовки: {e}")
            self.deleteLater()
            return

        try:
            main_window = FreeCADGui.getMainWindow()
            if not main_window:
                FreeCAD.Console.PrintError(
                    "Gen2dBehaviour._show_sketch_selector: Failed to get main window!\n"
                )
                self.selectBestSketch.deleteLater()
                self.deleteLater()
                return

            main_window.addDockWidget(Qt.LeftDockWidgetArea, self.selectBestSketch)
            self.selectBestSketch.setFloating(True)
            self.selectBestSketch.show()
        
        except Exception as e:
            FreeCAD.Console.PrintError(f"Gen2dBehaviour._show_sketch_selector: Error: {e}\n")
            import traceback
            FreeCAD.Console.PrintError(traceback.format_exc() + "\n")
            QMessageBox.critical(None, UIStrings.DISPLAY_ERROR_TITLE, f"Не удалось отобразить окно подготовки: {e}")
            if self.selectBestSketch:
                self.selectBestSketch.deleteLater()
            self.deleteLater()
    
    def _show_loading_animation(self) -> int:
        """
        Display a loading animation in the gallery.
        
        Returns:
            ID of the created loading cell
        """
        cell = LoadingCell()
        cell.set_estimated_time(self.ESTIMATED_GENERATION_TIME_SECONDS)
        cell_id = self.gen2d.add_cell(cell)
        self.gen_stack.append(cell_id)
        return cell_id
    
    def _remove_loading_animation(self):
        """Remove the loading animation from the gallery."""
        if self.gen_stack:
            self.gen2d.remove(self.gen_stack.pop())
    
    def _show_error_message(self, message: str):
        """
        Display an error message to the user.
        
        Args:
            message: The error message to display
        """
        QMessageBox.warning(
            FreeCADGui.getMainWindow(), 
            UIStrings.ERROR_TITLE, 
            message, 
            QMessageBox.Ok
        )
    
    # ==================== Generation Flow ====================
    
    def generate_render(self, gen2dInput: Models.Gen2dInput):
        """
        Start the 2D render generation process.
        
        Args:
            gen2dInput: Input parameters for the 2D generation
        """
        # Save input parameters
        self._save_parameters(gen2dInput)

        # Show loading animation
        cell_id = self._show_loading_animation()
        
        # Check authentication
        if self.authSession.is_authenticated():
            token = self.authSession.token
        else:
            log.info("Gen2dBehaviour.generate_render: Starting auto login")
            
            def on_auto_login(response: AsyncResponse):
                if response.has_result():
                    self.generate_render(gen2dInput)
                else:
                    QMessageBox.critical(None, UIStrings.AUTH_ERROR_TITLE, UIStrings.AUTH_ERROR_TEXT)
                    
            self.authSession.auto_login(on_auto_login)
            return
        
        # Prepare enhanced input with additional prompts
        enhanced_input = Models.Gen2dInput(
            prompt=gen2dInput.prompt + PromptEnhancements.POSITIVE,
            negative_prompt=gen2dInput.negative_prompt + PromptEnhancements.NEGATIVE,
            control_strength=gen2dInput.control_strength,
            image_base64=gen2dInput.image_base64,
            seed=gen2dInput.seed
        )
        
        # Define callback for animated response handling
        def on_generate_2d_animated(response: AsyncResponse[Optional[Models.Gen2dResult]]):
            self._on_image_generated_animated(response, cell_id)
        
        # Start API call
        self.masterApi.run_async_task(
            self.masterApi.generate_2d, 
            on_generate_2d_animated, 
            token=token, 
            gen2dInput=enhanced_input
        )
    
    def _save_parameters(self, gen2dInput: Models.Gen2dInput):
        """
        Save the generation parameters to project.
        
        Args:
            gen2dInput: Input parameters to save
        """
        exporting.save_prop("prompt", gen2dInput.prompt)
        exporting.save_prop("negative_prompt", gen2dInput.negative_prompt)
        exporting.save_prop("slider_value", gen2dInput.control_strength)
        
        if hasattr(self.prompt_edit, 'setText'):
            self.prompt_edit.setText(gen2dInput.prompt)
    
    # ==================== Response Handling ====================
    
    def _on_image_generated_animated(
        self, 
        response: AsyncResponse[Optional[Models.Gen2dResult]],
        cell_id: int
    ):
        """
        Handle image generation with animation completion.
        
        Args:
            response: The async response containing the generated image result
            cell_id: ID of the loading cell to animate
        """
        log.info("Gen2dBehaviour._on_image_generated_animated: callback entered")
        try:
            cell = self.gen2d.cells[cell_id]
        except Exception as e:
            FreeCAD.Console.PrintError(
                f"Gen2dBehaviour._on_image_generated_animated: failed to get loading cell: {e}\n"
            )
            self._on_image_generated(response)
            return
            
        if isinstance(cell, LoadingCell):
            try:
                cell.show_max_progress_and_close(lambda: self._on_image_generated(response), 1000)
            except Exception as e:
                FreeCAD.Console.PrintError(
                    f"Gen2dBehaviour._on_image_generated_animated: animation error: {e}\n"
                )
                self._on_image_generated(response)
        else:
            self._on_image_generated(response)
    
    def _on_image_generated(self, response: AsyncResponse[Optional[Models.Gen2dResult]]):
        """
        Handle the completion of image generation.
        
        Args:
            response: The async response containing the generated image result
        """
        if response.has_error() or not response.has_result():
            self._handle_generation_error(response.error)
            return
            
        if not response.result.image_base64:
            self._show_error_message(UIStrings.INVALID_CHARS_ERROR)
            self._remove_loading_animation()
            return
        
        self._save_and_display_generated_image(response.result.image_base64)
    
    def _handle_generation_error(self, error: Optional[Exception]):
        """
        Handle errors during image generation.
        
        Args:
            error: The error that occurred
        """
        error_msg = str(error) if error else "Unknown error"
        self._show_error_message(UIStrings.IMAGE_GEN_ERROR + error_msg)
        self._remove_loading_animation()
    
    # ==================== File & Gallery Management ====================
    
    def _save_and_display_generated_image(self, image_base64: str):
        """
        Save the generated image and display it in the gallery.
        
        Args:
            image_base64: Base64 encoded image data
        """
        # Create directory if needed
        project_path = exporting.get_project_path()
        gen_dir = f"{project_path}/{self.GENERATIONS_DIR}"
        if not os.path.exists(gen_dir):
            os.makedirs(gen_dir)
            
        # Save image to file
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        path = f"{gen_dir}/{timestamp}.jpg"
        
        with open(path, "wb") as f:
            f.write(base64.b64decode(image_base64))
        
        # Replace loading animation with the generated image
        cell = ImageCell(image_path=path)
        cell_id = self.gen_stack.pop()
        self.gen2d.change_cell(cell_id, cell)
        
        # Connect action to show full view
        cell.action.connect(lambda c: self.full_view.show(self._create_interactable(c)))
        
        # Save to project data
        exporting.save_arr_item(self.GENERATIONS_DIR, path)
    
    def _create_interactable(self, cell: ImageCell) -> Optional[FullViewWindowData]:
        """
        Create a FullViewWindowData for a 2D generation cell.
        
        Args:
            cell: The cell to create interactable for
            
        Returns:
            FullViewWindowData object or None if cell is not an ImageCell
        """
        if not isinstance(cell, ImageCell):
            return None
            
        return FullViewWindowData(
            interactable=FullViewImageInteractable(cell.image_path),
            buttons=[
                FullViewButtonData(
                    name=UIStrings.DELETE_BUTTON,
                    action=lambda: self._delete_cell(cell)
                ),
                FullViewButtonData(
                    name=UIStrings.CLOSE_BUTTON,
                    action=lambda: self.full_view.close()
                )
            ]
        )
    
    def _delete_cell(self, cell: ImageCell):
        """
        Delete a cell from the gallery.
        
        Args:
            cell: The cell to delete
        """
        self.gen2d.remove(cell.index)
        exporting.remove_arr_item(self.GENERATIONS_DIR, cell.image_path)
        self.full_view.close()

    # ==================== Lifecycle ====================
    
    def __del__(self):
        """Destructor to clean up resources."""
        log.info(f"Generate2dBehaviour instance {id(self)} being deleted.\n")
        if hasattr(self, 'selectBestSketch') and self.selectBestSketch:
            self.selectBestSketch.close()
            self.selectBestSketch.deleteLater()

