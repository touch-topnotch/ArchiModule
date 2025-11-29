"""
Prepare for Video Generation Module.

This module handles the UI and state management for preparing
data to send to the video generation API.
Allows selecting Start and End frames from sketches and 2D generations.
"""
import base64
from typing import Optional, Callable, List

import FreeCAD
from PySide.QtCore import Qt, Signal
from PySide.QtWidgets import (
    QLabel, QPushButton, QMessageBox, QWidget,
    QTextEdit, QVBoxLayout, QHBoxLayout
)
from PySide.QtGui import QPixmap

from tools.project_context.pipelines.form_window import FormWindow
from tools import exporting, models
from tools.project_context.utils.gallery_utils import GalleryWidget, GalleryCell, GalleryStyle, ImageCell
import tools.log as log


class UIStrings:
    """Constant strings used in the UI."""
    WINDOW_TITLE = "Генерация видео"
    
    # Frame selection
    TITLE = "Выберите кадры для генерации видео"
    SUBTITLE = "Выберите начальный и конечный кадры из скетчей или генераций"
    START_FRAME = "Начальный кадр"
    END_FRAME = "Конечный кадр"
    SELECT_BUTTON = "Выбрать"
    
    # Prompts
    PROMPT_LABEL = "Описание видео"
    PROMPT_PLACEHOLDER = "Опишите, что должно происходить в видео..."
    NEGATIVE_PROMPT_LABEL = "Что не должно быть в видео"
    NEGATIVE_PROMPT_PLACEHOLDER = "Укажите, чего следует избегать..."
    
    # Buttons
    CREATE_BUTTON = "Создать видео"
    CANCEL_BUTTON = "Отмена"
    CLOSE_BUTTON = "Закрыть"
    CONFIRM_BUTTON = "Подтвердить"
    
    # Messages
    NO_START_FRAME = "Не выбран начальный кадр"
    NO_END_FRAME = "Не выбран конечный кадр"
    NO_FRAMES_TEXT = "Пожалуйста, выберите оба кадра для генерации видео"
    SUCCESS_TITLE = "Готово"
    SUCCESS_TEXT = "Запрос на генерацию видео отправлен. Это займёт около 2 минут."
    ERROR_TITLE = "Ошибка"


# VideoGenInput is imported from tools.models


class FrameSelectionWindow(QWidget):
    """Window for selecting a frame (Start or End) from available images."""
    
    def __init__(
        self, 
        frame_type: str,  # "start" or "end"
        all_images: List[GalleryCell],
        parent=None, 
        on_image_selected: Optional[Callable[[str, str], None]] = None
    ):
        super().__init__(parent)
        
        self.frame_type = frame_type
        self.selected_image_path: Optional[str] = None
        self.all_images = all_images
        self.on_image_selected = on_image_selected
        
        # Window setup
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        frame_name = UIStrings.START_FRAME if frame_type == "start" else UIStrings.END_FRAME
        self.setWindowTitle(f"Выбор - {frame_name}")
        self.setMinimumSize(650, 550)
        self.setMaximumSize(850, 750)
        
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
            }
        """)
        
        self._center_window()
        self._setup_ui()
    
    def _center_window(self):
        """Centers the window relative to parent."""
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
    
    def _setup_ui(self):
        """Sets up the frame selection interface."""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(main_layout)
        
        # Title
        frame_name = UIStrings.START_FRAME if self.frame_type == "start" else UIStrings.END_FRAME
        title = QLabel(f"Выберите изображение для: {frame_name}")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Gallery
        self.gallery_style = GalleryStyle(
            number_of_cols=3,
            min_dock_height=250,
            max_dock_height=400,
            width_of_cell=140,
            gap=10
        )
        
        self.gallery_widget = GalleryWidget(self.gallery_style)
        self.gallery_widget.add_cells([cell.copy() for cell in self.all_images])
        
        # Connect cell actions
        for cell in self.gallery_widget.cells:
            if cell.index is not None:
                cell.action.connect(
                    lambda bound_cell=cell: self._handle_image_selection(bound_cell.index) 
                    if bound_cell.index is not None else None
                )
        
        main_layout.addWidget(self.gallery_widget)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        cancel_button = QPushButton(UIStrings.CANCEL_BUTTON)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #666666;
                border: 1px solid #888888;
                border-radius: 5px;
                padding: 10px 20px;
                color: #ffffff;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #777777;
            }
        """)
        cancel_button.clicked.connect(self.close)
        button_layout.addWidget(cancel_button)
        
        confirm_button = QPushButton(UIStrings.CONFIRM_BUTTON)
        confirm_button.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                border: 1px solid #0099dd;
                border-radius: 5px;
                padding: 10px 20px;
                color: #ffffff;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0088bb;
            }
        """)
        confirm_button.clicked.connect(self._handle_confirm)
        button_layout.addWidget(confirm_button)
        
        main_layout.addLayout(button_layout)
    
    def _handle_image_selection(self, index: int):
        """Handles selection of an image from the gallery."""
        if not self.gallery_widget or index >= len(self.gallery_widget.cells):
            return
        
        selected_cell = self.gallery_widget.cells[index]
        if hasattr(selected_cell, 'image_path'):
            self.selected_image_path = selected_cell.image_path
            log.debug(f"Selected {self.frame_type} frame: {self.selected_image_path}")
            
            # Update visual selection
            for i, cell in enumerate(self.gallery_widget.cells):
                if cell and hasattr(cell, 'label'):
                    if i == index:
                        cell.label.setStyleSheet(
                            "border: 3px solid rgba(0, 160, 200, 0.9); border-radius: 15px;"
                        )
                    else:
                        cell.label.setStyleSheet("border: 0px;")
    
    def _handle_confirm(self):
        """Confirms selection and closes window."""
        if self.selected_image_path:
            log.debug(f"Confirmed {self.frame_type} frame: {self.selected_image_path}")
            
            if self.on_image_selected:
                self.on_image_selected(self.frame_type, self.selected_image_path)
            
            self.close()
        else:
            QMessageBox.warning(
                self, 
                UIStrings.ERROR_TITLE, 
                "Пожалуйста, выберите изображение"
            )


class FramePreviewWidget(QWidget):
    """Widget showing a frame preview with select button."""
    
    clicked = Signal(str)  # Emits frame_type when clicked
    
    def __init__(self, frame_type: str, label_text: str, parent=None):
        super().__init__(parent)
        self.frame_type = frame_type
        self.image_path: Optional[str] = None
        
        self._setup_ui(label_text)
    
    def _setup_ui(self, label_text: str):
        """Setup the widget UI."""
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)
        
        # Label
        self.title_label = QLabel(label_text)
        self.title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #ffffff;")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Image preview
        self.image_label = QLabel()
        self.image_label.setFixedSize(180, 180)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #3d3d3d;
                border: 2px dashed #666666;
                border-radius: 10px;
            }
        """)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setText("Нет изображения")
        layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Select button
        self.select_button = QPushButton(UIStrings.SELECT_BUTTON)
        self.select_button.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                color: white;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0088bb;
            }
        """)
        self.select_button.clicked.connect(lambda: self.clicked.emit(self.frame_type))
        layout.addWidget(self.select_button, alignment=Qt.AlignmentFlag.AlignCenter)
    
    def set_image(self, image_path: str):
        """Set the preview image."""
        self.image_path = image_path
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                170, 170,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
            self.image_label.setStyleSheet("""
                QLabel {
                    background-color: #3d3d3d;
                    border: 2px solid #00a0c8;
                    border-radius: 10px;
                }
            """)


class PrepareForVideoGen(FormWindow):
    """
    Window for preparing video generation.
    Allows selecting Start/End frames and entering prompts.
    """
    
    def __init__(
        self,
        sketches: GalleryWidget,
        generations_2d: GalleryWidget,
        on_approve: Callable[[models.VideoGenInput], None],
        parent: Optional[QWidget] = None
    ):
        super().__init__(title=UIStrings.WINDOW_TITLE, parent=parent)
        
        self.on_approve = on_approve
        self.sketches = sketches
        self.generations_2d = generations_2d
        self.project_model = exporting.load()
        
        # Selected frames
        self.start_frame_path: Optional[str] = None
        self.end_frame_path: Optional[str] = None
        
        # UI elements
        self.start_preview: Optional[FramePreviewWidget] = None
        self.end_preview: Optional[FramePreviewWidget] = None
        self.prompt_edit: Optional[QTextEdit] = None
        self.n_prompt_edit: Optional[QTextEdit] = None
        self.open_windows: dict[str, FrameSelectionWindow] = {}
        
        self._setup_ui()
    
    def _get_all_images(self) -> List[GalleryCell]:
        """Combine all images from sketches and 2D generations."""
        all_cells = []
        
        # Add sketches
        if self.sketches and self.sketches.cells:
            all_cells.extend([cell.copy() for cell in self.sketches.cells])
        
        # Add 2D generations
        if self.generations_2d and self.generations_2d.cells:
            all_cells.extend([cell.copy() for cell in self.generations_2d.cells])
        
        return all_cells
    
    def _setup_ui(self):
        """Setup the main UI."""
        # Title
        title = QLabel(UIStrings.TITLE)
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formLayout.addRow(title)
        
        subtitle = QLabel(UIStrings.SUBTITLE)
        subtitle.setStyleSheet("font-size: 11pt; color: #aaaaaa;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formLayout.addRow(subtitle)
        
        # Frame selection area
        frames_widget = QWidget()
        frames_layout = QHBoxLayout()
        frames_layout.setSpacing(30)
        frames_layout.setContentsMargins(10, 20, 10, 20)
        frames_widget.setLayout(frames_layout)
        
        # Start frame
        self.start_preview = FramePreviewWidget("start", UIStrings.START_FRAME)
        self.start_preview.clicked.connect(self._open_frame_selector)
        frames_layout.addWidget(self.start_preview)
        
        # Arrow between frames
        arrow_label = QLabel("→")
        arrow_label.setStyleSheet("font-size: 32pt; color: #888888;")
        arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frames_layout.addWidget(arrow_label)
        
        # End frame
        self.end_preview = FramePreviewWidget("end", UIStrings.END_FRAME)
        self.end_preview.clicked.connect(self._open_frame_selector)
        frames_layout.addWidget(self.end_preview)
        
        self.formLayout.addRow(frames_widget)
        
        # Prompt
        prompt_label = QLabel(UIStrings.PROMPT_LABEL)
        prompt_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        self.formLayout.addRow(prompt_label)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(60)
        self.prompt_edit.setMaximumHeight(80)
        self.prompt_edit.setPlaceholderText(UIStrings.PROMPT_PLACEHOLDER)
        self.formLayout.addRow(self.prompt_edit)
        
        # Negative prompt
        n_prompt_label = QLabel(UIStrings.NEGATIVE_PROMPT_LABEL)
        n_prompt_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        self.formLayout.addRow(n_prompt_label)
        
        self.n_prompt_edit = QTextEdit()
        self.n_prompt_edit.setMinimumHeight(60)
        self.n_prompt_edit.setMaximumHeight(80)
        self.n_prompt_edit.setPlaceholderText(UIStrings.NEGATIVE_PROMPT_PLACEHOLDER)
        self.formLayout.addRow(self.n_prompt_edit)
        
        # Create button
        self.formLayout.setSpacing(15)
        create_button = QPushButton(UIStrings.CREATE_BUTTON)
        create_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                border: none;
                border-radius: 5px;
                padding: 12px 24px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2fc754;
            }
        """)
        create_button.clicked.connect(self._handle_create)
        self.formLayout.addRow(create_button)
    
    def _open_frame_selector(self, frame_type: str):
        """Open frame selection window."""
        log.debug(f"Opening frame selector for: {frame_type}")
        
        # Check if window already open
        if frame_type in self.open_windows:
            existing = self.open_windows[frame_type]
            if existing and existing.isVisible():
                existing.raise_()
                existing.activateWindow()
                return
        
        all_images = self._get_all_images()
        if not all_images:
            QMessageBox.warning(
                self,
                UIStrings.ERROR_TITLE,
                "Нет доступных изображений. Добавьте скетчи или сгенерируйте 2D рендеры."
            )
            return
        
        window = FrameSelectionWindow(
            frame_type,
            all_images,
            self,
            on_image_selected=self._on_frame_selected
        )
        
        self.open_windows[frame_type] = window
        window.destroyed.connect(lambda: self.open_windows.pop(frame_type, None))
        
        window.setWindowModality(Qt.WindowModality.ApplicationModal)
        window.raise_()
        window.activateWindow()
        window.show()
    
    def _on_frame_selected(self, frame_type: str, image_path: str):
        """Handle frame selection callback."""
        log.debug(f"Frame selected: {frame_type} = {image_path}")
        
        if frame_type == "start":
            self.start_frame_path = image_path
            if self.start_preview:
                self.start_preview.set_image(image_path)
        else:
            self.end_frame_path = image_path
            if self.end_preview:
                self.end_preview.set_image(image_path)
    
    def _handle_create(self):
        """Handle create button click."""
        # Validate
        if not self.start_frame_path:
            QMessageBox.warning(self, UIStrings.NO_START_FRAME, UIStrings.NO_FRAMES_TEXT)
            return
        
        if not self.end_frame_path:
            QMessageBox.warning(self, UIStrings.NO_END_FRAME, UIStrings.NO_FRAMES_TEXT)
            return
        
        prompt = self.prompt_edit.toPlainText().strip() if self.prompt_edit else ""
        n_prompt = self.n_prompt_edit.toPlainText().strip() if self.n_prompt_edit else ""
        
        # Encode images to base64
        try:
            with open(self.start_frame_path, 'rb') as f:
                start_base64 = base64.b64encode(f.read()).decode('utf-8')
            with open(self.end_frame_path, 'rb') as f:
                end_base64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            QMessageBox.critical(self, UIStrings.ERROR_TITLE, f"Не удалось прочитать изображения: {e}")
            return
        
        # Create input using models.VideoGenInput
        video_input = models.VideoGenInput(
            image1_base64=start_base64,
            image2_base64=end_base64,
            prompt=prompt if prompt else None,
            negative_prompt=n_prompt if n_prompt else None
        )
        
        QMessageBox.information(self, UIStrings.SUCCESS_TITLE, UIStrings.SUCCESS_TEXT)
        
        try:
            self.on_approve(video_input)
        except Exception as e:
            log.error(f"Error in on_approve callback: {e}")
            QMessageBox.critical(self, UIStrings.ERROR_TITLE, f"Ошибка: {e}")
        
        self.close()
    
    def closeEvent(self, event):
        """Cleanup on close."""
        log.debug(f"PrepareForVideoGen closing")
        for window in self.open_windows.values():
            if window:
                window.close()
        self.open_windows.clear()
        super().closeEvent(event)
    
    def __del__(self):
        log.debug(f"PrepareForVideoGen instance {id(self)} being deleted.")

