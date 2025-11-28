'''
Скрипт для тестирования генерации 3D модели через Hitem3D API
'''
import requests
import keyring
import base64
import time
import sys
import os

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gen_3d.model import Gen3dInput, Obj3dId

API_BASE_URL = "http://localhost:8001"
AUTH_SERVICE_URL = "https://touchtopnotch.com/api"
APP_NAME = "Archi"

def login_via_password(username: str, password: str):
    """Авторизация через логин и пароль"""
    response = requests.post(f"{AUTH_SERVICE_URL}/auth/token", 
                           data={"username": username, "password": password})
    if response.status_code == 200 or response.status_code == 201:
        keyring.set_password(APP_NAME, "username", username)
        keyring.set_password(APP_NAME, "password", password)
        return response.json()
    else:
        print(f"Ошибка авторизации: {response.status_code} - {response.text}")
        return None

def auto_login():
    """Автоматическая авторизация через сохраненные данные"""
    saved_username = keyring.get_password(APP_NAME, "username")
    saved_password = keyring.get_password(APP_NAME, "password")
    if saved_username and saved_password:
        response = requests.post(f"{AUTH_SERVICE_URL}/auth/token",
                                 data={"username": saved_username, "password": saved_password})
        if response.status_code == 200 or response.status_code == 201:
            print("✅ Авторизация успешна (из сохраненных данных)")
            return response.json()
    
    # Пробуем авторизоваться с дефолтными данными
    print("Попытка авторизации с дефолтными данными...")
    # В OAuth2PasswordRequestForm username может быть email
    return login_via_password("holofrixxx@gmail.com", "086975pop")

def submit_3d_generation(token: str, image_path: str):
    """Отправка изображения для генерации 3D модели"""
    # Читаем изображение и конвертируем в base64
    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")
    
    # Создаем запрос в новом формате (Gen3dInput)
    payload = {
        "image_base64": image_base64,  # Single image mode
        "model": "hitem3dv1.5",
        "resolution": "512",  # Разрешение модели (512³, 1024³, 1536³, 1536³ Pro)
        "face": 100000,  # Количество полигонов (диапазон: 10000-200000)
        "format": "glb"  # Format: "obj", "glb", "stl", "fbx" (строка, конвертируется в int в сервисе)
    }
    
    print(f"📤 Отправка запроса на генерацию 3D модели...")
    print(f"   Изображение: {image_path}")
    print(f"   Размер base64: {len(image_base64)} символов")
    
    response = requests.post(
        f"{API_BASE_URL}/tools/v1/3d_generator",
        json=payload,
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=60
    )
    
    print(f"📥 Ответ сервера: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ Ошибка: {response.text}")
        return None
    
    try:
        result = response.json()
        print(f"✅ Задача создана: {result}")
        return result
    except Exception as e:
        print(f"❌ Ошибка парсинга ответа: {e}")
        print(f"   Ответ: {response.text[:500]}")
        return None

def query_task_status(token: str, task_id: str):
    """Проверка статуса задачи"""
    # Используем POST с телом запроса (Obj3dId)
    payload = {"task_id": task_id}
    response = requests.post(
        f"{API_BASE_URL}/tools/v1/get-object",
        json=payload,
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ Ошибка запроса статуса: {response.status_code} - {response.text}")
        return None
    
    try:
        return response.json()
    except Exception as e:
        print(f"❌ Ошибка парсинга ответа: {e}")
        return None

def main():
    print("=" * 60)
    print("Тестирование генерации 3D модели через Hitem3D API")
    print("=" * 60)
    
    # Путь к изображению (assets находится в родительской директории)
    image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "generated_image.jpg")
    
    if not os.path.exists(image_path):
        print(f"❌ Изображение не найдено: {image_path}")
        return
    
    # Авторизация
    print("\n1️⃣ Авторизация...")
    token = auto_login()
    if not token or 'access_token' not in token:
        print("❌ Не удалось авторизоваться")
        return
    
    # Отправка запроса на генерацию
    print("\n2️⃣ Отправка запроса на генерацию 3D модели...")
    task_result = submit_3d_generation(token, image_path)
    
    if not task_result or 'task_id' not in task_result:
        print("❌ Не удалось создать задачу")
        return
    
    task_id = task_result['task_id']
    print(f"\n✅ Задача создана с ID: {task_id}")
    
    # Проверка статуса задачи
    print("\n3️⃣ Проверка статуса задачи...")
    max_attempts = 100  # Увеличиваем для полного цикла генерации
    for i in range(max_attempts):
        print(f"   Попытка {i+1}/{max_attempts}...")
        status = query_task_status(token, task_id)
        if status:
            state = status.get('state', 'unknown')
            progress = status.get('progress')
            estimated_time = status.get('estimated_time')
            
            print(f"   Статус: {state}")
            if progress is not None:
                print(f"   📊 Прогресс: {progress}%")
            if estimated_time is not None:
                if estimated_time == 0:
                    print(f"   ⏱️  Осталось: завершено")
                else:
                    minutes = estimated_time // 60
                    seconds = estimated_time % 60
                    if minutes > 0:
                        print(f"   ⏱️  Осталось: {minutes}м {seconds}с")
                    else:
                        print(f"   ⏱️  Осталось: {seconds}с")
            
            if state == 'success':
                print(f"\n🎉 Генерация завершена успешно!")
                print(f"   URL модели: {status.get('url', 'N/A')}")
                print(f"   URL обложки: {status.get('cover_url', 'N/A')}")
                break
            elif state == 'failed':
                print(f"\n❌ Генерация завершилась с ошибкой")
                print(f"   Сообщение: {status.get('message', 'N/A')}")
                break
        
        if i < max_attempts - 1:
            time.sleep(5)  # Ждем 5 секунд перед следующей проверкой
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

