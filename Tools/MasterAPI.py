'''
this script is responsible for testing the authentication of the user.
1. Auto login. Using keyring should try to auto log in to the system.
2. Log in via password and username. Password should be hashed.
3. Sign up for a new account. Password should be hashed.
'''

import requests
import keyring
import asyncio
from Models import Gen2dInput, Gen2dResult, Gen3dInput, Gen3dId, Gen3dResult, Token, RemoveBackgroundInput, ClearBackgroundInput
import threading
from typing import Callable, Any, Optional
from PySide.QtCore import QObject, Signal, Slot
import ConvertPNG

class AsyncWorker(QObject):
    result_ready = Signal(object, object)  # (result, error)

    def __init__(self):
        super().__init__()

    def run(self, async_func, *args, **kwargs):
        """Runs the given async function in a private event loop, then emits result_ready."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(async_func(*args, **kwargs))
            error = None
        except Exception as e:
            result = None
            error = e
        finally:
            loop.close()
        self.result_ready.emit(result, error)

class MasterAPI(QObject):
    
    API_BASE_URL = "http://localhost:8000"
    APP_NAME = "Archi"
    
    # Signal used to transfer callables to the main thread.
    invokeInMainThread = Signal(object)  # Will carry a tuple (func, args, kwargs)

    def __init__(self, API_BASE_URL: str="http://localhost:8000"):
        super().__init__()
        self.API_BASE_URL = API_BASE_URL
        
        # Connect the signal for main-thread invocation to its slot
        self.invokeInMainThread.connect(self.run_in_main_thread_slot)

    def auto_login(self):
        saved_username = keyring.get_password(self.APP_NAME, "username")
        saved_password = keyring.get_password(self.APP_NAME, "password")
        print("Saved user: " + str(saved_username))
        if saved_username and saved_password:
            response = requests.post(f"{self.API_BASE_URL}/auth/token",
                                    data={"username": saved_username, "password": saved_password})
            if response.status_code == 200:
                return Token(**response.json())
        return None

    def login_via_password(self, username: str, password: str):
        response = requests.post(f"{self.API_BASE_URL}/auth/token", data={"username": username, "password": password})

        if response.status_code in [200, 201]:
            keyring.set_password(self.APP_NAME, "username", username)
            keyring.set_password(self.APP_NAME, "password", password)
            return Token(**response.json())
        return None

    def sign_up(self, username: str, password: str):
        response = requests.post(f"{self.API_BASE_URL}/auth/", json={"username": username, "password": password})
        return response.status_code

    async def generate_2d(self, token:str, gen2dInput:Gen2dInput):
        print("Generating 2d. Endpoint: " + self.API_BASE_URL+"/tools/v1/pic_generator")
        
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
                print("Saving file to " + str(path))
                with open(path, "wb") as f:
                    f.write(response.content)
                if(path.split('.')[-1] == 'png'):
                    print("Converting to PNG")
                    ConvertPNG.convert_png(path, path)
                else:
                    print("Path " + str(path) + " is not a PNG")
            except Exception as e:
                raise Exception(f"Failed to save file: {e}")

        # Offload sync request to a thread
        await loop.run_in_executor(None, _sync_download)

        return True

    async def download_files(self, from_to_source: map):
        # Each file is downloaded in sequence
        for from_url, to_path in from_to_source:
            await self.download_file(from_url, to_path)
   
    @Slot(object)
    def run_in_main_thread_slot(self, data):
        """Slot to run the callback in the main thread."""
        func, args, kwargs = data
        func(*args, **kwargs)

    def run_in_main_thread(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """
        Emits invokeInMainThread so func(*args, **kwargs) is called on the main thread.
        """
        data_tuple = (func, args, kwargs)
        self.invokeInMainThread.emit(data_tuple)

    def run_async_task(
        self,
        async_func: Callable[..., Any],
        result_callback: Callable[[Optional[Any], Optional[Exception]], None],
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Runs an async function in a background thread, 
        then calls 'result_callback(result, error)' on the main thread.
        """
        worker = AsyncWorker()

        def on_result_ready(result, error):
            # Schedule a main-thread call to 'result_callback(result, error)'
            self.run_in_main_thread(result_callback, result, error)

        worker.result_ready.connect(on_result_ready)
        async_thread = threading.Thread(
            target=worker.run,
            args=(async_func, *args),
            kwargs=kwargs,
            daemon=True
        )
        async_thread.start()