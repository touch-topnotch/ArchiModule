"""
Prepare for 2D Generation Module.

This module handles the UI and state management for preparing
data to send to the 2D generation API.
"""
import base64
import time
from typing import Callable, Optional

import FreeCADGui
import FreeCAD
from PySide.QtCore import Qt
from PySide.QtWidgets import (
    QLabel, QSlider, QGraphicsOpacityEffect,
    QGraphicsBlurEffect, QPushButton, QMessageBox, QWidget,
    QTextEdit
)

from tools.project_context.pipelines.form_window import FormWindow
from tools import exporting, models
from tools.project_context.utils.gallery_utils import GalleryWidget, GalleryStyle, GalleryCell


class UIStrings:
    """Constant strings used in the UI."""
    WINDOW_TITLE = "Select Best Sketch for 2D Generation"
    TITLE = "Пожалуйста, выберите лучший скетч"
    SUBTITLE = "По большей части от него будет произведена генерация рендеров"
    SIMILARITY_LABEL = "Сходство "
    PROJECT_CONTEXT_LABEL = "Контекст проекта"
    NEGATIVE_PROMPT_LABEL = "Что вы не хотите видеть в рендере"
    CONFIRM_BUTTON = "Подтвердить"
    
    # Messages
    NO_SKETCH_TITLE = "Не выбран скетч"
    NO_SKETCH_TEXT = "Пожалуйста, выберите скетч для рендера"
    NO_CONTEXT_TITLE = "Нет контекста"
    NO_CONTEXT_TEXT = "Опишите это здание. Добавьте информацию об окружении, ландшафте, истории, контексте здания"
    INVALID_INPUT_TITLE = "Неккоректная запись"
    INVALID_INPUT_TEXT = "Некорректные запись: "
    SUCCESS_TITLE = "Готово"
    SUCCESS_TEXT = "Скоро рендеры будут готовы) Можете приступать к разработке проекта"


class PrepareFor2dGen(FormWindow):
    """ 
    Dialog window for preparing 2D generation.
    Allows selecting a sketch, setting parameters, and confirming generation.
    Inherits basic window setup and sizing from FormWindow.
    """
    
    def __init__(
        self,
        sketches: GalleryWidget,
        onApprove: Callable[[models.Gen2dInput], None],
        parent: Optional[QWidget] = None
    ):
        """
        Initialize the PrepareFor2dGen dialog.
        
        Args:
            sketches: Gallery widget containing sketch images to choose from
            onApprove: Callback function to call when user approves generation
            parent: Parent widget
        """
        super().__init__(title=UIStrings.WINDOW_TITLE, parent=parent)  # type: ignore[arg-type]

        self.onApprove = onApprove
        self.selected_sketch_path: Optional[str] = None
        self.input_sketches_widget = sketches
        self.project_model = exporting.load()
        self.selection_gallery: Optional[GalleryWidget] = None
        self.prompt_edit: Optional[QTextEdit] = None
        self.n_prompt_edit: Optional[QTextEdit] = None
        
        self._setup_header()
        self._setup_gallery()
        self._setup_controls()
        self._setup_buttons()
        
    def _setup_header(self):
        """Set up the header section with title and subtitle."""
        title_label = QLabel(UIStrings.TITLE)
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        subtitle_label = QLabel(UIStrings.SUBTITLE)
        subtitle_label.setStyleSheet("font-size: 12pt;")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.formLayout.addRow(title_label)
        self.formLayout.addRow(subtitle_label)
        
    def _setup_gallery(self):
        """Set up the gallery of sketches to choose from.
        
        Sizing logic ensures all 3 images fit BOTH horizontally AND vertically:
        1. Calculate max cell width to fit 3 images by width
        2. Calculate max cell width to fit 3 images by height (considering aspect ratio)
        3. Take the MINIMUM to guarantee all 3 images are fully visible
        """
        gap = 10
        num_images = 3
        number_of_cols = 3
        
        # Calculate available space for the gallery
        available_width = self.advisable_width - 40  # margins
        available_height = int(self.advisable_height * 0.5)  # gallery takes ~50% of window height
        
        # Find the tallest aspect ratio among input images (height/width)
        max_aspect_ratio = 1.0  # default to square
        for cell in self.input_sketches_widget.cells:
            if hasattr(cell, 'pixmap') and cell.pixmap and not cell.pixmap.isNull():
                w = cell.pixmap.width()
                h = cell.pixmap.height()
                if w > 0:
                    aspect = h / w
                    max_aspect_ratio = max(max_aspect_ratio, aspect)
        
        # Calculate max cell width to fit 3 images horizontally
        max_width_by_cols = int((available_width - gap * (number_of_cols - 1)) / number_of_cols)
        
        # Calculate max cell width to fit images vertically
        # If we have 3 cols, images stack in 1 row, so height needed = cell_width * aspect_ratio
        # available_height >= cell_width * max_aspect_ratio
        # cell_width <= available_height / max_aspect_ratio
        max_width_by_height = int(available_height / max_aspect_ratio) if max_aspect_ratio > 0 else max_width_by_cols
        
        # Take MINIMUM to ensure images fit BOTH ways
        cell_width = min(max_width_by_cols, max_width_by_height)
        
        # Calculate actual gallery height based on cell size
        estimated_cell_height = int(cell_width * max_aspect_ratio)
        min_dock_height = estimated_cell_height + gap * 2
        max_dock_height = max(min_dock_height, available_height)
        
        style = GalleryStyle(
            number_of_cols=number_of_cols, 
            min_dock_height=min_dock_height, 
            max_dock_height=max_dock_height,
            width_of_cell=cell_width, 
            gap=gap
        )
        
        self.selection_gallery = GalleryWidget(style)
        self.selection_gallery.add_cells([cell.copy() for cell in self.input_sketches_widget.cells])
        
        for cell in self.selection_gallery.cells:
            if cell.index is not None:
                cell.action.connect(
                    lambda bound_cell=cell: self._handle_sketch_selection(bound_cell.index) 
                    if bound_cell.index is not None else None
                )
            
        self.formLayout.addRow(self.selection_gallery)
        
    def _setup_controls(self):
        """Set up the control inputs (slider, prompts)."""
        self.realism_slider = QSlider(Qt.Orientation.Horizontal)
        self.realism_slider.setRange(0, 100)
        initial_slider_value = getattr(self.project_model, 'slider_value', 0.5)
        self.realism_slider.setValue(int(initial_slider_value * 100))
        self.formLayout.setSpacing(10)
        self.formLayout.addRow(UIStrings.SIMILARITY_LABEL, self.realism_slider)
        
        self.prompt_label = QLabel(UIStrings.PROJECT_CONTEXT_LABEL)
        self.formLayout.addRow(self.prompt_label)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setPlainText(getattr(self.project_model, 'prompt', ''))
        self.formLayout.addRow(self.prompt_edit)
        
        self.n_prompt_label = QLabel(UIStrings.NEGATIVE_PROMPT_LABEL)
        self.formLayout.addRow(self.n_prompt_label)
        
        self.n_prompt_edit = QTextEdit()
        self.n_prompt_edit.setMinimumHeight(80)
        self.n_prompt_edit.setPlainText(getattr(self.project_model, 'negative_prompt', ''))
        self.formLayout.addRow(self.n_prompt_edit)
        
    def _setup_buttons(self):
        """Set up the action buttons."""
        self.approve_button = QPushButton(UIStrings.CONFIRM_BUTTON)
        self.approve_button.clicked.connect(self._handle_approve)
        self.formLayout.addRow(self.approve_button)
    
    def _handle_sketch_selection(self, index: int):
        """
        Handle selection of a sketch from the gallery.
        
        Args:
            index: Index of the selected sketch
        """
        if not self.selection_gallery or index >= len(self.selection_gallery.cells):
            print(f"Warning: Invalid index {index} for sketch selection gallery.")
            return
        
        selected_cell = self.selection_gallery.cells[index]
        if hasattr(selected_cell, 'image_path'):
            self.selected_sketch_path = selected_cell.image_path  # type: ignore[attr-defined]
        
        if hasattr(selected_cell, 'label'):
            selected_cell.label.setStyleSheet(
                "border: 3px solid rgba(0, 160, 200, 0.9); border-radius: 15px;"
            )  # type: ignore[attr-defined]
            selected_cell.label.setGraphicsEffect(None)  # type: ignore[attr-defined]
            selected_cell.label.setWindowOpacity(1.0)  # type: ignore[attr-defined]
        
        for i, cell in enumerate(self.selection_gallery.cells):
            if i != index:
                self._apply_effects_to_cell(cell, blur=True, opacity=0.5)
            else:
                self._apply_effects_to_cell(cell, blur=False, opacity=1.0)
    
    def _apply_effects_to_cell(self, cell: GalleryCell, blur: bool, opacity: float):
        """
        Apply or remove blur and opacity effects to a cell's label.
        
        Args:
            cell: The GalleryCell to modify.
            blur: Whether to apply blur (True) or remove it (False).
            opacity: The desired window opacity (e.g., 1.0 for full, 0.5 for semi-transparent).
        """
        if not hasattr(cell, 'label'):
            return
            
        label = cell.label
        if blur:
            current_effect = label.graphicsEffect()
            if not isinstance(current_effect, QGraphicsBlurEffect):
                blur_effect = QGraphicsBlurEffect(label)
                blur_effect.setBlurRadius(5)
                label.setGraphicsEffect(blur_effect)
            elif current_effect.blurRadius() != 5:
                current_effect.setBlurRadius(5)
            label.setStyleSheet("border: 0px;")
        else:
            label.setGraphicsEffect(None)
        
        label.setWindowOpacity(opacity)

    def _handle_approve(self):
        """
        Validate inputs and call onApprove callback with generation parameters.
        """
        if not self._validate_inputs():
            FreeCAD.Console.PrintError("_handle_approve: Invalid inputs. Not calling onApprove.\n")
            return
            
        try:
            image_bytes_b64 = self._encode_selected_image()
            if image_bytes_b64 is None:
                QMessageBox.critical(self, "Ошибка кодирования", "Не удалось закодировать изображение")
                FreeCAD.Console.PrintError("\n_handle_approve: Failed to encode selected image.\n")
                return
        except Exception as e:
            QMessageBox.critical(self, "Ошибка кодирования", f"Не удалось закодировать изображение: {e}")
            FreeCAD.Console.PrintError(f"\n_handle_approve: Failed to encode selected image: {e}\n")
            return
        
        if not self.prompt_edit or not self.n_prompt_edit:
            QMessageBox.critical(self, "Ошибка", "Внутренняя ошибка: элементы UI не инициализированы")
            return

        current_prompt = self.prompt_edit.toPlainText().strip()
        current_neg_prompt = self.n_prompt_edit.toPlainText().strip()
        current_slider_val = self.realism_slider.value() / 100.0

        exporting.save_props({
            "prompt": current_prompt,
            "negative_prompt": current_neg_prompt,
            "slider_value": current_slider_val
        })

        gen2d_input = models.Gen2dInput(
            image_base64=image_bytes_b64.decode('utf-8'),
            prompt=current_prompt,
            control_strength=current_slider_val,
            negative_prompt=current_neg_prompt,
            seed=int(time.time()) % 10000
        )
        QMessageBox.information(self, UIStrings.SUCCESS_TITLE, UIStrings.SUCCESS_TEXT)
        
        try:
            self.onApprove(gen2d_input)
        except Exception as e:
            print(f"Error during onApprove callback: {e}")
            QMessageBox.critical(self, "Ошибка коллбэка", f"Произошла ошибка при вызове обработчика: {e}")
        
        self.close()
    
    def _validate_inputs(self) -> bool:
        """
        Validate all user inputs.
        
        Returns:
            True if all inputs are valid, False otherwise
        """
        if self.selected_sketch_path is None:
            FreeCAD.Console.PrintWarning("_validate_inputs: No sketch selected\n")
            QMessageBox.warning(self, UIStrings.NO_SKETCH_TITLE, UIStrings.NO_SKETCH_TEXT)
            return False
        
        if not self.prompt_edit or not self.n_prompt_edit:
            FreeCAD.Console.PrintWarning("_validate_inputs: UI elements not initialized\n")
            QMessageBox.warning(self, "Ошибка", "Внутренняя ошибка: элементы UI не инициализированы")
            return False
            
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            FreeCAD.Console.PrintWarning("_validate_inputs: Empty prompt\n")
            QMessageBox.warning(self, UIStrings.NO_CONTEXT_TITLE, UIStrings.NO_CONTEXT_TEXT)
            return False
        
        # Validate that text can be encoded as UTF-8 (supports all languages including Russian)
        neg_prompt_text = self.n_prompt_edit.toPlainText().strip()
        try:
            prompt_text.encode('utf-8')
            neg_prompt_text.encode('utf-8')
        except UnicodeEncodeError as e:
            bad_char = e.object[e.start:e.end]
            FreeCAD.Console.PrintWarning(f"_validate_inputs: Invalid character '{bad_char}'\n")
            QMessageBox.warning(
                self, UIStrings.INVALID_INPUT_TITLE, 
                f"{UIStrings.INVALID_INPUT_TEXT} Слово: '{bad_char}'"
            )
            return False
            
        return True
    
    def _encode_selected_image(self) -> Optional[bytes]:
        """
        Encode the selected sketch image as base64.
        
        Returns:
            Base64 encoded image bytes, or None if an error occurs.
        """
        if not self.selected_sketch_path:
            QMessageBox.critical(self, "Ошибка", "Внутренняя ошибка: Изображение не выбрано для кодирования.")
            return None
        try:
            with open(self.selected_sketch_path, "rb") as f:
                return base64.b64encode(f.read())
        except FileNotFoundError:
            QMessageBox.critical(
                self, "Ошибка файла", 
                f"Не удалось найти файл изображения: {self.selected_sketch_path}"
            )
            return None
        except IOError as e:
            QMessageBox.critical(self, "Ошибка файла", f"Не удалось прочитать файл изображения: {e}")
            return None

