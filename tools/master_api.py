'''
this script is responsible for testing the authentication of the user.
1. Auto login. Using keyring should try to auto log in to the system.
2. Log in via password and username. Password should be hashed.
3. Sign up for a new account. Password should be hashed.
'''

import requests
import asyncio
import inspect
from tools.models import (Gen2dInput, Gen2dResult, Gen3dInput, Gen3dId, Gen3dResult, Gen3dModel,
                          Token, RemoveBackgroundInput, ClearBackgroundInput, AsyncResponse,
                          VideoGenInput, VideoGenId, VideoGenStatus, VideoInfo)
from tools.convert_png import convert_png
from PySide.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot
import tools.log as log
from typing import Callable, Any, Optional

class UIStrings:
    """Constant strings used in the UI."""
    WRONG_CREDENTIALS = (
        "Указанные логин или пароль не найдены. Повторите попытку, чтобы получить доступ к AI инструментам"
    )
    WRONG_CREDENTIALS_TITLE = "Неверные данные"
    NO_CREDENTIALS = "Укажите логин и пароль, чтобы получить доступ к AI инструментам"
    NO_CREDENTIALS_TITLE = "Нет данных"
    CONNECTION_ABORTED = (
        "Похоже, вы не подключены к интернету. Некоторые функции могут быть не доступны"
    )
    CONNECTION_ABORTED_TITLE = "Нет подключения"


class AsyncTask(QRunnable):
    """
    Generic task runner that handles both sync functions and coroutines.
    Emits WorkerSignals.finished with (result, error).
    """
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):  # executes in thread pool
        try:
            log.info(f"AsyncTask.run: starting function {self.fn.__name__}")
            if inspect.iscoroutinefunction(self.fn):
                log.info("AsyncTask.run: detected coroutine, creating new event loop")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.fn(*self.args, **self.kwargs))
                loop.close()
                log.info("AsyncTask.run: coroutine completed")
            else:
                log.info("AsyncTask.run: calling sync function")
                result = self.fn(*self.args, **self.kwargs)
                log.info("AsyncTask.run: sync function completed")
                
            log.info(f"AsyncTask.run: result type={type(result).__name__}, is_async_response={isinstance(result, AsyncResponse)}")
            if isinstance(result, AsyncResponse):
                log.info("AsyncTask.run: emitting AsyncResponse")
                self.signals.finished.emit(result.result, result.error)
            else:
                log.info("AsyncTask.run: emitting result with None error")
                self.signals.finished.emit(result, None)
            log.info("AsyncTask.run: signals.finished.emit completed")
        except Exception as e:
            log.error(f"AsyncTask.run: exception occurred: {e}")
            import traceback
            log.error(f"AsyncTask.run: traceback: {traceback.format_exc()}")
            self.signals.finished.emit(None, e)

class WorkerSignals(QObject):
    finished = Signal(object, object)  # emits (result, error)

class MasterAPI(QObject):
    
    API_BASE_URL = "http://89.169.36.93:8001"
    APP_NAME = "Archi"
    
    has_internet_connection = False
    
    def __init__(self, api_base_url: str = None):
        super().__init__()
        if api_base_url:
            self.API_BASE_URL = api_base_url
        self.thread_pool = QThreadPool.globalInstance()
        # Keep strong references to active tasks to prevent GC before slots run
        self._active_tasks = set()
        # No extra main-thread relay; Qt will marshal signal deliveries appropriately
        self._token_refresh_callback: Optional[Callable[[], Optional[Token]]] = None

    def _invoke_on_main(self, payload):
        # Deprecated path; kept for compatibility if referenced elsewhere
        func, args, kwargs = payload
        func(*args, **kwargs)
    
    def _create_auth_headers(self, token: Token) -> dict:
        """Создает заголовки авторизации для HTTP запросов."""
        # Нормализуем token_type: приводим к правильному формату
        token_type = token.token_type.strip() if token.token_type else "Bearer"
        # Убеждаемся, что первая буква заглавная, остальные строчные
        if token_type:
            token_type = token_type.capitalize()
        else:
            token_type = "Bearer"
        
        auth_header = f"{token_type} {token.access_token}"
        log.debug(f"_create_auth_headers: token_type='{token.token_type}' -> normalized='{token_type}'")
        log.debug(f"_create_auth_headers: header='{token_type} {token.access_token[:20]}...'")
        return {"Authorization": auth_header}
    
    def _log_request_details(self, method_name: str, endpoint: str, payload: dict, token: Token):
        """Логирует детали HTTP запроса."""
        log.info(f"{method_name}: Endpoint: {self.API_BASE_URL}{endpoint}")
        
        # Логируем детали токена
        auth_header = f"{token.token_type} {token.access_token}"
        log.info(f"{method_name}: Authorization header: {auth_header}")
        log.info(f"{method_name}: Token type: '{token.token_type}'")
        log.info(f"{method_name}: Access token length: {len(token.access_token)}")
        log.info(f"{method_name}: Token expired: {token.is_expired}")
    
    def _log_response_details(self, method_name: str, response: requests.Response):
        """Логирует детали HTTP ответа."""
        try:
            # log.info(f"{method_name} HTTP {response.status_code}, elapsed={getattr(response, 'elapsed', None)}")
            try:
                headers_dict = dict(response.headers)
                log.info(f"{method_name} headers: {headers_dict}")
            except Exception:
                pass
            body_text = response.text or ""
            # log.info(f"{method_name} body length: {len(body_text)}")
            if body_text:
                chunk_size = 100
                for i in range(len(body_text)-chunk_size, len(body_text), chunk_size):
                    end = min(i+chunk_size, len(body_text))
                    # log.info(f"{method_name} body chunk {i}-{end}: {body_text[i:end]}")
        except Exception as e:
            log.error(f"{method_name}: failed to log response details: {e}")
    
    def _handle_api_response(self, method_name: str, response: requests.Response, expected_keys: list = None) -> dict:
        """Обрабатывает ответ API и возвращает данные JSON."""
        try:
            data = response.json()
        except Exception as e:
            log.error(f"{method_name}: failed to parse JSON, text starts: {response.text[:200]}")
            raise Exception(response.text)
        
        # Проверяем наличие ожидаемых ключей
        if expected_keys:
            for key in expected_keys:
                if not isinstance(data, dict) or key not in data or not data[key]:
                    keys_or_type = list(data.keys()) if isinstance(data, dict) else type(data)
                    log.error(f"{method_name}: invalid response: missing {key}, keys={keys_or_type}")
                    raise Exception(f"Invalid response: missing {key}")
        
        return data
    
    def _check_internet_connection(self) -> bool:
        """Проверяет подключение к интернету."""
        try:
            response = requests.get("http://www.google.com", timeout=5)
            self.has_internet_connection = response.status_code == 200
            return self.has_internet_connection
        except Exception:
            self.has_internet_connection = False
            return False
    
    def check_api_health(self) -> bool:
        """Проверяет состояние API сервера."""
        try:
            response = requests.get(f"{self.API_BASE_URL}/health", timeout=10)
            return response.status_code == 200
        except Exception as e:
            log.error(f"API health check failed: {e}")
            return False
    
    def set_token_refresh_callback(self, callback: Callable[[], Optional[Token]]):
        """Register a function that refreshes tokens on authorization failure."""
        self._token_refresh_callback = callback

    def _make_api_request(self, method: str, endpoint: str, token: Token, payload: dict = None, 
                         params: dict = None, timeout: int = 30, expected_keys: list = None,
                         _retry_on_unauthorized: bool = True) -> dict:
        """Универсальный метод для выполнения API запросов."""
        # Проверяем подключение к интернету
        if not self._check_internet_connection():
            raise Exception("Нет подключения к интернету")
        
        url = f"{self.API_BASE_URL}{endpoint}"
        headers = self._create_auth_headers(token)
        
        # # Детальное логирование заголовков авторизации для отладки
        # log.info(f"{method}: URL: {url}")
        # log.info(f"{method}: Authorization header: {headers.get('Authorization', 'MISSING')[:50]}...")
        # log.info(f"{method}: Token type from Token object: '{token.token_type}'")
        # log.info(f"{method}: Token access_token length: {len(token.access_token)}")
        # log.info(f"{method}: Token expired: {token.is_expired}")
        
        # Логируем детали запроса
        # if payload:
            # self._log_request_details(method, endpoint, payload, token)
        
        try:
            # Выполняем запрос
            if method.upper() == "GET":
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
            elif method.upper() == "POST":
                response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Логируем ответ
            # self._log_response_details(method, response)
            
            # Обрабатываем ошибки HTTP
            response.raise_for_status()
            
            # Обрабатываем ответ
            return self._handle_api_response(method, response, expected_keys)
            
        except requests.exceptions.ConnectionError as e:
            error_msg = "Ошибка подключения к серверу. Проверьте интернет-соединение."
            log.error(f"{method}: Connection error: {error_msg}")
            raise Exception(error_msg)
        except requests.exceptions.Timeout as e:
            error_msg = f"Превышено время ожидания запроса ({timeout} сек)"
            log.error(f"{method}: Timeout error: {error_msg}")
            raise Exception(error_msg)
        except requests.exceptions.HTTPError as e:
            # Детальное логирование для ошибок авторизации
            status_code = response.status_code if 'response' in locals() else 'unknown'
            response_text = response.text if 'response' in locals() else str(e)
            
            if status_code == 401:
                log.error(f"{method}: UNAUTHORIZED (401) - Проверьте токен авторизации")
                log.error(f"{method}: Request headers: {headers}")
                log.error(f"{method}: Token type: '{token.token_type}'")
                log.error(f"{method}: Token expired: {token.is_expired}")
                log.error(f"{method}: Response: {response_text[:500]}")
                if _retry_on_unauthorized and self._token_refresh_callback:
                    new_token = self._token_refresh_callback()
                    if new_token:
                        token.access_token = new_token.access_token
                        token.token_type = new_token.token_type
                        log.info(f"{method}: Retrying request after token refresh")
                        return self._make_api_request(
                            method, endpoint, token, payload, params, timeout, expected_keys, False
                        )
            else:
                log.error(f"{method}: HTTP {status_code}: {response_text[:500]}")
            
            error_msg = f"HTTP {status_code}: {response_text[:200]}"
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Неожиданная ошибка в {method}: {str(e)}"
            log.error(f"{method}: Unexpected error: {error_msg}")
            raise Exception(error_msg)
        
    def _run_async(
        self,
        fn: Callable,
        callback: Callable[[AsyncResponse], None],
        *args,
        **kwargs,
    ):
        """
        Helper to run a function (sync or async) in background and invoke callback(result) on main thread.
        """
        task = AsyncTask(fn, *args, **kwargs)
        # Parent the signal object to this MasterAPI to ensure it survives until delivery
        try:
            task.signals.setParent(self)
        except Exception:
            pass
        # Retain the task strongly until finished
        self._active_tasks.add(task)
        def _on_finished(result, error):
            # Release retained task
            try:
                self._active_tasks.discard(task)
            except Exception:
                pass
            try:
                log.info(f"_run_async._on_finished: received; result_type={type(result).__name__ if result is not None else 'None'}, error={'None' if not error else str(error)}")
            except Exception:
                pass
            # Directly invoke the provided callback with AsyncResponse, as before
            if result is not None and isinstance(result, AsyncResponse):
                callback(result)
                return

            if error:
                if isinstance(error, Exception):
                    callback(AsyncResponse(error=error))
                else:
                    callback(AsyncResponse(error=Exception(str(error))))
                return

            callback(AsyncResponse(result=result))
            
        task.signals.finished.connect(_on_finished)
        self.thread_pool.start(task)

    async def generate_2d(self, token: Token, gen2dInput: Gen2dInput):
        """Генерирует 2D изображение используя API."""
        # Создаем payload без None полей для избежания зависания бэкенда
        payload = {
            "image_base64": gen2dInput.image_base64,
            "prompt": gen2dInput.prompt,
            "control_strength": gen2dInput.control_strength,
        }
        if gen2dInput.negative_prompt is not None:
            payload["negative_prompt"] = gen2dInput.negative_prompt
        if gen2dInput.seed is not None:
            payload["seed"] = gen2dInput.seed

        # Выполняем API запрос в отдельном потоке, чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self._make_api_request,
            "POST",
            "/tools/v1/2d_generator",
            token,
            payload,
            None,  # params
            50,  # timeout
            ["image_base64"]  # expected_keys
        )
        
        # Логируем размер полученного изображения
        try:
            log.info(f"generate_2d: image_base64 len={len(data.get('image_base64', ''))}")
        except Exception:
            pass
        
        return Gen2dResult(**data)
        
            
    async def generate_3d(self, token: Token, gen3dInput: Gen3dInput):
        """Генерирует 3D модель используя API."""
        # Создаем payload в формате нового API (from test_hitem3d.py и новой модели Gen3dInput)
        payload = {}
        
        # Single image mode (приоритет, если указан image_base64)
        if gen3dInput.image_base64 is not None:
            payload["image_base64"] = gen3dInput.image_base64
        else:
            # Multi-image mode (новая модель API использует суффикс _image_base64)
            # Маппим старые поля (front, back, left, right, other) в новый формат
            if gen3dInput.front is not None:
                payload["front_image_base64"] = gen3dInput.front
            if gen3dInput.back is not None:
                payload["back_image_base64"] = gen3dInput.back
            if gen3dInput.left is not None:
                payload["left_image_base64"] = gen3dInput.left
            if gen3dInput.right is not None:
                payload["right_image_base64"] = gen3dInput.right
            # other может быть использован как дополнительное изображение
            if gen3dInput.other is not None and "image_base64" not in payload:
                # Если нет других изображений, используем other как основное
                payload["image_base64"] = gen3dInput.other
        
        # API параметры (from test_hitem3d.py - новый формат API)
        payload["model"] = "hitem3dv1.5"
        
        # Конвертируем качество resolution в числовое значение для API
        resolution_quality = gen3dInput.resolution or "low"
        resolution_map = {
            "low": "512",
            "medium": "1024",
            "high": "1536",
            "ultra": "1536 Pro"
        }
        payload["resolution"] = resolution_map.get(resolution_quality, resolution_quality)  # Если уже число, оставляем как есть
        
        # Конвертируем качество face в числовое значение для API
        face_quality = gen3dInput.face or "low"
        face_map = {
            "low": 100000,
            "high": 1000000,
            "ultra": 2000000
        }
        # Если face - строка качества, конвертируем; если уже число, оставляем как есть
        if isinstance(face_quality, str) and face_quality in face_map:
            payload["face"] = face_map[face_quality]
        elif isinstance(face_quality, (int, str)):
            # Если уже число (int или строка с числом), используем как есть
            payload["face"] = int(face_quality) if isinstance(face_quality, str) and face_quality.isdigit() else face_quality
        else:
            payload["face"] = 100000  # Default
        
        payload["format"] = "obj"  # Format: "obj", "glb", "stl", "fbx" (строка, как в test_hitem3d.py)
        
        log.debug(f"generate_3d: Payload keys: {list(payload.keys())}")
        
        # Выполняем API запрос в отдельном потоке, чтобы не блокировать event loop
        # Используем правильный эндпоинт из test_hitem3d.py
        loop = asyncio.get_event_loop()
        response_data = await loop.run_in_executor(
            None,
            self._make_api_request,
            "POST",
            "/tools/v1/3d_generator",  # Правильный эндпоинт из test_hitem3d.py
            token,
            payload,
            None,  # params
            60  # timeout
        )
        
        log.debug(f"generate_3d: Response: {response_data}")
        
        # Обрабатываем старый и новый форматы ответа
        if "task_id" in response_data:
            # Новый формат с task_id
            return Gen3dId(task_id=response_data["task_id"])
        elif "obj_id" in response_data:
            # Старый формат с obj_id
            return Gen3dId(obj_id=response_data["obj_id"])
        else:
            raise Exception(f"Unexpected response format: {response_data}")
    async def remove_background_pipeline(self, token: Token, removeBackgroundInput: RemoveBackgroundInput):
        """Удаляет фон с изображения используя pipeline."""
        payload = removeBackgroundInput.model_dump()
        
        # Выполняем API запрос в отдельном потоке, чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self._make_api_request,
            "POST",
            "/tools/v1/remove-background-pipeline",
            token,
            payload,
            None,  # params
            30  # timeout
        )
        
        return Gen2dResult(**data)
        
    async def remove_background(self, token: Token, removeBackgroundInput: RemoveBackgroundInput):
        """Удаляет фон с изображения."""
        payload = removeBackgroundInput.model_dump()
        # Удаляем None поля явно
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Выполняем API запрос в отдельном потоке, чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self._make_api_request,
            "POST",
            "/tools/v1/remove-background",
            token,
            payload,
            None,  # params
            30  # timeout
        )
        
        return Gen2dResult(**data)
        
    async def clear_background(self, token: Token, clearBackgroundInput: ClearBackgroundInput):
        """Очищает фон изображения."""
        payload = clearBackgroundInput.model_dump()
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Выполняем API запрос в отдельном потоке, чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self._make_api_request,
            "POST",
            "/tools/v1/clear-background",
            token,
            payload,
            None,  # params
            30  # timeout
        )
        
        return Gen2dResult(**data)

    async def generate_video(self, token: Token, videoGenInput: VideoGenInput):
        """Generates video using multi-image2video API."""
        payload = {}
        
        # Images (at least 2 required)
        payload["image1_base64"] = videoGenInput.image1_base64
        payload["image2_base64"] = videoGenInput.image2_base64
        if videoGenInput.image3_base64:
            payload["image3_base64"] = videoGenInput.image3_base64
        if videoGenInput.image4_base64:
            payload["image4_base64"] = videoGenInput.image4_base64
        
        # Parameters
        payload["model_name"] = videoGenInput.model_name
        payload["mode"] = videoGenInput.mode
        payload["duration"] = videoGenInput.duration
        payload["aspect_ratio"] = videoGenInput.aspect_ratio
        payload["cfg_scale"] = videoGenInput.cfg_scale
        
        if videoGenInput.prompt:
            payload["prompt"] = videoGenInput.prompt
        if videoGenInput.negative_prompt:
            payload["negative_prompt"] = videoGenInput.negative_prompt
        
        log.debug(f"generate_video: Payload keys: {list(payload.keys())}")
        
        # Execute API request
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self._make_api_request,
            "POST",
            "/tools/v1/video_generator",
            token,
            payload,
            None,  # params
            120,  # timeout for video generation request
            ["task_id"]  # expected_keys
        )
        
        log.debug(f"generate_video: Response: {data}")
        
        # Handle response
        return VideoGenId(
            task_id=data.get("task_id"),
            request_id=data.get("request_id"),
            task_status=data.get("task_status")
        )
    
    async def get_video(self, token: Token, task_id: str):
        """Gets video generation status and result."""
        payload = {"task_id": task_id}
        
        # Execute API request
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self._make_api_request,
            "POST",
            "/tools/v1/get-video",
            token,
            payload,
            None,  # params
            30,  # timeout
            None  # expected_keys - can vary
        )
        
        log.debug(f"get_video: Response: {data}")
        
        # Parse videos list
        videos = []
        if "videos" in data and isinstance(data["videos"], list):
            for v in data["videos"]:
                videos.append(VideoInfo(
                    id=v.get("id"),
                    duration=v.get("duration"),
                    url=v.get("url")
                ))
        
        return VideoGenStatus(
            task_id=data.get("task_id", task_id),
            task_status=data.get("task_status", "unknown"),
            task_status_msg=data.get("task_status_msg"),
            progress=data.get("progress", 0),
            estimated_time=data.get("estimated_time"),
            videos=videos
        )

    async def get_3d_obj(self, token: Token, obj_id: Gen3dId):
        """Получает 3D объект по ID задачи."""
        # Используем task_id для нового API, fallback к obj_id для legacy
        task_id = obj_id.get_id()
        
        # Используем POST с телом запроса (как в test_hitem3d.py)
        payload = {"task_id": task_id}
        
        # Выполняем API запрос в отдельном потоке, чтобы не блокировать event loop
        # Используем правильный эндпоинт и метод из test_hitem3d.py
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            self._make_api_request,
            "POST",  # POST вместо GET (как в test_hitem3d.py)
            "/tools/v1/get-object",  # Правильный эндпоинт из test_hitem3d.py
            token,
            payload,  # payload
            None,  # params
            30  # timeout
        )
        
        log.debug(f"get_3d_obj: Response data: {data}")
        
        # Обрабатываем новый формат ответа Obj3dResult (based on monitor_task.py and new API model)
        if "state" in data:
            state = data.get("state", "unknown")
            # Используем task_id из ответа API или из параметра obj_id
            response_task_id = data.get("task_id")
            task_id = response_task_id if response_task_id else obj_id.get_id()
            progress = data.get("progress") if data.get("progress") is not None else 0
            estimated_time = data.get("estimated_time")  # Estimated time in seconds (from Obj3dResult)
            url = data.get("url", "")
            cover_url = data.get("cover_url", "")
            
            # Проверяем завершена ли генерация
            if state == "success":
                # Новая модель API: url и текстуры в корне ответа
                # Маппим текстуры из новой модели в старую структуру для обратной совместимости
                texture = None
                base_color = data.get("base_color_texture")
                metallic = data.get("metallic_texture")
                roughness = data.get("roughness_texture")
                normal = data.get("normal_texture")
                
                if base_color or metallic or roughness or normal:
                    from tools.models import Gen3dTexture
                    texture = Gen3dTexture(
                        base_color_url=base_color or "",
                        metallic_url=metallic or "",
                        roughness_url=roughness or "",
                        normal_url=normal or ""
                    )
                
                # Проверяем наличие вложенного объекта object (legacy format для обратной совместимости)
                if "object" in data and isinstance(data["object"], dict):
                    obj_data = data["object"]
                    return Gen3dResult(
                        progress=100,
                        object=Gen3dModel(
                            obj_url=obj_data.get("obj_url", ""),
                            fbx_url=obj_data.get("fbx_url", ""),
                            usdz_url=obj_data.get("usdz_url", ""),
                            glb_url=obj_data.get("glb_url", url)
                        ),
                        texture=texture,
                        estimated_time=estimated_time
                    )
                elif url:
                    # Новый формат API: url в корне ответа (Obj3dResult model)
                    # API возвращает только один URL модели - используем его напрямую
                    # Определяем формат по расширению URL и заполняем только соответствующий формат
                    # Убираем query параметры для проверки расширения
                    url_without_query = url.split('?')[0] if '?' in url else url
                    url_lower = url_without_query.lower()
                    model = Gen3dModel(
                        glb_url="",
                        fbx_url="",
                        usdz_url="",
                        obj_url=""
                    )
                    
                    # Заполняем только тот формат, который реально есть в URL
                    if url_lower.endswith(".zip"):
                        # ZIP архив содержит OBJ файлы (material_0.png, material.mtl, model.obj)
                        model.obj_url = url
                    elif url_lower.endswith(".glb"):
                        model.glb_url = url
                    elif url_lower.endswith(".fbx"):
                        model.fbx_url = url
                    elif url_lower.endswith(".usdz"):
                        model.usdz_url = url
                    elif url_lower.endswith(".obj"):
                        model.obj_url = url
                    else:
                        # Если формат не определен, проверяем наличие .zip в URL (может быть в query)
                        if ".zip" in url_lower:
                            model.obj_url = url
                        else:
                            # Если формат не определен, используем как GLB по умолчанию
                            model.glb_url = url
                    
                    return Gen3dResult(
                        progress=100,
                        object=model,
                        texture=texture,
                        estimated_time=estimated_time
                    )
                else:
                    # Успешно, но URL еще не доступен
                    return Gen3dResult(progress=100, object=None, texture=None, estimated_time=estimated_time)
            elif state == "failed":
                # Задача завершилась с ошибкой
                message = data.get("message", "Unknown error")
                raise Exception(f"Generation failed: {message}")
            elif state in ["created", "queueing", "processing"]:
                # Все еще обрабатывается, возвращаем прогресс
                return Gen3dResult(progress=progress, object=None, texture=None, estimated_time=estimated_time)
            else:
                # Неизвестное состояние
                message = data.get("message", "")
                raise Exception(f"Unexpected state: {state}, message: {message}")
        else:
            # Legacy формат (для обратной совместимости)
            return Gen3dResult(**data)
    
    async def download_file(self, url: str, path: str):
        loop = asyncio.get_event_loop()

        def _sync_download():
            response = requests.get(url)
            if response.status_code != 200:
                raise Exception(f"Failed to download file: {response.status_code}")
            try:
                log.info("Saving file to " + str(path))
                with open(path, "wb") as f:
                    f.write(response.content)
                if(path.split('.')[-1] == 'png'):
                    log.info("Converting to PNG")
                    convert_png(path, path)
                else:
                    log.info("Path " + str(path) + " is not a PNG")
            except Exception as e:
                raise Exception(f"Failed to save file: {e}")

        # Offload sync request to a thread
        await loop.run_in_executor(None, _sync_download)

        return True

    async def download_files(self, from_to_source: map):
        # Each file is downloaded in sequence
        for from_url, to_path in from_to_source:
            await self.download_file(from_url, to_path)
   

    def run_async_task(
        self,
        async_func: Callable[..., Any],
        result_callback: Callable[[AsyncResponse], None],
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Runs an async function in a background thread, 
        then calls 'result_callback(result, error)' on the main thread.
        """
        self._run_async(async_func, result_callback, *args, **kwargs)   
