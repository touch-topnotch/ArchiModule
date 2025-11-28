
import hashlib
import requests
import keyring
import json
import os
import asyncio
import threading
import websockets
import webbrowser
import time
from datetime import datetime

from PySide.QtCore import QTimer

# Note: UI-related imports are kept in authentication_window.py to avoid coupling

from tools.master_api import MasterAPI
import tools.log as log
from tools.models import AuthInput, AsyncResponse, Token
from typing import Callable, Optional



class TouchTopNotchAuth:
    """TouchTopNotch authentication service integration."""
    
    API_BASE_URL = "https://touchtopnotch.com/api/auth"
    WEBSOCKET_URL = "ws://89.169.36.93:8081/auth/ws/desktop"
    APP_NAME = "TouchTopNotch_Auth"
    
    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.token_type = "Bearer"  # По умолчанию Bearer
        self.user_info = None
        log.info(f"🔐 TouchTopNotchAuth initialized with API: {self.API_BASE_URL}")
        log.info(f"🔌 WebSocket URL: {self.WEBSOCKET_URL}")
        
    def _hash_password(self, password: str) -> str:
        """Returns SHA-256 hash of the password."""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    def auto_login(self) -> Optional[dict]:
        """Auto-login using saved credentials in keyring (preferably via refresh_token)."""
        log.info("🔄 Attempting auto-login via keyring...")
        
        # 1) Preferably: refresh_token
        refresh_token = keyring.get_password(self.APP_NAME, "refresh_token")
        if refresh_token:
            log.info("🔑 Found refresh_token in keyring, attempting auto-login...")
            try:
                response = requests.post(f"{self.API_BASE_URL}/refresh", params={"refresh_token": refresh_token})
                if response.status_code == 200:
                    log.info("✅ Auto-login via refresh_token successful!")
                    data = response.json()
                    # Update refresh_token in keyring
                    new_refresh = data.get("refresh_token")
                    if new_refresh:
                        try:
                            keyring.set_password(self.APP_NAME, "refresh_token", new_refresh)
                            log.info("💾 Updated refresh_token in keyring")
                        except Exception as e:
                            log.warning(f"⚠️ Failed to update refresh_token in keyring: {e}")
                    self.access_token = data.get("access_token")
                    self.refresh_token = new_refresh
                    # Сохраняем token_type из ответа сервера, если он есть
                    self.token_type = data.get("token_type", "Bearer")
                    log.info(f"🎯 Access token obtained: {self.access_token[:20] if self.access_token else 'None'}...")
                    log.info(f"🎯 Token type: {self.token_type}")
                    return data
                else:
                    log.warning(f"❌ refresh_token invalid: {response.status_code} - {response.text}")
            except Exception as e:
                log.error(f"❌ Error in auto-login via refresh_token: {e}")
        else:
            log.info("ℹ️ No refresh_token found in keyring")
        
        # 2) Legacy: username/password if available
        saved_username = keyring.get_password(self.APP_NAME, "username")
        saved_password = keyring.get_password(self.APP_NAME, "password")
        if saved_username and saved_password:
            log.info(f"🔑 Attempting auto-login via username/password: {saved_username}")
            try:
                response = requests.post(
                    f"{self.API_BASE_URL}/token",
                    data={"username": saved_username, "password": saved_password}
                )
                if response.status_code == 200:
                    log.info("✅ Auto-login via password successful!")
                    data = response.json()
                    # Save refresh_token for future auto-logins
                    rt = data.get("refresh_token")
                    if rt:
                        keyring.set_password(self.APP_NAME, "refresh_token", rt)
                        log.info("💾 Saved refresh_token for future auto-logins")
                    self.access_token = data.get("access_token")
                    self.refresh_token = rt
                    # Сохраняем token_type из ответа сервера, если он есть
                    self.token_type = data.get("token_type", "Bearer")
                    log.info(f"🎯 Access token obtained: {self.access_token[:20] if self.access_token else 'None'}...")
                    log.info(f"🎯 Token type: {self.token_type}")
                    return data
                else:
                    log.warning(f"❌ Auto-login via password failed: {response.status_code} - {response.text}")
            except Exception as e:
                log.error(f"❌ Error in auto-login via password: {e}")
        else:
            log.info("ℹ️ No username/password found in keyring for auto-login")
        
        log.info("❌ Auto-login failed - no valid credentials found")
        return None
    
    def login_via_password(self, username: str, password: str) -> Optional[dict]:
        """Login via username/password"""
        log.info(f"Attempting to login with user: {username}")
        
        response = requests.post(
            f"{self.API_BASE_URL}/token",
            data={"username": username, "password": password}
        )
        
        if response.status_code == 200:
            log.info("✅ Login successful!")
            # Save only username (don't save password for security)
            try:
                keyring.set_password(self.APP_NAME, "username", username)
            except Exception as e:
                log.warning(f"⚠️ Failed to save username to keyring: {e}")
            # Save refresh_token for future auto-logins
            try:
                data = response.json()
                rt = data.get("refresh_token")
                if rt:
                    try:
                        keyring.set_password(self.APP_NAME, "refresh_token", rt)
                    except Exception as e:
                        log.warning(f"⚠️ Failed to save refresh_token to keyring: {e}")
                self.access_token = data.get("access_token")
                self.refresh_token = rt
                # Сохраняем token_type из ответа сервера, если он есть
                self.token_type = data.get("token_type", "Bearer")
                log.info(f"🎯 Token type from server: {self.token_type}")
            except Exception:
                pass
            return response.json()
        else:
            log.error(f"❌ Login failed: {response.status_code}")
            log.error(response.text)
            return None
    
    def sign_up(self, username: str, email: str, password: str, full_name: str) -> Optional[dict]:
        """Register new user"""
        log.info(f"Registering new user: {username}")
        
        data = {
            "username": username,
            "email": email,
            "password": password,
            "full_name": full_name
        }
        
        response = requests.post(f"{self.API_BASE_URL}/register", json=data)
        
        if response.status_code == 200:
            log.info("✅ Registration successful!")
            return response.json()
        else:
            log.error(f"❌ Registration failed: {response.status_code}")
            log.error(response.text)
            return None
    
    def get_current_user(self, token: str) -> Optional[dict]:
        """Get current user information"""
        log.info("Getting current user information...")
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{self.API_BASE_URL}/me", headers=headers)
        
        if response.status_code == 200:
            log.info("✅ User information retrieved!")
            self.user_info = response.json()
            return self.user_info
        else:
            log.error(f"❌ Failed to get user information: {response.status_code}")
            log.error(response.text)
            return None
    
    def logout(self, token: str) -> bool:
        """Logout from system"""
        log.info("Logging out...")
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(f"{self.API_BASE_URL}/logout", headers=headers)
        
        if response.status_code == 200:
            log.info("✅ Logout successful!")
            # Safely remove saved data
            try:
                existing_user = keyring.get_password(self.APP_NAME, "username")
                if existing_user is not None:
                    keyring.delete_password(self.APP_NAME, "username")
                    log.info("✅ Username removed from keyring")
            except Exception as e:
                log.warning(f"⚠️ Failed to remove username from keyring: {e}")
            
            try:
                # Remove refresh_token if exists
                existing_rt = keyring.get_password(self.APP_NAME, "refresh_token")
                if existing_rt is not None:
                    keyring.delete_password(self.APP_NAME, "refresh_token")
                    log.info("✅ Refresh token removed from keyring")
            except Exception as e:
                log.warning(f"⚠️ Failed to remove refresh_token from keyring: {e}")
            
            try:
                # Remove password only if it was saved previously (legacy behavior)
                existing = keyring.get_password(self.APP_NAME, "password")
                if existing is not None:
                    keyring.delete_password(self.APP_NAME, "password")
                    log.info("✅ Password removed from keyring")
            except Exception as e:
                log.warning(f"⚠️ Failed to remove password from keyring: {e}")
            
            self.access_token = None
            self.refresh_token = None
            self.user_info = None
            return True
        else:
            log.error(f"❌ Logout error: {response.status_code}")
            log.error(response.text)
            return False
    
    async def authenticate_via_websocket(self) -> Optional[str]:
        """
        Elegant method to get bearer token via WebSocket.
        Connects to server, waits for user authorization, automatically gets token.
        """
        log.info("\n🌐 Starting automated authentication test via WebSocket")
        log.info(f"🔌 Connecting to: {self.WEBSOCKET_URL}")
        
        try:
            log.info("📡 Establishing WebSocket connection...")
            async with websockets.connect(self.WEBSOCKET_URL) as websocket:
                log.info("✅ WebSocket connection established")
                
                # Step 1: Send authorization request
                auth_request = {
                    "type": "auth_request",
                    "timestamp": datetime.now().isoformat()
                }
                log.info(f"📤 Sending auth request: {auth_request}")
                await websocket.send(json.dumps(auth_request))
                log.info("📤 Authorization request sent")
                
                # Wait for confirmation
                log.info("⏳ Waiting for server response...")
                response = await websocket.recv()
                response_data = json.loads(response)
                log.info(f"📨 Received response: {response_data}")
                
                if response_data.get("type") == "connection_established":
                    client_id = response_data.get("client_id")
                    log.info(f"✅ Connection established. Client ID: {client_id}")
                    
                    # Now send authorization request
                    auth_request = {
                        "type": "auth_request",
                        "timestamp": datetime.now().isoformat()
                    }
                    log.info(f"📤 Sending auth request: {auth_request}")
                    await websocket.send(json.dumps(auth_request))
                    log.info("📤 Authorization request sent")
                    
                    # Wait for auth_request confirmation
                    log.info("⏳ Waiting for auth request confirmation...")
                    auth_response = await websocket.recv()
                    auth_response_data = json.loads(auth_response)
                    log.info(f"📨 Auth response: {auth_response_data}")
                    
                    if auth_response_data.get("type") == "auth_request_received":
                        log.info(f"✅ Request accepted by server. Client ID: {client_id}")
                        log.info(f"📝 Message: {auth_response_data.get('message')}")
                    else:
                        log.warning(f"⚠️ Unexpected response to auth_request: {auth_response_data}")
                else:
                    log.warning(f"⚠️ Unexpected response: {response_data}")
                    return None
                
                # Step 2: Automatically open authorization site
                auth_url = "https://touchtopnotch.com/auth/?force_login=1"
                log.info(f"\n2️⃣ Automatically opening authorization site...")
                log.info(f"🌐 URL: {auth_url}")
                
                try:
                    # Try to open in default browser
                    webbrowser.open(auth_url)
                    log.info("✅ Browser opened automatically")
                    
                    # Desktop notification (macOS)
                    if os.name == 'posix' and os.uname().sysname == 'Darwin':
                        try:
                            os.system(f"""
                                osascript -e 'display notification "Open the authorization site and log in" with title "TouchTopNotch Auth" subtitle "Waiting for authorization"'
                            """)
                            log.info("🔔 Notification sent to desktop")
                        except Exception as e:
                            log.warning(f"⚠️ Failed to send desktop notification: {e}")
                            
                except Exception as e:
                    log.error(f"❌ Error opening browser: {e}")
                    log.info(f"📋 Open manually: {auth_url}")
                    
                    # Error notification
                    if os.name == 'posix' and os.uname().sysname == 'Darwin':
                        try:
                            os.system(f"""
                                osascript -e 'display notification "Browser opening error. Open the site manually." with title "TouchTopNotch Auth" subtitle "Error"'
                            """)
                        except Exception as e:
                            log.warning(f"⚠️ Failed to send error notification: {e}")
                
                # Step 3: Wait for token via WebSocket
                log.info("\n3️⃣ Waiting for token via WebSocket...")
                log.info("📝 Please perform the following actions:")
                log.info("   - Register or log in on the site")
                log.info("   - After successful authorization, token will come automatically")
                log.info("   - Waiting...")
                
                # Wait for token with 5 minute timeout
                timeout = 300  # 5 minutes
                start_time = time.time()
                log.info(f"⏰ Timeout set to {timeout} seconds")
                
                while time.time() - start_time < timeout:
                    try:
                        # Set timeout for receiving message
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        message_data = json.loads(message)
                        log.info(f"📨 Message received: {message_data.get('type', 'unknown')}")
                        
                        if message_data.get("type") == "auth_success":
                            access_token = message_data.get("access_token")
                            refresh_token = message_data.get("refresh_token")
                            user_info = message_data.get("user_info", {})
                            
                            log.info("\n🎉 TOKEN RECEIVED AUTOMATICALLY!")
                            log.info(f"✅ Access Token: {access_token[:20]}...")
                            log.info(f"✅ Refresh Token: {refresh_token[:20]}...")
                            log.info(f"👤 User: {user_info.get('username', 'N/A')}")
                            log.info(f"📧 Email: {user_info.get('email', 'N/A')}")
                            log.info(f"👨‍💼 Full name: {user_info.get('full_name', 'N/A')}")
                            
                            # Save refresh_token for auto-login (best-effort)
                            if refresh_token:
                                log.info("\n💾 Saving refresh_token for auto-login...")
                                try:
                                    keyring.set_password(self.APP_NAME, "refresh_token", refresh_token)
                                    log.info("✅ Refresh token saved to keyring")
                                except Exception as e:
                                    log.warning(f"⚠️ Failed to save refresh_token to keyring: {e}")
                            
                            # Save username for convenience (best-effort)
                            username = user_info.get('username')
                            if username:
                                try:
                                    keyring.set_password(self.APP_NAME, "username", username)
                                    log.info(f"💾 Username saved to keyring: {username}")
                                except Exception as e:
                                    log.warning(f"⚠️ Failed to save username to keyring: {e}")
                            
                            self.access_token = access_token
                            self.refresh_token = refresh_token
                            self.user_info = user_info
                            # Сохраняем token_type из ответа, если он есть
                            self.token_type = message_data.get("token_type", "Bearer")
                            log.info(f"🎯 Token type: {self.token_type}")
                            log.info("🎯 Authentication completed successfully!")
                            return access_token
                        
                        elif message_data.get("type") == "pong":
                            log.debug("🏓 Pong received, continuing...")
                            continue
                        else:
                            log.info(f"📨 Message received: {message_data.get('type', 'unknown')}")
                            
                    except asyncio.TimeoutError:
                        # Log progress every 30 seconds
                        elapsed = int(time.time() - start_time)
                        if elapsed % 30 == 0:
                            log.info(f"⏳ Still waiting... ({elapsed}s elapsed)")
                        continue
                    except Exception as e:
                        # Do not abort the flow due to non-fatal errors (e.g., keychain write issues)
                        log.warning(f"⚠️ Non-fatal error while handling message: {e}")
                        continue
                
                log.info(f"\n⏰ Token wait timeout ({timeout} seconds)")
                log.error("❌ Token not received automatically")
                return None
                
        except websockets.exceptions.ConnectionClosed:
            log.error("❌ WebSocket connection closed")
            return None
        except Exception as e:
            log.error(f"❌ WebSocket connection error: {e}")
            import traceback
            log.error(f"📋 Traceback: {traceback.format_exc()}")
            return None

class AuthenticatedSession:
    """TouchTopNotch authenticated session manager."""
    
    def __init__(self, masterAPI: MasterAPI):
        self.masterAPI = masterAPI
        log.info("🔐 Initializing TouchTopNotch authenticated session...")
        self.auth_service = TouchTopNotchAuth()
        log.info("✅ TouchTopNotchAuth service created")
        self.authWindow = None
        self.on_login_callback = None
        self.on_error_callback = None
        self.has_internet_connection = True
        log.info("✅ AuthenticatedSession initialized successfully")

    def _handle_network_error(self, err_msg: str, callback: Callable[[AsyncResponse], None]):
        self.has_internet_connection = False
        log.error(f"🌐 Network error: {err_msg}")
        callback(AsyncResponse(error=Exception(err_msg)))

    def _login_via_credentials(self, auth_input: AuthInput) -> AsyncResponse:
        log.info(f"🔑 Attempting login with credentials for user: {auth_input.username}")
        try:
            result = self.auth_service.login_via_password(auth_input.username, auth_input.password)
            if result:
                log.info("✅ Login via credentials successful")
                return AsyncResponse(result=result)
            log.error("❌ Login via credentials failed")
            return AsyncResponse(error=Exception("Login failed"))
        except Exception as e:
            log.error(f"❌ Login error: {str(e)}")
            return AsyncResponse(error=Exception(str(e)))

    def _sign_up_via_credentials(self, auth_input: AuthInput) -> AsyncResponse:
        log.info(f"📝 Attempting registration for user: {auth_input.username}")
        try:
            # For registration, we need additional fields
            # Using email as username for now, can be enhanced later
            result = self.auth_service.sign_up(
                username=auth_input.username,
                email=f"{auth_input.username}@example.com",  # Placeholder email
                password=auth_input.password,
                full_name=auth_input.username  # Placeholder full name
            )
            if result:
                log.info("✅ Registration successful, attempting auto-login...")
                # After successful registration, try to login
                return self._login_via_credentials(auth_input)
            log.error(f"❌ Registration failed: {result}")
            return AsyncResponse(error=Exception("Registration failed"))
        except Exception as e:
            log.error(f"❌ Registration error: {str(e)}")
            return AsyncResponse(error=Exception(str(e)))

    def set_auth_window(self, window):
        """Set the authentication window and configure callbacks."""
        if not window:
            log.error("❌ Cannot set null authentication window")
            return
            
        log.info("🔗 Setting authentication window and configuring callbacks...")
        self.authWindow = window
        self.authWindow.login_success.connect(self._on_login_success)
        self.authWindow.register_success.connect(self._on_register_success)
        log.info("✅ Authentication window callbacks configured")

    def _on_login_success(self, response: AsyncResponse):
        """Handle successful login."""
        if not response:
            log.error("❌ Received null result in login success handler")
            return
            
        if response.has_error():
            log.error(f"❌ Login failed: {response.error}")
            if self.on_error_callback:
                self.on_error_callback(response.error)
            return

        log.info("✅ User successfully logged in")
        if self.on_login_callback:
            log.info("📞 Calling on_login_callback...")
            self.on_login_callback(response.result)

    def _on_register_success(self, response: AsyncResponse):
        """Handle successful registration."""
        if not response:
            log.error("❌ Received null result in registration success handler")
            return
            
        if response.has_error():
            log.error(f"❌ Registration failed: {response.error}")
            if self.on_error_callback:
                self.on_error_callback(response.error)
            return

        log.info("✅ User successfully registered")
        if self.on_login_callback:
            log.info("📞 Calling on_login_callback...")
            self.on_login_callback(response.result)

    def auto_login(self, callback: Callable[[AsyncResponse], None]):
        """Attempt to login automatically using saved credentials."""
        log.info("🔄 Attempting auto-login...")
        if not self.masterAPI:
            log.error("❌ Cannot auto-login: master API not initialized")
            callback(AsyncResponse(error=Exception("Master API not initialized")))
            return
            
        try:
            log.info("🔍 Checking for saved credentials...")
            result = self.auth_service.auto_login()
            if result:
                log.info("✅ Auto-login successful")
                callback(AsyncResponse(result=result))
            else:
                log.info("❌ Auto-login failed - no valid credentials")
                callback(AsyncResponse(error=Exception("No saved credentials found. Please authenticate via browser.")))
        except Exception as e:
            log.error(f"❌ Auto-login error: {str(e)}")
            callback(AsyncResponse(error=Exception(str(e))))

    def login(self, auth_input: AuthInput, callback: Callable[[AsyncResponse], None]):
        """Login with username and password."""
        log.info(f"🔑 Login requested for user: {auth_input.username}")
        if not self.masterAPI:
            log.error("❌ Cannot login: master API not initialized")
            callback(AsyncResponse(error=Exception("Master API not initialized")))
            return
            
        def on_login(response: AsyncResponse):
            if not response:
                log.error("❌ Received null result in login handler")
                callback(AsyncResponse(error=Exception("Received null result in login handler")))
                return
            if response.has_error():
                log.error(f"❌ Login failed: {response.error}")
                if self.on_error_callback:
                    self.on_error_callback(response.error)
                callback(response)
                return
            
            log.info("✅ Login successful, calling success handler...")
            self._on_login_success(response)
            callback(response)

        log.info("🚀 Running async login task...")
        self.masterAPI.run_async_task(self._login_via_credentials, on_login, auth_input=auth_input)

    def sign_up(self, auth_input: AuthInput, callback: Callable[[AsyncResponse], None]):
        """Register a new user."""
        log.info(f"📝 Registration requested for user: {auth_input.username}")
        if not self.masterAPI:
            log.error("❌ Cannot sign up: master API not initialized")
            callback(AsyncResponse(error=Exception("Master API not initialized")))
            return
            
        def on_signup(response: AsyncResponse):
            if response.has_error():
                log.error(f"❌ Registration failed: {response.error}")
                if self.on_error_callback:
                    self.on_error_callback(response.error)
                callback(response)
                return

            if not response:
                log.error("❌ Received null result in signup handler")
                callback(AsyncResponse(error=Exception("Received null result in signup handler")))
                return

            log.info("✅ Registration successful, calling success handler...")
            self._on_register_success(response)
            callback(response)

        log.info("🚀 Running async registration task...")
        self.masterAPI.run_async_task(self._sign_up_via_credentials, on_signup, auth_input=auth_input)

    async def authenticate_via_websocket(self, callback: Callable[[AsyncResponse], None]):
        """Authenticate via WebSocket (opens browser automatically)."""
        log.info("🌐 WebSocket authentication requested...")
        try:
            token = await self.auth_service.authenticate_via_websocket()
            if token:
                log.info("✅ WebSocket authentication successful")
                callback(AsyncResponse(result={"access_token": token}))
            else:
                log.error("❌ WebSocket authentication failed")
                callback(AsyncResponse(error=Exception("WebSocket authentication failed")))
        except Exception as e:
            log.error(f"❌ WebSocket authentication error: {str(e)}")
            callback(AsyncResponse(error=Exception(str(e))))

    # Desktop UI controls are defined in authentication_window.py
        
    def get_token(self, callback: Callable[[AsyncResponse], None]):
        """Get the current authentication token."""
        log.info("🎯 Getting authentication token...")
        if self.auth_service.access_token:
            log.info("✅ Token found in session")
            callback(AsyncResponse(result=self.auth_service.access_token))
        else:
            log.info("🔄 No token found, attempting auto-login...")
            self.auto_login(callback)

    def is_authenticated(self):
        """Check if the user is currently authenticated."""
        is_auth = self.auth_service.access_token is not None
        log.info(f"🔍 Authentication status: {'✅ Authenticated' if is_auth else '❌ Not authenticated'}")
        return is_auth

    @property
    def token(self) -> Token:
        """Return current token as Token model for API calls expecting Token.
        Raises if not authenticated."""
        if not self.auth_service.access_token:
            raise AttributeError("No access token available; user is not authenticated")
        # Используем token_type из auth_service, который был получен от сервера
        token_type = getattr(self.auth_service, 'token_type', 'Bearer')
        # log.info(f"🔑 Creating Token with type: {token_type}")
        return Token(access_token=self.auth_service.access_token, token_type=token_type)

    def logout(self):
        """Logout the current user."""
        log.info("🚪 Logging out user...")
        if self.auth_service.access_token:
            result = self.auth_service.logout(self.auth_service.access_token)
            if result:
                log.info("✅ Logout successful")
            else:
                log.error("❌ Logout failed")
            return result
        log.info("ℹ️ No active session to logout")
        return True

class Archi_Authentication_Command:
    def __init__(self, masterAPI: MasterAPI):
        self.masterAPI: MasterAPI = masterAPI
        # Website-based auth only: initialize session without any desktop auth window
        self.session: AuthenticatedSession | None = AuthenticatedSession(self.masterAPI)

    def GetResources(self):
        return {
            "MenuText": "Authentication",
            "ToolTip": "Sign in or create an account",
            "Pixmap": "Archi_Authentication"
        }

    def Activated(self):
        """Handle authentication command activation."""
        log.info("Authentication command activated")
        try:
            if self.session and self.session.is_authenticated():
                log.info("Session is authenticated, calling _on_authentication_success")
                self._on_authentication_success(AsyncResponse(result=True))
                return
        
            # Ensure session exists
            if not self.session:
                self.session = AuthenticatedSession(self.masterAPI)

            # Try auto_login first; if no saved credentials, fall back to website-based auth
            def on_auto_login(response: AsyncResponse):
                if response and response.has_result():
                    self._on_authentication_success(response)
                else:
                    log.info("No saved credentials; starting website-based authentication via WebSocket")
                    try:
                        # Run websocket auth in a dedicated background event loop
                        def run_ws_auth():
                            try:
                                asyncio.run(self.session.authenticate_via_websocket(self._on_authentication_success))
                            except Exception as e:
                                log.error(f"WebSocket auth thread error: {e}")

                        threading.Thread(target=run_ws_auth, daemon=True).start()
                    except Exception as e:
                        log.error(f"Failed to start WebSocket auth thread: {e}")

            # Add small delay before auto_login
            QTimer.singleShot(100, lambda: self.session.auto_login(on_auto_login))

        except Exception as e:
            log.error(f"Error in authentication command: {str(e)}")

    def IsActive(self):
        return True

    def _on_authentication_success(self, response: AsyncResponse):
        """Handle successful authentication (no window to manage)."""
        if not response:
            log.error("Received null response in authentication success handler")
            return
        if response.has_error():
            log.error(f"Authentication failed: {response.error}")
            return
        log.info("Authentication successful via website/WebSocket")



# INFO: DESKTOP WINDOW INTEGRATION 

# class Archi_Authentication_Command:
#     def __init__(self, masterAPI: MasterAPI):
#         self.masterAPI: MasterAPI = masterAPI
#         self.authWindow: ArchiAuthenticationWindow | None = None
#         self.session: AuthenticatedSession | None = None

#     def GetResources(self):
#         return {
#             "MenuText": "Authentication",
#             "ToolTip": "Sign in or create an account",
#             "Pixmap": "Archi_Authentication"
#         }

#     def Activated(self):
#         """Handle authentication command activation."""
#         log.info("Authentication command activated")
        
#         try:
#             if self.authWindow is None:
#                 self._initialize_auth_window()

#             if self.session and self.session.is_authenticated():
#                 log.info("Session is authenticated, calling _on_authentication_success")
#                 self._on_authentication_success(AsyncResponse(result=True))
#                 return
        
#             # Add small delay before auto_login
#             QTimer.singleShot(100, lambda: self.session.auto_login(
#                 lambda response: self._on_authentication_success(response) if response.has_result() 
#                 else self._show_existing_window()
#             ))

#         except Exception as e:
#             log.error(f"Error in authentication command: {str(e)}")
            
#     def _initialize_auth_window(self):
#         """Initialize and show a new authentication window."""
#         log.info("Initializing authentication window")
#         mw = FreeCADGui.getMainWindow()
#         self._close_existing_auth_windows(mw)
        
#         # Create session and window
#         self.session = AuthenticatedSession(self.masterAPI)
#         self.authWindow = ArchiAuthenticationWindow(mw)
#         self.authWindow.setup_widgets(self.session)
        
#         # Set up callbacks
#         self.session.set_auth_window(self.authWindow)
#         self.session.on_login_callback = self._on_authentication_success
        
#         # Add window to main window
#         mw.addDockWidget(Qt.RightDockWidgetArea, self.authWindow)
#         self.authWindow.setFloating(True)

#     def _show_existing_window(self):
#         """Show the existing authentication window."""
#         if self.authWindow:
#             self.authWindow.toggleWidgets(ArchiAuthenticationWindow.WidgetType.LOGIN)
#             self.authWindow.show()
#             self.authWindow.raise_()  
#             self.authWindow.activateWindow()
        
#     def _close_existing_auth_windows(self, main_window):
#         """Close any existing authentication windows."""
#         dock_widgets = main_window.findChildren(QDockWidget)
#         for widget in dock_widgets:
#             if widget.windowTitle() == "Authentication":
#                 widget.close()
#         log.info("Closed existing authentication windows")

#     def _on_authentication_success(self, response: AsyncResponse):
#         """Handle successful authentication."""
#         log.info("Authentication successful")
#         if self.authWindow:
#             self.authWindow.hide()

#     def IsActive(self):
#         return True

# m = MasterAPI("http://localhost:8000")
# FreeCADGui.addCommand("Archi_Authentication", Archi_Authentication_Command(m))
# FreeCADGui.runCommand("Archi_Authentication")