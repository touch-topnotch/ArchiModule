import base64
import datetime
import os
from typing import Optional, List, Callable

import FreeCAD
import FreeCADGui
from PySide.QtCore import Qt, QObject, Signal
from PySide.QtWidgets import QLineEdit, QMessageBox, QWidget
from tools.authentication import AuthenticatedSession
from tools.master_api import MasterAPI
from tools import models as Models
from tools.gallery_utils import GalleryWidget, ImageCell, AnimatedCell
from tools.full_view import (FullViewWindow, FullViewWindowData, 
                           FullViewImageInteractable, FullViewButtonData)
from tools.project_context.utils.project_behaviour_base import ProjectBehaviour
from tools.project_context.pipelines.prepare_for_2d_gen import PrepareFor2dGen
from tools import exporting


class UIStrings:
    """Constant strings used in the UI."""
    DELETE_BUTTON = "Удалить"
    CLOSE_BUTTON = "Закрыть"
    
    # Error messages
    ERROR_TITLE = "Ошибка"
    IMAGE_GEN_ERROR = "Ошибка при генерации изображения: "
    INVALID_CHARS_ERROR = "Скорее всего вы ввели недопустимые символы в поле контекста"


class Generate2dBehaviour(ProjectBehaviour):
    """
    Behavior for generating 2D renders from sketches.
    Handles the selection of sketches, generation of 2D renders, and display in the gallery.
    """
    
    def __init__(self,
                 authSession: AuthenticatedSession,
                 masterApi: MasterAPI,
                 sketches: GalleryWidget,
                 gen2d: GalleryWidget,
                 full_view: FullViewWindow,
                 prompt_edit: QWidget,
                 parent: QObject = None):
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
        self.gen_stack: List[int] = []
        
        # Create and show sketch selection dialog
        self._show_sketch_selector()
    
    def _show_sketch_selector(self):
        """Create and display the sketch selection dialog."""
        if not self.sketches or not self.sketches.cells:
            QMessageBox.warning(None, "Нет скетчей", "Пожалуйста, добавьте скетчи в раздел 'Концепты' перед генерацией.")
            self.deleteLater() # Clean up behaviour if no sketches
            return

        try:
            self.selectBestSketch = PrepareFor2dGen(
                sketches=self.sketches,
                onApprove=self.generate_render
            )
        except Exception as e:
            FreeCAD.Console.PrintError(f"Gen2dBehaviour._show_select_sketch_ui: CRITICAL ERROR during PrepareFor2dGen instantiation: {e}\n")
            import traceback
            FreeCAD.Console.PrintError(traceback.format_exc() + "\n")
            QMessageBox.critical(None, "Ошибка инициализации", f"Не удалось создать окно подготовки: {e}")
            self.deleteLater() # Clean up
            return # Stop execution here if creation failed

        try:
            main_window = FreeCADGui.getMainWindow()
            if not main_window:
                 FreeCAD.Console.PrintError("Gen2dBehaviour._show_select_sketch_ui: Failed to get main window! Cannot show PrepareFor2dGen.\n")
                 self.selectBestSketch.deleteLater() # Clean up widget
                 self.deleteLater()
                 return

            main_window.addDockWidget(Qt.LeftDockWidgetArea, self.selectBestSketch) # Or Qt.RightDockWidgetArea, etc.
            self.selectBestSketch.setFloating(True)
            self.selectBestSketch.show()
        
        except Exception as e:
            FreeCAD.Console.PrintError(f"Gen2dBehaviour._show_select_sketch_ui: Error showing PrepareFor2dGen: {e}\n")
            import traceback
            FreeCAD.Console.PrintError(traceback.format_exc() + "\n")
            QMessageBox.critical(None, "Ошибка отображения", f"Не удалось отобразить окно подготовки: {e}")
            if self.selectBestSketch:
                self.selectBestSketch.deleteLater() # Clean up widget if it exists
            self.deleteLater()
    
    def generate_render(self, gen2dInput: Models.Gen2dInput):
        """
        Start the 2D render generation process.
        
        Args:
            gen2dInput: Input parameters for the 2D generation
        """
        # Save input parameters

        self._save_parameters(gen2dInput)

        # Handle authentication if needed
        if not self._ensure_authenticated():
            return

        # Show loading animation
        cell_id = self._show_loading_animation()
        
        # Start generation API call
        if(self.authSession.auto_login()):
            token = self.authSession.token.access_token
        else:
            self.authSession.show_login()
            return
        self.masterApi.run_async_task(
            self.masterApi.generate_2d, 
            self.on_image_generated, 
            token=token, 
            gen2dInput=gen2dInput
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
        
        self.prompt_edit.setText(gen2dInput.prompt)
    
    def _ensure_authenticated(self) -> bool:
        """
        Ensure the user is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        if not self.authSession or not self.authSession.token:
            complete = self.authSession.auto_login()
            if not complete:
                self.authSession.show_login()
                return False
        return True
    
    def _show_loading_animation(self) -> int:
        """
        Display a loading animation in the gallery.
        
        Returns:
            ID of the created cell
        """
        loader_path = FreeCAD.getResourceDir() + "Mod/ArchiModule/Resources/anims/Archi_Preloader.svg"
        cell = AnimatedCell(loader_path)
        cell.setBackground(self.selectBestSketch.selected_sketch_path)
        cell_id = self.gen2d.add_cell(cell)
        self.gen_stack.append(cell_id)
        return cell_id
    
    def on_image_generated(self, result: Optional[Models.Gen2dResult], error: Optional[Exception]):
        """
        Handle the completion of image generation.
        
        Args:
            result: The generated image result
            error: Any error that occurred during generation
        """
        if error or not result:
            self._handle_generation_error(error)
            return
            
        if not result.image_base64:
            self._show_error_message(UIStrings.INVALID_CHARS_ERROR)
            self._remove_loading_animation()
            return
        
        # Save and display the generated image
        self._save_and_display_generated_image(result.image_base64)
    
    def _handle_generation_error(self, error: Optional[Exception]):
        """
        Handle errors during image generation.
        
        Args:
            error: The error that occurred
        """
        error_msg = str(error) if error else "Unknown error"
        self._show_error_message(UIStrings.IMAGE_GEN_ERROR + error_msg)
        self._remove_loading_animation()
    
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
    
    def _remove_loading_animation(self):
        """Remove the loading animation from the gallery."""
        if self.gen_stack:
            self.gen2d.remove(self.gen_stack.pop())
    
    def _save_and_display_generated_image(self, image_base64: str):
        """
        Save the generated image and display it in the gallery.
        
        Args:
            image_base64: Base64 encoded image data
        """
        # Create directory if needed
        project_path = exporting.get_project_path()
        gen_dir = f"{project_path}/generations2d"
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
        cell.action.connect(lambda cell: self.full_view.show(self.gen2d_interactable(cell)))
        
        # Save to project data
        exporting.save_arr_item("generations2d", path)
    
    def gallery_on_delete_cell(self, gallery: GalleryWidget, item_name: str, cell: ImageCell):
        """
        Handle deletion of a cell from a gallery.
        
        Args:
            gallery: The gallery widget containing the cell
            item_name: Name of the item type for export
            cell: The cell to delete
        """
        gallery.remove(cell.index)
        exporting.remove_arr_item(item_name, cell.image_path)
        self.full_view.close()
    
    def gen2d_interactable(self, cell: ImageCell) -> Optional[FullViewWindowData]:
        """
        Create a FullViewWindowData for a 2D generation cell.
        
        Args:
            cell: The cell to create interactable for
            
        Returns:
            FullViewWindowData object or None if cell is not an ImageCell
        """
        if isinstance(cell, ImageCell):
            return FullViewWindowData(
                interactable=FullViewImageInteractable(cell.image_path),
                buttons=[
                    FullViewButtonData(
                        name=UIStrings.DELETE_BUTTON,
                        action=lambda: self.gallery_on_delete_cell(self.gen2d, "generations2d", cell)
                    ),
                    FullViewButtonData(
                        name=UIStrings.CLOSE_BUTTON,
                        action=lambda: self.full_view.close()
                    )
                ]
            )
        return None

    def __del__(self):
        """Destructor to print a message when the object is deleted."""
        FreeCAD.Console.PrintMessage(f"Generate2dBehaviour instance {id(self)} being deleted.\n")
        # Ensure any owned widgets like the dialog are closed/deleted if necessary
        if self.selectBestSketch:
            self.selectBestSketch.close() # Try closing it first
            self.selectBestSketch.deleteLater()