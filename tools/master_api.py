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


class WorkerSignals(QObject):
    finished = Signal(object, object)  # emits (result, error)

    
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
            if inspect.iscoroutinefunction(self.fn):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(self.fn(*self.args, **self.kwargs))
                loop.close()
            else:
                result = self.fn(*self.args, **self.kwargs)
                
            if isinstance(result, AsyncResponse):
                self.signals.finished.emit(result.result, result.error)
            else:
                self.signals.finished.emit(result, None)
        except Exception as e:
            self.signals.finished.emit(None, e)

class MasterAPI(QObject):
    
    API_BASE_URL = "http://localhost:8000"
    APP_NAME = "Archi"
    
    # Signal used to transfer callables to the main thread.
    invokeInMainThread = Signal(object)  # Will carry a tuple (func, args, kwargs)
    has_internet_connection = False
    def __init__(self, API_BASE_URL: str="http://localhost:8000"):
        super().__init__()
        self.API_BASE_URL = API_BASE_URL
    
    def __init__(self, api_base_url: str = None):
        super().__init__()
        if api_base_url:
            self.API_BASE_URL = api_base_url
        self.thread_pool = QThreadPool.globalInstance()
        
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
        def _on_finished(result, error):
            
            if(result is not None and isinstance(result, AsyncResponse)):
                callback(result)
                return
            
            if error:
                if isinstance(error, Exception):
                    callback(AsyncResponse(error=error))
                    return
                else:
                    callback(AsyncResponse(error=Exception(str(error))))
                    return
                
            callback(AsyncResponse(result=result))
            
        task.signals.finished.connect(_on_finished)
        self.thread_pool.start(task)

    async def generate_2d(self, token:str, gen2dInput:Gen2dInput):
        log.info("Generating 2d. Endpoint: " + self.API_BASE_URL+"/tools/v1/pic_generator")
        
        response = requests.post(f"{self.API_BASE_URL}/tools/v1/pic_generator", json={
            "image_base64": gen2dInput.image_base64,
            "prompt":  gen2dInput.prompt,
            "negative_prompt": gen2dInput.negative_prompt,
            "control_strength": gen2dInput.control_strength,
            "seed": gen2dInput.seed,
        }, headers={"Authorization": f"Bearer {token}"})
        
        try:
            return Gen2dResult(**response.json())
        except Exception as e:
            raise Exception(response.text)     
        
            
    async def generate_3d(self, token:Token, gen3dInput:Gen3dInput):
   
        response = requests.post(self.API_BASE_URL+"/tools/v1/3d_generator", json={
            "image_base64": gen3dInput.image_base64}, headers={"Authorization": f"{token.token_type} {token.access_token}"})
        try:
            return Gen3dId(**response.json())
        except:
            raise Exception(response.text)
    async def remove_background_pipeline(self, token, removeBackgroundInput:RemoveBackgroundInput):
        response = requests.post(self.API_BASE_URL+"/tools/v1/remove-background-pipeline", 
            json=removeBackgroundInput.model_dump(),
            headers={"Authorization": f"{token.token_type} {token.access_token}"})
        try:
            return Gen2dResult(**response.json())
        except Exception as e:
            raise Exception(response.text)
        
    async def remove_background(self, token, removeBackgroundInput:RemoveBackgroundInput):
        response = requests.post(self.API_BASE_URL+"/tools/v1/remove-background", 
            json=removeBackgroundInput.model_dump(),
            headers={"Authorization": f"{token.token_type} {token.access_token}"})
        try:
            return Gen2dResult(**response.json())
        except Exception as e:
            raise Exception(response.text)
        
    async def clear_background(self, token, clearBackgroundInput:ClearBackgroundInput):
        response = requests.post(self.API_BASE_URL+"/tools/v1/clear-background", 
            json=clearBackgroundInput.model_dump(),
            headers={"Authorization": f"{token.token_type} {token.access_token}"})
        try:
            return Gen2dResult(**response.json())
        except Exception as e:
            raise Exception(response.text)

    async def get_3d_obj(self, token: Token, obj_id: Gen3dId):
        url = self.API_BASE_URL + "/tools/v1/get-object"
        headers = {"Authorization": f"{token.token_type} {token.access_token}"}
        try:
            response = requests.post(url, json=obj_id.model_dump(), headers=headers)
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