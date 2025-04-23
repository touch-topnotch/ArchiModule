import base64
import time
from typing import Callable, Optional, Any, List

import FreeCADGui
import FreeCAD
from PySide.QtCore import Qt
from PySide.QtWidgets import (QLabel, QSlider, QLineEdit, QGraphicsOpacityEffect,
                              QGraphicsBlurEffect, QPushButton, QMessageBox, QWidget,
                              QTextEdit)
from Tools.ProjectContext.Pipelines.FormWindow import FormWindow
from Tools import Exporting, Models
from Tools.GalleryUtils import GalleryWidget, GalleryStyle, GalleryCell


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
    
    def __init__(self, sketches: GalleryWidget, onApprove: Callable[[Models.Gen2dInput], None], parent: QWidget = None):
        """
        Initialize the PrepareFor2dGen dialog.
        
        Args:
            sketches: Gallery widget containing sketch images to choose from
            onApprove: Callback function to call when user approves generation
            parent: Parent widget
        """
        
        super().__init__(title=UIStrings.WINDOW_TITLE, parent=parent)

        self.onApprove = onApprove
        self.selected_sketch_path: Optional[str] = None
        self.input_sketches_widget = sketches
        self.project_model = Exporting.load()
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
        title_label.setAlignment(Qt.AlignCenter)
        
        subtitle_label = QLabel(UIStrings.SUBTITLE)
        subtitle_label.setStyleSheet("font-size: 12pt;")
        subtitle_label.setAlignment(Qt.AlignCenter)
        
        self.formLayout.addRow(title_label)
        self.formLayout.addRow(subtitle_label)
        
    def _setup_gallery(self):
        """Set up the gallery of sketches to choose from."""
        style = GalleryStyle(
            number_of_cols=3, 
            min_dock_height=int(self.advisable_height * 0.3), 
            max_dock_height=int(self.advisable_height * 0.5),
            width_of_cell=int(self.advisable_width / 3.2), 
            gap=10
        )
        
        self.selection_gallery = GalleryWidget(style)
        self.selection_gallery.add_cells([cell.copy() for cell in self.input_sketches_widget.cells])
        
        for cell in self.selection_gallery.cells:
            cell.action.connect(lambda bound_cell=cell: self._handle_sketch_selection(bound_cell.index))
            
        self.formLayout.addRow(self.selection_gallery)
        
    def _setup_controls(self):
        """Set up the control inputs (slider, prompts)."""
        self.realism_slider = QSlider(Qt.Horizontal)
        self.realism_slider.setRange(0, 100)
        initial_slider_value = getattr(self.project_model, 'slider_value', 0.5)
        self.realism_slider.setValue(int(initial_slider_value * 100))
        self.formLayout.setSpacing(10)
        self.formLayout.addRow(UIStrings.SIMILARITY_LABEL, self.realism_slider)
        
        self.prompt_label = QLabel(UIStrings.PROJECT_CONTEXT_LABEL)
        self.formLayout.addRow(self.prompt_label)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setText(getattr(self.project_model, 'prompt', ''))
        self.formLayout.addRow(self.prompt_edit)
        
        self.n_prompt_label = QLabel(UIStrings.NEGATIVE_PROMPT_LABEL)
        self.formLayout.addRow(self.n_prompt_label)
        
        self.n_prompt_edit = QTextEdit()
        self.n_prompt_edit.setMinimumHeight(80)
        self.n_prompt_edit.setText(getattr(self.project_model, 'negative_prompt', ''))
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
        self.selected_sketch_path = self.selection_gallery.cells[index].image_path
        
        selected_cell = self.selection_gallery.cells[index]
        selected_cell.label.setStyleSheet("border: 3px solid rgba(0, 160, 200, 0.9); border-radius: 15px;")
        selected_cell.label.setGraphicsEffect(None)
        selected_cell.label.setWindowOpacity(1.0)
        
        for i, cell in enumerate(self.selection_gallery.cells):
            if i != index:
                self._apply_effects_to_cell(cell, blur=True, opacity=0.5)
            else:
                self._apply_effects_to_cell(cell, blur=False, opacity=1.0)
    
    def _apply_effects_to_cell(self, cell, blur: bool, opacity: float):
        """
        Apply or remove blur and opacity effects to a cell's label.
        
        Args:
            cell: The GalleryCell to modify.
            blur: Whether to apply blur (True) or remove it (False).
            opacity: The desired window opacity (e.g., 1.0 for full, 0.5 for semi-transparent).
        """
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
        

        current_prompt = self.prompt_edit.toPlainText().strip()

        current_neg_prompt = self.n_prompt_edit.toPlainText().strip()

        current_slider_val = self.realism_slider.value() / 100.0

        Exporting.save_props({
            "prompt": current_prompt,
            "negative_prompt": current_neg_prompt,
            "slider_value": current_slider_val
        })

        gen2d_input = Models.Gen2dInput(
            image_base64=image_bytes_b64,
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
            QMessageBox.warning(self, UIStrings.NO_SKETCH_TITLE, UIStrings.NO_SKETCH_TEXT)
            return False
            
        prompt_text = self.prompt_edit.toPlainText().strip()
        if not prompt_text:
            QMessageBox.warning(self, UIStrings.NO_CONTEXT_TITLE, UIStrings.NO_CONTEXT_TEXT)
            return False
            
        neg_prompt_text = self.n_prompt_edit.toPlainText().strip()
        try:
            prompt_text.encode('ascii')
            neg_prompt_text.encode('ascii')
        except UnicodeEncodeError as e:
            bad_char = e.object[e.start:e.end]
            QMessageBox.warning(self, UIStrings.INVALID_INPUT_TITLE, f"{UIStrings.INVALID_INPUT_TEXT} Символ: '{bad_char}'")
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
            QMessageBox.critical(self, "Ошибка файла", f"Не удалось найти файл изображения: {self.selected_sketch_path}")
            return None
        except IOError as e:
            QMessageBox.critical(self, "Ошибка файла", f"Не удалось прочитать файл изображения: {e}")
            return None
