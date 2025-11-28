import base64
from typing import Optional

import FreeCADGui
import FreeCAD

from PySide.QtCore import Qt
from PySide.QtWidgets import (
    QLabel, QPushButton,
    QMessageBox, QGraphicsBlurEffect, QWidget,
    QTextEdit, QGridLayout, QVBoxLayout, QHBoxLayout, QDialog, QComboBox
)
from PySide.QtGui import QPixmap
import os


from .form_window import FormWindow
from tools.authentication.authentication import AuthenticatedSession
from tools import exporting, models
from tools.project_context.utils.gallery_utils import GalleryWidget, GalleryCell, GalleryStyle
from tools.project_context.utils import MultiViewCell
import tools.log as log
from tools.models import AsyncResponse


class ViewSelectionWindow(QWidget):
    """Separate window for selecting generated images for a specific view type."""
    
    def __init__(self, view_type: str, generations: GalleryWidget, parent=None, on_image_selected=None):
        super().__init__(parent)
        
        self.view_type = view_type
        self.selected_image_path: Optional[str] = None
        self.generations = generations
        self.on_image_selected = on_image_selected
        
        # Set window flags to make it a proper floating window
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        
        # Set up window properties
        self.setWindowTitle(f"Выбор изображений - {view_type.upper()}")
        self.setMinimumSize(600, 500)
        self.setMaximumSize(800, 700)
        
        # Set background color for the window
        self.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
            }
        """)
        
        # Center the window on the screen
        self._center_window()
        
        self._setup_view_selection()
    
    def _center_window(self):
        """Centers the window on the screen."""
        from PySide.QtGui import QScreen
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
            self.move(x, y)
    
    def _setup_view_selection(self):
        """Sets up the view selection interface with gallery."""
        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        self.setLayout(main_layout)
        
        # Title
        title = QLabel(f"Выберите лучшее изображение для вида: {self.view_type.upper()}")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Create gallery widget
        self.gallery_style = GalleryStyle(
            number_of_cols=3,
            min_dock_height=200,
            max_dock_height=350,
            width_of_cell=120,
            gap=8
        )
        
        self.gallery_widget = GalleryWidget(self.gallery_style)
        self.gallery_widget.add_cells([cell.copy() for cell in self.generations.cells])
        
        # Connect cell actions
        for cell in self.gallery_widget.cells:
            if cell.index is not None:
                cell.action.connect(lambda bound_cell=cell: self._handle_image_selection(bound_cell.index) if bound_cell.index is not None else None)
        
        main_layout.addWidget(self.gallery_widget)
        
        # Add device upload button
        device_button = QPushButton("Или добавить с устройства")
        device_button.setStyleSheet("""
            QPushButton {
                background-color: #444444;
                border: 1px solid #666666;
                border-radius: 5px;
                padding: 8px;
                color: #cccccc;
                font-size: 11px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #555555;
                border: 1px solid #888888;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
        """)
        device_button.setMaximumHeight(35)
        device_button.clicked.connect(self._handle_device_upload)
        main_layout.addWidget(device_button)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        cancel_button = QPushButton("Отмена")
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
        
        confirm_button = QPushButton("Подтвердить")
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
        confirm_button.clicked.connect(self._handle_confirm_selection)
        button_layout.addWidget(confirm_button)
        
        main_layout.addLayout(button_layout)
    
    def _handle_image_selection(self, index: int):
        """Handles the selection of an image from the gallery."""
        if not self.gallery_widget or index >= len(self.gallery_widget.cells):
            return
        
        selected_cell = self.gallery_widget.cells[index]
        if hasattr(selected_cell, 'image_path'):
            self.selected_image_path = selected_cell.image_path
            log.debug(f"Selected image for {self.view_type}: {self.selected_image_path}")
            
            # Update visual selection
            for i, cell in enumerate(self.gallery_widget.cells):
                if cell and hasattr(cell, 'label'):
                    if i == index:
                        cell.label.setStyleSheet("border: 3px solid rgba(0, 160, 200, 0.9); border-radius: 15px;")
                    else:
                        cell.label.setStyleSheet("border: 0px;")
    
    def _handle_device_upload(self):
        """Handles the device upload request."""
        log.debug("Device upload requested in view window")
        QMessageBox.information(self, "Референсы", "Функция добавления референсов будет реализована в следующей версии.")
    
    def _handle_confirm_selection(self):
        """Confirms the selection and closes the window."""
        if self.selected_image_path:
            log.debug(f"Confirmed selection for {self.view_type}: {self.selected_image_path}")
            
            # Call callback to parent window to update the cell
            if self.on_image_selected:
                self.on_image_selected(self.view_type, self.selected_image_path)
            
            self.close()
        else:
            QMessageBox.warning(self, "Не выбрано изображение", "Пожалуйста, выберите изображение или добавьте референсы.")


class PrepareFor3dGen(FormWindow):
    """Window to guide the user through selecting a render and preparing it for 3D generation."""

    def __init__(self, generations: GalleryWidget, auth_session: AuthenticatedSession, onObjIdReceived, parent: Optional[QWidget] = None):
        super().__init__(title="Prepare for 3D generation", parent=parent)  # type: ignore[arg-type]

        self.onObjIdReceived = onObjIdReceived
        self.auth_session = auth_session
        self.sketches_gallery_widget = generations # Store the input gallery
        self.project_model = exporting.load()

        self.selected_view_type: Optional[str] = None
        self.selected_images: dict[str, str] = {}  # Store selected images for each view type
        self.multi_view_cells: dict[str, MultiViewCell] = {}
        self.prompt_edit: Optional[QTextEdit] = None
        self.waiting_message_box: Optional[QMessageBox] = None
        self.open_view_windows: dict[str, ViewSelectionWindow] = {}  # Track open view windows
        self.resolution_combo: Optional[QComboBox] = None
        self.face_combo: Optional[QComboBox] = None

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
        """Sets up the Multi-View selection interface."""
        self._clear_layout()

        title = QLabel("Выберите вид для генерации 3D модели")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        
        # Create subtitle with info button
        subtitle_layout = QHBoxLayout()
        subtitle_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        subtitle = QLabel("Выберите хотя-бы один из видов для создания 3D модели")
        subtitle.setStyleSheet("font-size: 12pt;")
        
        info_button = QPushButton("ℹ")
        info_button.setMaximumSize(30, 30)
        info_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(210, 180, 140, 0.3);
                border: 1px solid rgba(210, 180, 140, 0.5);
                border-radius: 20px;
                color: rgba(255, 255, 255, 0.9);
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(210, 180, 140, 0.5);
                border: 1px solid rgba(210, 180, 140, 0.7);
            }
            QPushButton:pressed {
                background-color: rgba(210, 180, 140, 0.6);
            }
        """)
        info_button.clicked.connect(self._show_info_dialog)
        
        subtitle_layout.addWidget(subtitle)
        subtitle_layout.addWidget(info_button)
        
        subtitle_widget = QWidget()
        subtitle_widget.setLayout(subtitle_layout)
        
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.formLayout.addRow(title)
        self.formLayout.addRow(subtitle_widget)

        # Create Multi-View grid (2x2)
        multi_view_widget = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Create the 5 view cells (including back view)
        view_types = ["front", "back", "left", "right", "other"]
        positions = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]
        
        for view_type, (row, col) in zip(view_types, positions):
            cell = MultiViewCell(view_type)
            cell.clicked.connect(self._handle_view_selection)
            self.multi_view_cells[view_type] = cell
            grid_layout.addWidget(cell, row, col)
        
        multi_view_widget.setLayout(grid_layout)
        self.formLayout.addRow(multi_view_widget)

        # Project context
        prompt_label = QLabel("Контекст проекта")
        self.formLayout.addRow(prompt_label)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setPlainText(getattr(self.project_model, 'prompt', ''))
        self.prompt_edit.textChanged.connect(
            lambda: exporting.save_prop("prompt", self.prompt_edit.toPlainText()) if self.prompt_edit else None
        )
        self.formLayout.addRow(self.prompt_edit)

        # Quality settings
        quality_label = QLabel("Настройки качества")
        quality_label.setStyleSheet("font-size: 12pt; font-weight: bold;")
        self.formLayout.addRow(quality_label)

        # Resolution selection
        resolution_label = QLabel("Разрешение модели:")
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["low", "medium", "high", "ultra"])
        self.resolution_combo.setCurrentText("low")  # Default: low (512)
        self.resolution_combo.setStyleSheet("""
            QComboBox {
                background-color: #3d3d3d;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
                color: #ffffff;
                min-width: 120px;
            }
            QComboBox:hover {
                border: 1px solid #777777;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #3d3d3d;
                color: #ffffff;
                selection-background-color: #007acc;
            }
        """)
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(resolution_label)
        resolution_layout.addWidget(self.resolution_combo)
        resolution_layout.addStretch()
        resolution_widget = QWidget()
        resolution_widget.setLayout(resolution_layout)
        self.formLayout.addRow(resolution_widget)

        # Face count selection
        face_label = QLabel("Количество полигонов:")
        self.face_combo = QComboBox()
        self.face_combo.addItems(["low", "high", "ultra"])
        self.face_combo.setCurrentText("low")  # Default: low (100000)
        self.face_combo.setStyleSheet("""
            QComboBox {
                background-color: #3d3d3d;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 5px;
                color: #ffffff;
                min-width: 120px;
            }
            QComboBox:hover {
                border: 1px solid #777777;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #3d3d3d;
                color: #ffffff;
                selection-background-color: #007acc;
            }
        """)
        face_layout = QHBoxLayout()
        face_layout.addWidget(face_label)
        face_layout.addWidget(self.face_combo)
        face_layout.addStretch()
        face_widget = QWidget()
        face_widget.setLayout(face_layout)
        self.formLayout.addRow(face_widget)

        self.formLayout.setSpacing(10)
        approve_button = QPushButton("Подтвердить")
        approve_button.clicked.connect(self._handle_approve_render)
        self.formLayout.addRow(approve_button)


    # --- Event Handlers ---
    
    def _show_info_dialog(self):
        """Shows an information dialog with an image."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Информация")
        dialog.setMinimumSize(400, 500)
        dialog.setMaximumSize(600, 700)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QLabel {
                color: #ffffff;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Image
        image_label = QLabel()
        # Try to load the SVG resource
        resource_path = ":/Archi_ProjectContext.svg"
        if os.path.exists(resource_path):
            pixmap = QPixmap(resource_path)
        else:
            # Try alternative path
            alt_path = os.path.join(os.path.dirname(__file__), "..", "..", "Gui", "Resources", "icons", "Archi_ProjectContext.svg")
            if os.path.exists(alt_path):
                pixmap = QPixmap(alt_path)
            else:
                pixmap = QPixmap(200, 200)
                pixmap.fill(Qt.GlobalColor.transparent)
        
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(scaled_pixmap)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image_label)
        
        # Title
        title_label = QLabel("Генерация 3D модели")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Text
        info_text = """<p style="font-size: 12pt; line-height: 1.5;">
        Для создания 3D модели необходимо выбрать вид изображения, который будет использоваться в качестве основного.
        \n
        \n
        <b>Доступные виды:</b><br>
        • <b>FRONT</b> - вид спереди<br>
        • <b>BACK</b> - вид сзади<br>
        • <b>LEFT</b> - вид слева<br>
        • <b>RIGHT</b> - вид справа<br>
        • <b>OTHER</b> - другой ракурс<br><br>
        
        Выберите хотя бы один вид для генерации 3D модели. Рекомендуется выбрать несколько видов для более точного результата.
        </p>
        """
        text_label = QLabel(info_text)
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(text_label)
        
        # Close button
        close_button = QPushButton("Закрыть")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0088bb;
            }
        """)
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        
        dialog.setLayout(layout)
        dialog.exec()

    def _handle_view_selection(self, view_type: str):
        """Handles the selection of a view type - opens new window for image selection."""
        log.debug(f"Selected view type: {view_type}")
        
        # Check if window for this view type is already open
        if view_type in self.open_view_windows:
            existing_window = self.open_view_windows[view_type]
            if existing_window and existing_window.isVisible():
                # Window already exists and is visible, just bring it to front
                existing_window.raise_()
                existing_window.activateWindow()
                return
        
        # Create new modal window for image selection
        view_window = ViewSelectionWindow(
            view_type, 
            self.sketches_gallery_widget, 
            self, 
            on_image_selected=self._on_image_selected_callback
        )
        
        # Store reference to the window
        self.open_view_windows[view_type] = view_window
        
        # Connect to window close event to remove from tracking
        view_window.destroyed.connect(lambda: self.open_view_windows.pop(view_type, None))
        
        # Ensure the window is raised and activated (appears in front)
        view_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        view_window.raise_()
        view_window.activateWindow()
        view_window.show()
    
    def _on_image_selected_callback(self, view_type: str, image_path: str):
        """Callback when an image is selected in the ViewSelectionWindow."""
        log.debug(f"_on_image_selected_callback: {view_type}, {image_path}")
        
        # Update the cell with the selected image
        if view_type in self.multi_view_cells:
            cell = self.multi_view_cells[view_type]
            cell.set_image(image_path)
            cell.set_selected(True)
        
        # Store the selected image for this view type
        self.selected_images[view_type] = image_path
        
        # Mark this view type as selected
        self.selected_view_type = view_type



    def _handle_approve_render(self):
        """Checks selection and proceeds directly to 3D generation."""
        if not self.selected_images:
            QMessageBox.warning(self, "Не выбран вид", "Пожалуйста, выберите хотя бы один вид для генерации 3D модели")
            return
        
        # Save the selected views for 3D generation
        log.debug(f"_handle_approve_render: Selected images: {list(self.selected_images.keys())}")
        
        # Prompt is saved via textChanged signal
        self._handle_approve_model()

    def _handle_approve_model(self):
        """Validates the selected view and initiates the 3D generation API call."""
        log.debug("_handle_approve_model")
        
        # Check if at least one image is selected
        if not self.selected_images:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите хотя бы одно изображение для генерации 3D модели.")
            return

        log.debug(f"_handle_approve_model: Selected images: {list(self.selected_images.keys())}")

        # Build multi-image input
        gen3d_input_dict = {}
        
        for view_type, image_path in self.selected_images.items():
            try:
                # Read the actual image file
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
                
                if not image_bytes:
                    QMessageBox.warning(self, "Ошибка", f"Изображение пустое: {image_path}")
                    return
                
                image_bytes_b64 = base64.b64encode(image_bytes).decode()
                log.debug(f"_handle_approve_model: Loaded {view_type} image {image_path}, size: {len(image_bytes)} bytes")
                
                # Map view types to Gen3dInput fields
                if view_type == "front":
                    gen3d_input_dict["front"] = image_bytes_b64
                elif view_type == "back":
                    gen3d_input_dict["back"] = image_bytes_b64
                elif view_type == "left":
                    gen3d_input_dict["left"] = image_bytes_b64
                elif view_type == "right":
                    gen3d_input_dict["right"] = image_bytes_b64
                elif view_type == "other":
                    gen3d_input_dict["other"] = image_bytes_b64
                    
            except FileNotFoundError:
                QMessageBox.critical(self, "Ошибка", f"Файл не найден: {image_path}")
                FreeCAD.Console.PrintError(f"_handle_approve_model: File not found: {image_path}\n")
                return
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать изображение: {e}")
                FreeCAD.Console.PrintError(f"_handle_approve_model: Failed to read image {image_path}: {e}\n")
                return

        # Получаем значения качества из UI
        resolution_quality = self.resolution_combo.currentText() if self.resolution_combo else "low"
        face_quality = self.face_combo.currentText() if self.face_combo else "low"
        
        # Добавляем параметры качества в gen3d_input_dict
        gen3d_input_dict["resolution"] = resolution_quality
        gen3d_input_dict["face"] = face_quality
        
        # Create Gen3dInput with multi-image support
        gen3d_input = models.Gen3dInput(**gen3d_input_dict)
        log.debug(f"_handle_approve_model: Created Gen3dInput with fields: {list(gen3d_input_dict.keys())}")
        log.debug(f"_handle_approve_model: Quality settings - resolution: {resolution_quality}, face: {face_quality}")
        self._call_generate_3d_api(gen3d_input)


    # --- API Call Methods ---


    def _call_generate_3d_api(self, gen3d_input: models.Gen3dInput):
         """Calls the 3D generation API asynchronously."""
         log.debug("_call_generate_3d_api: Starting")
         
         # Проверяем авторизацию и валидность токена
         if not (self.auth_session.is_authenticated()):
            log.debug("_call_generate_3d_api: Not authenticated, attempting auto-login")
            self.auth_session.auto_login(callback=lambda _: self._call_generate_3d_api(gen3d_input))
            return
         
         # Проверяем, что токен не пустой и не истек
         try:
             token = self.auth_session.token
             if not token or not token.access_token:
                 log.warning("_call_generate_3d_api: Token is empty, attempting auto-login")
                 self.auth_session.auto_login(callback=lambda _: self._call_generate_3d_api(gen3d_input))
                 return
             
             if token.is_expired:
                 log.warning("_call_generate_3d_api: Token expired, attempting auto-login")
                 self.auth_session.auto_login(callback=lambda _: self._call_generate_3d_api(gen3d_input))
                 return
         except Exception as e:
             log.error(f"_call_generate_3d_api: Error getting token: {e}, attempting auto-login")
             self.auth_session.auto_login(callback=lambda _: self._call_generate_3d_api(gen3d_input))
             return
         
         # Сохраняем gen3d_input для возможного повторного запроса при ошибке авторизации
         self._last_gen3d_input = gen3d_input
         
         self._show_waiting_message("Генерация 3d модели", "Пожалуйста, подождите, идет генерация 3d модели...")
         log.debug("_call_generate_3d_api: Running async task")
         self.auth_session.masterAPI.run_async_task(
             self.auth_session.masterAPI.generate_3d,
             self._on_generated_3d,
             token=self.auth_session.token,
             gen3dInput=gen3d_input
         )


    # --- API Callbacks ---


    def _on_generated_3d(self, response:AsyncResponse[models.Gen3dId]):
        """Handles the result of the 3D generation API call."""
        log.debug("_on_generated_3d: Received callback")
        self._hide_waiting_message()

        if response.error:
            error_str = str(response.error)
            # Проверяем, является ли ошибка ошибкой авторизации (401)
            if "401" in error_str or "Unauthorized" in error_str or "Could not validate user" in error_str:
                log.warning("_on_generated_3d: Authentication error (401), attempting to re-authenticate")
                FreeCAD.Console.PrintWarning("_on_generated_3d: Token invalid, attempting to refresh...\n")
                # Пытаемся обновить токен и повторить запрос
                # Получаем gen3d_input из последнего вызова (нужно сохранить его)
                if hasattr(self, '_last_gen3d_input'):
                    self.auth_session.auto_login(callback=lambda _: self._call_generate_3d_api(self._last_gen3d_input))
                else:
                    QMessageBox.warning(self, "Ошибка авторизации", "Токен авторизации недействителен. Пожалуйста, войдите заново.")
                    self.onObjIdReceived(None, response.error)
                return
            
            FreeCAD.Console.PrintError(f"_on_generated_3d: 3D Generation error: {response.error}\n")
            QMessageBox.warning(self, "Ошибка", f"Ошибка при генерации 3d модели: {response.error}")
            self.onObjIdReceived(None, response.error) # Pass error back
            return

        if not response.result:
            FreeCAD.Console.PrintWarning("_on_generated_3d: No result received.\n")
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации 3d модели: Не получен результат.")
            self.onObjIdReceived(None, "No result") # Pass info back
            return

        # Используем get_id() для получения task_id или obj_id (from test_hitem3d.py - API returns task_id)
        task_id = response.result.get_id()
        if not task_id:
            FreeCAD.Console.PrintWarning("_on_generated_3d: No task_id or obj_id in result.\n")
            QMessageBox.warning(self, "Ошибка", "Ошибка при генерации 3d модели: Не получен ID задачи.")
            self.onObjIdReceived(None, "No task_id or obj_id") # Pass info back
            return

        log.debug(f"_on_generated_3d: Success. Received task_id: {task_id}")
        QMessageBox.information(self, "Успешно", "Запрос на генерацию 3D модели успешно отправлен.")
        self.onObjIdReceived(response.result, None) # Pass success result (Gen3dId with task_id) back
        self.close() # Close the preparation window on success


    # --- Utility Methods --- 


    def _show_waiting_message(self, title: str, text: str):
        """Displays a non-closable waiting message box."""
        FreeCADGui.updateGui()
        if self.waiting_message_box:
            self.waiting_message_box.hide()
            self.waiting_message_box.deleteLater()
        parent_widget = FreeCADGui.getMainWindow() if FreeCADGui.getMainWindow() else self # Fallback parent
        self.waiting_message_box = QMessageBox(QMessageBox.Icon.Information, title, text, QMessageBox.StandardButton.NoButton, parent_widget)
        self.waiting_message_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
        self.waiting_message_box.setWindowModality(Qt.WindowModality.ApplicationModal)
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
        log.debug(f"PrepareFor3dGen closing event for {id(self)}")
        self._hide_waiting_message()

        # Safely delete Multi-View cells
        for cell in self.multi_view_cells.values():
            try:
                cell.deleteLater()
            except RuntimeError:
                pass
        self.multi_view_cells.clear()

        super().closeEvent(event)

    def __del__(self):
        log.debug(f"PrepareFor3dGen instance {id(self)} being deleted.")

