import base64
import datetime
import os
from enum import Enum
from typing import Optional, Tuple

import FreeCADGui
import FreeCAD # Added for PrintMessage
from PySide.QtCore import Qt, QPoint, Signal, QSize
from PySide.QtWidgets import (
    QLabel, QLineEdit, QPushButton, QHBoxLayout,
    QMessageBox, QGraphicsOpacityEffect, QGraphicsBlurEffect, QWidget,
    QTextEdit # Import QTextEdit
)
from PySide.QtGui import QPixmap, QPainter, QPen, QIcon, QMouseEvent

from .FormWindow import FormWindow
from Tools.Authentication import AuthenticatedSession
from Tools import Exporting, Models
from Tools.GalleryUtils import GalleryWidget, GalleryCell, GalleryStyle
from Tools.ProjectContext.Utils.Widgets import MyRadioButton
from Tools.ProjectContext.Utils.ImageUtils import apply_blur_effect, blend_images
import Tools.log as log

class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked."""
    clicked = Signal(QPoint)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton:
            self.clicked.emit(event.pos())
        super().mouseMoveEvent(event)


class PrepareFor3dGen(FormWindow):
    """Window to guide the user through selecting a render and preparing it for 3D generation."""

    class ToolType(Enum):
        PEN = 0
        ERASER = 1
        NONE = 2

    selected_tool: ToolType = ToolType.NONE
    MIN_CLICK_DISTANCE_DELTA = 90 # Minimum pixel distance between recorded clicks for drawing

    def __init__(self, generations: GalleryWidget, auth_session: AuthenticatedSession, onObjIdReceived, parent=None):
        super().__init__(title="Prepare for 3D generation", parent=parent)

        self.onObjIdReceived = onObjIdReceived
        self.auth_session = auth_session
        self.sketches_gallery_widget = generations # Store the input gallery
        self.project_model = Exporting.load()

        self.selected_render_path: Optional[str] = None
        self.pen_points: list[Tuple[int, int]] = []
        self.erased_points: list[Tuple[int, int]] = []
        self.image_path_history: list[str] = [] # Stack to keep track of image versions for undo

        self.selection_gallery: Optional[GalleryWidget] = None # Define instance variable
        self.prompt_edit: Optional[QTextEdit] = None # Change type hint to QTextEdit
        self.image_display_label: Optional[ClickableLabel] = None
        self.original_pixmap: Optional[QPixmap] = None
        self.blurred_pixmap: Optional[QPixmap] = None
        self.current_pixmap: Optional[QPixmap] = None
        self.original_image_size: Optional[QSize] = None
        self.display_scale_factors: Optional[Tuple[float, float]] = None # (x_scale, y_scale)
        self.last_click_pos: Optional[QPoint] = None

        self.waiting_message_box: Optional[QMessageBox] = None
        self.undo_button: Optional[QPushButton] = None

        # Calculate gallery style based on advisable size from FormWindow
        self.gallery_style = GalleryStyle(
            number_of_cols=3,
            min_dock_height=int(self.advisable_height*0.3),
            max_dock_height=self.advisable_height, # Allow gallery to take significant height
            width_of_cell=int(self.advisable_width /3.2),
            gap=10
        )

        self._setup_select_sketch_view()


    # --- UI Setup Methods ---

    def _clear_layout(self):
        """Removes all widgets from the main form layout."""
        # Use the layout from the base class
        while self.formLayout.count():
            item = self.formLayout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                # If it's a layout item, clear it recursively
                layout_item = item.layout()
                if layout_item:
                    # Basic clearing for nested QHBoxLayout etc.
                    while layout_item.count():
                        sub_item = layout_item.takeAt(0)
                        sub_widget = sub_item.widget()
                        if sub_widget:
                            sub_widget.deleteLater()


    def _setup_select_sketch_view(self):
        """Sets up the initial view for selecting the best render."""
        self._clear_layout()


        title = QLabel("Пожалуйста, выберите лучший рендер")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        subtitle = QLabel("По большей части от него будет произведена генерация 3d моделей")
        subtitle.setStyleSheet("font-size: 12pt;")
        title.setAlignment(Qt.AlignCenter)
        subtitle.setAlignment(Qt.AlignCenter)
        self.formLayout.addRow(title)
        self.formLayout.addRow(subtitle)

        self.selection_gallery = GalleryWidget(self.gallery_style)
        self.selection_gallery.add_cells([cell.copy() for cell in self.sketches_gallery_widget.cells])
        for cell in self.selection_gallery.cells:
            cell.action.connect(lambda bound_cell=cell: self._handle_sketch_selection(bound_cell.index))
        self.formLayout.addRow(self.selection_gallery)

        prompt_label = QLabel("Контекст проекта")
        self.formLayout.addRow(prompt_label)

        # --- Use QTextEdit instead of QLineEdit --- 
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(80)
        # setAlignment and setWordWrap are not needed/available for QTextEdit
        self.prompt_edit.setText(getattr(self.project_model, 'prompt', '')) # Load safely
        # Save prompt changes automatically
        self.prompt_edit.textChanged.connect(
             # Use lambda to get text from QTextEdit correctly
             lambda: Exporting.save_prop("prompt", self.prompt_edit.toPlainText()) # Use toPlainText()
        )
        self.formLayout.addRow(self.prompt_edit)

        self.formLayout.setSpacing(10)
        approve_button = QPushButton("Подтвердить")
        approve_button.clicked.connect(self._handle_approve_render)
        self.formLayout.addRow(approve_button)

    def _setup_remove_background_view(self, image_path: str):
        """Sets up the view for removing the background from the selected image."""
        self._clear_layout()
        self.image_path_history = [image_path] # Reset history with the new base image
        self.pen_points = []
        self.erased_points = []
        self.last_click_pos = None

        title = QLabel("Нужно удалить все лишнее, чтобы модель сгенерировалась максимально качественно!")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        subtitle = QLabel("Карандаш - для восстановления деталей, Ластик - для удаления лишних элементов")
        subtitle.setStyleSheet("font-size: 12pt;")
        title.setAlignment(Qt.AlignCenter)
        subtitle.setAlignment(Qt.AlignCenter)
        self.formLayout.addRow(title)
        self.formLayout.addRow(subtitle)

        # Tool selection buttons
        btn_container = QHBoxLayout()
        btn_container.setAlignment(Qt.AlignRight)
        pen_button = self._create_tool_button(":/icons/Archi_Pencil", self.ToolType.PEN)
        eraser_button = self._create_tool_button(":/icons/Archi_Easier", self.ToolType.ERASER)
        eraser_button.setChecked(True) # Default to eraser
        self.selected_tool = self.ToolType.ERASER
        btn_container.addWidget(pen_button)
        btn_container.addWidget(eraser_button)
        self.formLayout.addRow(btn_container)

        # Image display area
        self.image_display_label = ClickableLabel()
        if not self._load_and_prepare_image(image_path):
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить изображение.")
            self._setup_select_sketch_view() # Go back if image fails
            return

        if self.current_pixmap:
             self.image_display_label.setPixmap(self.current_pixmap)
        self.image_display_label.setAlignment(Qt.AlignCenter)
        self.image_display_label.clicked.connect(self._handle_image_click)
        self.formLayout.addRow(self.image_display_label)

        # Action buttons
        option_buttons_layout = QHBoxLayout() # Use a layout for horizontal buttons

        rem_back_button = QPushButton("Удалить фон")
        rem_back_button.clicked.connect(self._handle_remove_background)
        option_buttons_layout.addWidget(rem_back_button)

        self.undo_button = QPushButton("Назад")
        self.undo_button.clicked.connect(self._handle_undo_remove_background)
        option_buttons_layout.addWidget(self.undo_button)
        self.undo_button.hide() # Initially hidden

        # Add the button layout to the form layout
        self.formLayout.addRow(option_buttons_layout)

        approve_final_button = QPushButton("Подтвердить")
        approve_final_button.clicked.connect(self._handle_approve_model)
        self.formLayout.addRow(approve_final_button)

    def _create_tool_button(self, icon_path: str, tool_type: ToolType) -> MyRadioButton:
        """Helper to create a tool selection radio button."""
        button = MyRadioButton()
        button.setIcon(QIcon(icon_path))
        button.setIconSize(QSize(70, 30))
        button.toggled.connect(lambda checked, t=tool_type: self._handle_tool_selection(checked, t))
        return button

    def _load_and_prepare_image(self, image_path: str) -> bool:
        """Loads an image, prepares scaled and blurred versions."""
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                log.error(f"_load_and_prepare_image: Failed to load pixmap from {image_path}\n")
                return False

            self.original_image_size = pixmap.size()
            # Use advisable_height from base class for target height
            target_height = self.advisable_height * 0.6 # Adjust ratio for image display
            # Calculate width maintaining aspect ratio
            if pixmap.height() > 0:
                target_width = pixmap.width() * target_height / pixmap.height()
            else:
                target_width = self.advisable_width * 0.8 # Fallback width calculation

            # Ensure target dimensions are valid integers
            target_width = max(1, int(target_width))
            target_height = max(1, int(target_height))

            # Calculate scale factors, avoiding division by zero
            if target_width > 0 and target_height > 0:
                self.display_scale_factors = (
                    self.original_image_size.width() / target_width,
                    self.original_image_size.height() / target_height
                )
            else:
                 FreeCAD.Console.PrintError("_load_and_prepare_image: Invalid target dimensions for scaling.\n")
                 self.display_scale_factors = None # Indicate error
                 return False

            self.original_pixmap = pixmap.scaled(target_width, target_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            if self.original_pixmap.isNull():
                 FreeCAD.Console.PrintError("_load_and_prepare_image: Scaled pixmap is null.\n")
                 return False

            if self.blurred_pixmap is None:
                self.blurred_pixmap = apply_blur_effect(self.original_pixmap.copy(), 10)
                if self.blurred_pixmap.isNull():
                    FreeCAD.Console.PrintError("_load_and_prepare_image: Blurred pixmap is null.\n")
                    # Continue without blur? Or return False?
                    # Let's try continuing without blur effect for now
                    self.blurred_pixmap = self.original_pixmap.copy() # Fallback

            self._update_display_pixmap(self.original_pixmap) # Start with the original blended over blur
            return True

        except Exception as e:
            FreeCAD.Console.PrintError(f"_load_and_prepare_image: Error loading image {image_path}: {e}\n")
            import traceback
            FreeCAD.Console.PrintError(traceback.format_exc() + "\n")
            # Reset related members on error
            self.original_pixmap = None
            self.blurred_pixmap = None
            self.current_pixmap = None
            self.original_image_size = None
            self.display_scale_factors = None
            return False

    # --- Event Handlers ---

    def _handle_sketch_selection(self, index: int):
        """Handles the selection of a sketch from the gallery."""
        if not self.selection_gallery or index >= len(self.selection_gallery.cells):
            FreeCAD.Console.PrintWarning(f"_handle_sketch_selection: Invalid index {index}\n")
            return

        self.selected_render_path = self.selection_gallery.cells[index].image_path

        for i, cell in enumerate(self.selection_gallery.cells):
            if cell and cell.label: # Check if cell and label exist
                if i == index:
                    # Apply selected style and remove effects
                    cell.label.setStyleSheet("border: 3px solid rgba(0, 160, 200, 0.9); border-radius: 15px;")
                    self._apply_effects_to_cell(cell, blur=False, opacity=1.0)
                else:
                    # Apply deselected style (no border) and add effects
                     cell.label.setStyleSheet("border: 0px;")
                     self._apply_effects_to_cell(cell, blur=True, opacity=0.5)
            else:
                 FreeCAD.Console.PrintWarning(f"_handle_sketch_selection: Cell or label missing at index {i}\n")

    def _apply_effects_to_cell(self, cell: GalleryCell, blur: bool, opacity: float):
        """
        Apply or remove blur and opacity effects to a cell's label.
        Similar to the implementation in PrepareFor2dGen.
        Args:
            cell: The GalleryCell to modify.
            blur: Whether to apply blur (True) or remove it (False).
            opacity: The desired window opacity (e.g., 1.0 for full, 0.5 for semi-transparent).
        """
        label = cell.label
        if not label:
            return

        if blur:
            current_effect = label.graphicsEffect()
            # Apply blur only if it doesn't exist or isn't already a blur effect
            if not isinstance(current_effect, QGraphicsBlurEffect):
                try:
                    blur_effect = QGraphicsBlurEffect(label)
                    blur_effect.setBlurRadius(5) # Consistent blur radius
                    label.setGraphicsEffect(blur_effect)
                except Exception as e:
                    FreeCAD.Console.PrintError(f"_apply_effects_to_cell: Error applying blur effect: {e}\n")
            # Optionally adjust existing blur radius if needed:
            # elif isinstance(current_effect, QGraphicsBlurEffect) and current_effect.blurRadius() != 5:
            #     current_effect.setBlurRadius(5)
        else:
            # Remove effect only if it exists
            if label.graphicsEffect():
                label.setGraphicsEffect(None)

        # Apply opacity
        label.setWindowOpacity(opacity)

    def _handle_tool_selection(self, checked: bool, tool_type: ToolType):
        """Handles the selection of the drawing tool."""
        if checked:
            self.selected_tool = tool_type
            FreeCAD.Console.PrintMessage(f"Tool selected: {tool_type.name}")

    def _handle_approve_render(self):
        """Checks selection and proceeds to the background removal step."""
        if self.selected_render_path is None:
            QMessageBox.warning(self, "Не выбран скетч", "Пожалуйста, выберите скетч для рендера")
            return
        # Prompt is saved via textChanged signal
        self._setup_remove_background_view(self.selected_render_path)

    def _handle_image_click(self, pos: QPoint):
        """Handles clicks on the image for drawing."""
        if not self.image_display_label or not self.current_pixmap or not self.display_scale_factors:
            FreeCAD.Console.PrintWarning("_handle_image_click: Required components missing.\n")
            return

        # Throttle clicks based on distance
        if self._click_distance(self.last_click_pos, pos) < self.MIN_CLICK_DISTANCE_DELTA:
            return
        self.last_click_pos = pos

        # Calculate coordinates in the original image space
        orig_x, orig_y = self._map_display_to_original(pos)

        if orig_x is None: # Click outside image bounds
             return

        if self.selected_tool == self.ToolType.NONE:
            QMessageBox.warning(self, "Не выбран инструмент", "Пожалуйста, выберите инструмент для работы с изображением")
            return

        # Draw on the current pixmap
        try:
            if not self.current_pixmap or self.current_pixmap.isNull():
                FreeCAD.Console.PrintError("_handle_image_click: Cannot draw on null pixmap.\n")
                return
            self.current_pixmap = self.current_pixmap.copy() # Work on a copy

            painter = QPainter(self.current_pixmap)
            if not painter.isActive():
                 FreeCAD.Console.PrintError("_handle_image_click: QPainter failed to activate.\n")
                 return

            painter.setRenderHint(QPainter.Antialiasing)
            tool_color = Qt.cyan if self.selected_tool == self.ToolType.PEN else Qt.red
            pen = QPen(tool_color, 30, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.setOpacity(0.5) # Semi-transparent drawing
            painter.drawPoint(QPoint(orig_x, orig_y)) # Draw on the display coordinates
            painter.end()

            self.image_display_label.setPixmap(self.current_pixmap)

            # Store coordinates for API call
            point = (int(orig_x*self.display_scale_factors[0]), int(orig_y*self.display_scale_factors[1]))
            if self.selected_tool == self.ToolType.PEN:
                # print(f"Adding PEN point: {point}") # Debug
                self.pen_points.append(point)
            elif self.selected_tool == self.ToolType.ERASER:
                # print(f"Adding ERASER point: {point}") # Debug
                self.erased_points.append(point)
            log.info(f"Image resolution: {self.original_pixmap.size()}")
            if self.pen_points:
                log.info(f"Pen point: {self.pen_points[-1]}")
            if self.erased_points:
                log.info(f"Eraser point: {self.erased_points[-1]}")
        except Exception as e:
             FreeCAD.Console.PrintError(f"_handle_image_click: Error during drawing: {e}\n")
             import traceback
             FreeCAD.Console.PrintError(traceback.format_exc() + "\n")


    def _handle_remove_background(self):
        """Initiates the background removal API call."""
        if not self.image_path_history:
            FreeCAD.Console.PrintWarning("_handle_remove_background: No image history.\n")
            return

        if len(self.erased_points) == 0:
            QMessageBox.warning(self, "Не выбраны точки для удаления фона", "Пожалуйста, выберите точки для удаления фона.")
            return

        if len(self.pen_points) == 0:
            QMessageBox.warning(self, "Не объект", "Пожалуйста, поставьте хотя бы одну точку на объект.")
            return

        last_image_path = self.image_path_history[-1]
        FreeCAD.Console.PrintMessage(f"_handle_remove_background: Processing {last_image_path}")
        FreeCAD.Console.PrintMessage(f"_handle_remove_background: Pen points: {self.pen_points}")
        FreeCAD.Console.PrintMessage(f"_handle_remove_background: Erase points: {self.erased_points}")
        try:
            with open(last_image_path, "rb") as f:
                image_bytes_b64 = base64.b64encode(f.read())
        except IOError as e:
             QMessageBox.critical(self, "Ошибка файла", f"Не удалось прочитать файл: {e}")
             FreeCAD.Console.PrintError(f"_handle_remove_background: Failed to read file {last_image_path}: {e}\n")
             return

        rb_input = Models.RemoveBackgroundInput(
            image_base64=image_bytes_b64,
            remove_coords=self.erased_points,
            keep_coords=self.pen_points
        )

        stored_pen_points = list(self.pen_points)
        stored_erased_points = list(self.erased_points)
        self.pen_points = []
        self.erased_points = []

        self._call_remove_background_api(rb_input, stored_pen_points, stored_erased_points)

    def _handle_undo_remove_background(self):
        """Reverts to the previous image state."""

        if len(self.image_path_history) <= 1:
            FreeCAD.Console.PrintMessage("_handle_undo_remove_background: Cannot undo initial image.")
            return # Cannot undo the original image

        self.image_path_history.pop()
        last_image_path = self.image_path_history[-1]
        FreeCAD.Console.PrintMessage(f"_handle_undo_remove_background: Reverted to {last_image_path}")

        if self._load_and_prepare_image(last_image_path):
            if self.image_display_label and self.current_pixmap:
                 self.image_display_label.setPixmap(self.current_pixmap) # Update display
        else:
             QMessageBox.warning(self, "Ошибка", "Не удалось загрузить предыдущее изображение.")
             # Potentially disable undo or try to recover

        # Reset points when undoing
        self.pen_points = []
        self.erased_points = []

        # Hide/Show undo button
        if self.undo_button:
            can_undo = len(self.image_path_history) > 1
            self.undo_button.setVisible(can_undo)
            FreeCAD.Console.PrintMessage(f"_handle_undo_remove_background: Undo button visible: {can_undo}")


    def _handle_approve_model(self):
        """Validates the final image and initiates the 3D generation API call."""
        FreeCAD.Console.PrintMessage("_handle_approve_model")
        if not self.image_path_history:
            QMessageBox.critical(self, "Ошибка", "Нет изображения для обработки.")
            self.close()
            return

        final_image_path = self.image_path_history[-1]
        FreeCAD.Console.PrintMessage(f"_handle_approve_model: Approving image {final_image_path}")

        # Check if any background removal steps were taken
        if len(self.image_path_history) == 1: # Only original image exists
             reply = QMessageBox.question(self, "Предупреждение",
                                          "Фон не был изменен с помощью инструментов. Продолжить генерацию с оригиналом?",
                                          QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
             if reply == QMessageBox.No:
                 FreeCAD.Console.PrintMessage("_handle_approve_model: User chose not to proceed with original.")
                 return

        # Save the path of the final cleaned image
        Exporting.save_prop("cleaned_image_path", final_image_path) # Save the path
        FreeCAD.Console.PrintMessage(f"_handle_approve_model: Saved cleaned_image_path: {final_image_path}")

        try:
            with open(final_image_path, "rb") as f:
                image_bytes_b64 = base64.b64encode(f.read()).decode()
        except IOError as e:
             QMessageBox.critical(self, "Ошибка файла", f"Не удалось прочитать финальный файл: {e}")
             FreeCAD.Console.PrintError(f"_handle_approve_model: Failed to read final file {final_image_path}: {e}\n")
             return

        gen3d_input = Models.Gen3dInput(image_base64=image_bytes_b64)
        self._call_generate_3d_api(gen3d_input)


    # --- API Call Methods ---

    def _call_remove_background_api(self, rb_input: Models.RemoveBackgroundInput, pen_points_used: list, erased_points_used: list):
        """Calls the background removal API asynchronously."""
        FreeCAD.Console.PrintMessage("_call_remove_background_api: Starting")
        self.auth_session.auto_login()
        if not self.auth_session.token:
            FreeCAD.Console.PrintWarning("_call_remove_background_api: Not logged in. Showing login.\n")
            self.auth_session.show_login()
            # Restore points if login failed before API call
            self.pen_points = pen_points_used
            self.erased_points = erased_points_used
            return

        self._show_waiting_message("Удаление фона", "Пожалуйста, подождите, идет удаление фона...")

        callback = lambda result, error: self._on_background_removed(
            result, error, pen_points_used, erased_points_used
        )

        FreeCAD.Console.PrintMessage("_call_remove_background_api: Running async task")
        self.auth_session.masterAPI.run_async_task(
            self.auth_session.masterAPI.remove_background_pipeline,
            callback,
            token=self.auth_session.token,
            removeBackgroundInput=rb_input
        )

    def _call_generate_3d_api(self, gen3d_input: Models.Gen3dInput):
         """Calls the 3D generation API asynchronously."""
         FreeCAD.Console.PrintMessage("_call_generate_3d_api: Starting")
         self.auth_session.auto_login()
         if not self.auth_session.token:
             FreeCAD.Console.PrintWarning("_call_generate_3d_api: Not logged in. Showing login.\n")
             self.auth_session.show_login()
             return

         self._show_waiting_message("Генерация 3d модели", "Пожалуйста, подождите, идет генерация 3d модели...")
         FreeCAD.Console.PrintMessage("_call_generate_3d_api: Running async task")
         self.auth_session.masterAPI.run_async_task(
             self.auth_session.masterAPI.generate_3d,
             self._on_generated_3d,
             token=self.auth_session.token,
             gen3dInput=gen3d_input
         )


    # --- API Callbacks ---

    def _on_background_removed(self, result: Optional[Models.RemoveBackgroundOutput], error: Optional[Exception], pen_points_used: list, erased_points_used: list):
        """Handles the result of the background removal API call."""

        self._hide_waiting_message()

        if error:
            error_str = str(error)
            FreeCAD.Console.PrintError(f"_on_background_removed: Background removal error: {error_str}\n")
            if len(error_str) > 500:
                 error_str = error_str[:250] + "..." + error_str[-250:]
            QMessageBox.warning(self, "Ошибка", f"Ошибка при удалении фона:{error_str}")
            # Restore drawing points as the API call failed
            self.pen_points = pen_points_used
            self.erased_points = erased_points_used
            FreeCAD.Console.PrintMessage("_on_background_removed: Restored points due to error.")
            return

        if not result or not result.image_base64:
            FreeCAD.Console.PrintWarning("_on_background_removed: No result or image_base64 received.\n")
            QMessageBox.warning(self, "Ошибка", "Не удалось получить результат удаления фона.")
            # Restore drawing points as the API call failed
            self.pen_points = pen_points_used
            self.erased_points = erased_points_used
            FreeCAD.Console.PrintMessage("_on_background_removed: Restored points due to no result.")
            return

        FreeCAD.Console.PrintMessage("_on_background_removed: Success. Saving result.")
        # API call succeeded, points were used, keep the cleared lists (self.pen_points = [])
        try:
            output_dir = os.path.join(Exporting.get_project_path(), "background_removed")
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            new_image_path = os.path.join(output_dir, f"{timestamp}_removed.png")
            FreeCAD.Console.PrintMessage(f"_on_background_removed: Saving to {new_image_path}")

            image_data = base64.b64decode(result.image_base64)
            if not image_data:
                 raise ValueError("Decoded image data is empty")

            with open(new_image_path, "wb") as f:
               f.write(image_data)

            # Update UI
            self.image_path_history.append(new_image_path)
            if self._load_and_prepare_image(new_image_path):
                if self.image_display_label and self.current_pixmap:
                     self.image_display_label.setPixmap(self.current_pixmap)
                if self.undo_button:
                     self.undo_button.show() # Show undo now that we have history
                     FreeCAD.Console.PrintMessage("_on_background_removed: Undo button shown.")
            else:
                 QMessageBox.warning(self, "Ошибка", "Не удалось загрузить обработанное изображение.")
                 self.image_path_history.pop() # Remove the failed path

        except (IOError, base64.binascii.Error, ValueError, Exception) as e:
             FreeCAD.Console.PrintError(f"_on_background_removed: Error saving/loading processed image: {e}\n")
             import traceback
             FreeCAD.Console.PrintError(traceback.format_exc() + "\n")
             QMessageBox.critical(self, "Ошибка", f"Ошибка при сохранении/загрузке результата: {e}")

    def _on_generated_3d(self, result: Optional[Models.Gen3dId], error: Optional[Exception]):
        """Handles the result of the 3D generation API call."""
        FreeCAD.Console.PrintMessage("_on_generated_3d: Received callback")
        self._hide_waiting_message()

        if error:
            FreeCAD.Console.PrintError(f"_on_generated_3d: 3D Generation error: {error}\n")
            QMessageBox.warning(self, "Ошибка", f"Ошибка при генерации 3d модели: {error}")
            self.onObjIdReceived(None, error) # Pass error back
            return

        if not result or not result.obj_id:
            FreeCAD.Console.PrintWarning("_on_generated_3d: No result or obj_id received.\n")
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации 3d модели: Не получен ID объекта.")
            self.onObjIdReceived(None, "No result or obj_id") # Pass info back
            return

        FreeCAD.Console.PrintMessage(f"_on_generated_3d: Success. Received obj_id: {result.obj_id}")
        QMessageBox.information(self, "Успешно", "Запрос на генерацию 3D модели успешно отправлен.")
        self.onObjIdReceived(result, None) # Pass success result (obj_id) back
        self.close() # Close the preparation window on success


    # --- Utility Methods --- 

    def _update_display_pixmap(self, new_foreground_pixmap: QPixmap):
         """Blends the given foreground pixmap with the blurred background and updates the display."""
         # FreeCAD.Console.PrintMessage("_update_display_pixmap: Updating")
         if self.blurred_pixmap and not new_foreground_pixmap.isNull():
             try:

                foreground_image = new_foreground_pixmap.toImage()
                # Save foreground image for testing
                try:
                    save_path = os.path.expanduser("~/downloads/blur_test")
                    if not os.path.exists(save_path):
                        os.makedirs(save_path)
                    foreground_image.save(os.path.join(save_path, "foreground.png"))
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Failed to save foreground test image: {e}\n")
                if foreground_image.isNull():
                    FreeCAD.Console.PrintWarning("_update_display_pixmap: Foreground image for blending is null.\n")
                    self.current_pixmap = new_foreground_pixmap # Fallback
                    return

                blurred_image = self.blurred_pixmap
                # Save blurred image for testing
                try:
                    save_path = os.path.expanduser("~/downloads/blur_test")
                    if not os.path.exists(save_path):
                        os.makedirs(save_path)
                    blurred_image.save(os.path.join(save_path, "blurred.png"))
                except Exception as e:
                    FreeCAD.Console.PrintError(f"Failed to save blurred test image: {e}\n")
                if blurred_image.isNull():
                    FreeCAD.Console.PrintWarning("_update_display_pixmap: Blurred background image is null.\n")
                    self.current_pixmap = new_foreground_pixmap # Fallback
                    return

                result_image = blend_images(blurred_image, foreground_image)
                if result_image.isNull():
                    FreeCAD.Console.PrintWarning("_update_display_pixmap: Blending resulted in a null image.\n")
                    self.current_pixmap = new_foreground_pixmap # Fallback
                else:
                    self.current_pixmap = QPixmap.fromImage(result_image)

             except Exception as e:
                 FreeCAD.Console.PrintError(f"_update_display_pixmap: Error blending images: {e}\n")
                 self.current_pixmap = new_foreground_pixmap # Fallback to non-blended
         else:
              # FreeCAD.Console.PrintMessage("_update_display_pixmap: Using foreground directly (no blur or invalid input).")
              self.current_pixmap = new_foreground_pixmap # Use directly if no blur or invalid input


    def _map_display_to_original(self, display_pos: QPoint) -> Tuple[Optional[float], Optional[float]]:
        """Maps a point from the display label coordinates to the original image coordinates."""
        if not self.image_display_label or not self.current_pixmap or self.current_pixmap.isNull() \
           or not self.display_scale_factors or not self.original_image_size:
            return None, None

        pixmap_size = self.current_pixmap.size()
        widget_size = self.image_display_label.size()

        offset_x = max(0, (widget_size.width() - pixmap_size.width()) // 2)
        
        offset_y = max(0, (widget_size.height() - pixmap_size.height()) // 2)
        
        pixmap_x = display_pos.x() - offset_x
        pixmap_y = display_pos.y() - offset_y

        if not (0 <= pixmap_x < pixmap_size.width() and 0 <= pixmap_y < pixmap_size.height()):
            return None, None

        original_x = pixmap_x #* self.display_scale_factors[0]
        original_y = pixmap_y #* self.display_scale_factors[1]

        original_x = max(0.0, min(original_x, float(self.original_image_size.width() - 1)))
        original_y = max(0.0, min(original_y, float(self.original_image_size.height() - 1)))

        return original_x, original_y


    def _click_distance(self, p1: Optional[QPoint], p2: QPoint) -> float:
        """Calculates the Euclidean distance between two QPoints."""
        if p1 is None:
            return float('inf')
        return ((p1.x() - p2.x())**2 + (p1.y() - p2.y())**2)**0.5

    def _show_waiting_message(self, title: str, text: str):
        """Displays a non-closable waiting message box."""
        FreeCADGui.updateGui()
        if self.waiting_message_box:
            self.waiting_message_box.hide()
            self.waiting_message_box.deleteLater()
        parent_widget = FreeCADGui.getMainWindow() if FreeCADGui.getMainWindow() else self # Fallback parent
        self.waiting_message_box = QMessageBox(QMessageBox.Information, title, text, QMessageBox.NoButton, parent_widget)
        self.waiting_message_box.setStandardButtons(QMessageBox.NoButton)
        self.waiting_message_box.setWindowModality(Qt.ApplicationModal)
        self.waiting_message_box.show()
        FreeCADGui.updateGui()

    def _hide_waiting_message(self):
        """Hides the waiting message box if it's visible."""
        if self.waiting_message_box:
            self.waiting_message_box.hide()
            self.waiting_message_box.deleteLater()
            self.waiting_message_box = None
        FreeCADGui.updateGui()

    def closeEvent(self, event):
        """Ensure cleanup happens when the window is closed."""
        FreeCAD.Console.PrintMessage(f"PrepareFor3dGen closing event for {id(self)}")
        self._hide_waiting_message()
        self.original_pixmap = None
        self.blurred_pixmap = None
        self.current_pixmap = None
        # Disconnect signals to prevent issues after close?
        # if self.prompt_edit:
        #     try: self.prompt_edit.textChanged.disconnect() except RuntimeError: pass

        # Explicitly delete potentially large widgets if needed, though deleteLater in _clear_layout helps
        if self.selection_gallery:
            self.selection_gallery.deleteLater() # Schedule gallery for deletion
            self.selection_gallery = None
        if self.image_display_label:
            self.image_display_label.deleteLater()
            self.image_display_label = None

        super().closeEvent(event)

    def __del__(self):
        FreeCAD.Console.PrintMessage(f"PrepareFor3dGen instance {id(self)} being deleted.")

