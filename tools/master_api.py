'''
this script is responsible for testing the authentication of the user.
1. Auto login. Using keyring should try to auto log in to the system.
2. Log in via password and username. Password should be hashed.
3. Sign up for a new account. Password should be hashed.
'''

import requests
import asyncio
import inspect
from tools.models import (Gen2dInput, Gen2dResult, Gen3dInput, Gen3dId, Gen3dResult,
                          Token, RemoveBackgroundInput, ClearBackgroundInput, AsyncResponse)
from tools.convert_png import convert_png
from PySide.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot
import tools.log as log
from typing import Callable, Any

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
    def __init__(self, API_BASE_URL: str="http://89.169.36.93:8001"):
        super().__init__()
        self.API_BASE_URL = API_BASE_URL
    
    def __init__(self, api_base_url: str = None):
        super().__init__()
        if api_base_url:
            self.API_BASE_URL = api_base_url
        self.thread_pool = QThreadPool.globalInstance()
        # Keep strong references to active tasks to prevent GC before slots run
        self._active_tasks = set()
        # No extra main-thread relay; Qt will marshal signal deliveries appropriately

    def _invoke_on_main(self, payload):
        # Deprecated path; kept for compatibility if referenced elsewhere
        func, args, kwargs = payload
        func(*args, **kwargs)
        
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

    async def generate_2d(self, token:str, gen2dInput:Gen2dInput):
        log.info("Generating 2d. Endpoint: " + self.API_BASE_URL+"/tools/v1/pic_generator")
        # Build payload without None fields to avoid backend hangs on nulls
        payload = {
            "image_base64": gen2dInput.image_base64,
            "prompt": gen2dInput.prompt,
            "control_strength": gen2dInput.control_strength,
        }
        if gen2dInput.negative_prompt is not None:
            payload["negative_prompt"] = gen2dInput.negative_prompt
        if gen2dInput.seed is not None:
            payload["seed"] = gen2dInput.seed

        response = requests.post(
            f"{self.API_BASE_URL}/tools/v1/pic_generator",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=50,
        )
        
        # Log ALL response from the server (status, headers, body in chunks)
        try:
            log.info(f"generate_2d HTTP {response.status_code}, elapsed={getattr(response, 'elapsed', None)}")
            try:
                headers_dict = dict(response.headers)
                log.info(f"generate_2d headers: {headers_dict}")
            except Exception:
                pass
            body_text = response.text or ""
            log.info(f"generate_2d body length: {len(body_text)}")
            if body_text:
                chunk_size = 100
                for i in range(len(body_text)-chunk_size, len(body_text), chunk_size):
                    end = min(i+chunk_size, len(body_text))
                    log.info(f"generate_2d body chunk {i}-{end}: {body_text[i:end]}")
        
        except Exception as e:
            log.error(f"generate_2d: failed to log full response: {e}")
        
        try:
            data = response.json()
        except Exception as e:
            log.error(f"gen2d: failed to parse json, text starts: {response.text[:200]}")
            raise Exception(response.text)
        # Guard: ensure image_base64 present to avoid UI hanging
        if not isinstance(data, dict) or "image_base64" not in data or not data["image_base64"]:
            keys_or_type = list(data.keys()) if isinstance(data, dict) else type(data)
            log.error(f"gen2d: invalid response: missing image_base64, keys={keys_or_type}")
            raise Exception("Invalid response: missing image_base64")
        try:
            log.info(f"gen2d: image_base64 len={len(data.get('image_base64', ''))}")
        except Exception:
            pass
        
        return Gen2dResult(**data)
        
            
    async def generate_3d(self, token:Token, gen3dInput:Gen3dInput):
   
        response = requests.post(self.API_BASE_URL+"/tools/v1/3d_generator", json={
            "image_base64": gen3dInput.image_base64}, headers={"Authorization": f"{token.token_type} {token.access_token}"})
        try:
            return Gen3dId(**response.json())
        except:
            raise Exception(response.text)
    async def remove_background_pipeline(self, token: Token, removeBackgroundInput:RemoveBackgroundInput):
        response = requests.post(self.API_BASE_URL+"/tools/v1/remove-background-pipeline", 
            json=removeBackgroundInput.model_dump(),
            headers={"Authorization": f"{token.token_type} {token.access_token}"})
        try:
            return Gen2dResult(**response.json())
        except Exception as e:
            raise Exception(response.text)
        
    async def remove_background(self, token: Token, removeBackgroundInput:RemoveBackgroundInput):
        payload = removeBackgroundInput.model_dump()
        # Strip None fields explicitly
        payload = {k: v for k, v in payload.items() if v is not None}
        response = requests.post(
            self.API_BASE_URL+"/tools/v1/remove-background",
            json=payload,
            headers={"Authorization": f"{token.token_type} {token.access_token}"},
            timeout=30,
        )
        try:
            return Gen2dResult(**response.json())
        except Exception as e:
            raise Exception(response.text)
        
    async def clear_background(self, token, clearBackgroundInput:ClearBackgroundInput):
        payload = clearBackgroundInput.model_dump()
        payload = {k: v for k, v in payload.items() if v is not None}
        response = requests.post(
            self.API_BASE_URL+"/tools/v1/clear-background",
            json=payload,
            headers={"Authorization": f"{token.token_type} {token.access_token}"},
            timeout=30,
        )
        try:
            return Gen2dResult(**response.json())
        except Exception as e:
            raise Exception(response.text)

    async def get_3d_obj(self, token: Token, obj_id: Gen3dId):
        url = self.API_BASE_URL + "/tools/v1/get-object"
        headers = {"Authorization": f"{token.token_type} {token.access_token}"}
        try:
            response = requests.post(url, json=obj_id.model_dump(), headers=headers, timeout=30)
            response.raise_for_status()  # Raise an error if not a 2xx status
            data = response.json()
            return Gen3dResult(**data)
        except Exception as e:
            raise Exception(f"Error in get_3d_obj: {e}\nServer response: {response.text if 'response' in locals() else ''}")
    
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