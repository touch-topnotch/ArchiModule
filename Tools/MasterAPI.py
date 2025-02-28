'''
this script is responsible for testing the authentication of the user.
1. Auto login. Using keyring should try to auto log in to the system.
2. Log in via password and username. Password should be hashed.
3. Sign up for a new account. Password should be hashed.
'''

import requests
import keyring
import asyncio
from Models import Gen2dInput, Gen2dResult, Gen3dInput, Gen3dId, Gen3dResult, Token
import threading
from typing import Callable, Any, Optional
from PySide2.QtCore import QObject, Signal, QMetaObject, Qt


class AsyncWorker(QObject):
    result_ready = Signal(object, object)  # result, exception

    def __init__(self):
        super().__init__()

    def run(self, async_func, *args, **kwargs):
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
        # Emit signal in the widget's thread
        self.result_ready.emit(result, error)

class MasterAPI:
    API_BASE_URL = "http://localhost:8000"
    APP_NAME = "Archi"
    def __init__(self, API_BASE_URL: str="http://localhost:8000"):
        self.API_BASE_URL = API_BASE_URL
        
    def auto_login(self):
        saved_username = keyring.get_password(self.APP_NAME, "username")
        saved_password = keyring.get_password(self.APP_NAME, "password")
        print("Saved user: " + saved_username)
        if saved_username and saved_password:
            response = requests.post(f"{self.API_BASE_URL}/auth/token",
                                    data={"username": saved_username, "password": saved_password})
        if response.status_code == 200:
            return Token(**response.json())
        return None

    def login_via_password(self, username: str, password: str):
        response = requests.post(f"{self.API_BASE_URL}/auth/token", data={"username": username, "password": password})

        if response.status_code == 200 or response.status_code == 201:
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
            return e
            
            
    async def generate_3d(self, token:Token, gen3dInput:Gen3dInput):
   
        response = requests.post(self.API_BASE_URL+"/tools/v1/3d_generator", json={
            "image_base64": gen3dInput.image_base64}, headers={"Authorization": f"{token.token_type} {token.access_token}"})
        try:
            return Gen3dId(**response.json())
        except:
            return response.json()

    async def get_3d_obj(self, token:Token, obj_id:Gen3dId):
        response = requests.post(self.API_BASE_URL+"/tools/v1/get-object", json=obj_id, headers={"Authorization": f"{token.token_type} {token.access_token}"})
        try:
            return Gen3dResult(**response.json())
        except:
            response.json()
    
    def __run_async_task(
        self,
        async_func: Callable[..., Any],
        result_callback: Callable[[Optional[Any], Optional[Exception]], None],
        *args: Any,
        **kwargs: Any
    ) -> None:
        """
        Internal method to run the async function in a new event loop and handle the result or error.
        """
        loop = None
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the async function and get its result
            value = loop.run_until_complete(async_func(*args, **kwargs))

            # Pass the result to the callback
            result_callback(value, None)
        except Exception as e:
            # Pass the exception to the callback
            result_callback(None, e)
        finally:
            # Clean up the event loop
            if loop:
                loop.close()

    def run_async_task(
        self,
        async_func: Callable[..., Any],
        result_callback: Callable[[Optional[Any], Optional[Exception]], None],
        *args: Any,
        **kwargs: Any
    ) -> None:
        worker = AsyncWorker()
        worker.result_ready.connect(result_callback, Qt.QueuedConnection)
        async_thread = threading.Thread(
            target=worker.run,
            args=(async_func, *args),
            kwargs=kwargs,
            daemon=True
        )
        async_thread.start()

