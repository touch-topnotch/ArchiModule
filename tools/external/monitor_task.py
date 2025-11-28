#!/usr/bin/env python3
"""
Скрипт для мониторинга статуса задачи Hitem3D
"""
import requests
import keyring
import json
import time
import os

APP_NAME = "Archi"
AUTH_SERVICE_URL = "https://touchtopnotch.com/api"
MASTER_API_BASE_URL = "http://localhost:8001"

# ID существующей задачи
TASK_ID = "b1b484c4cebf4cbeaf99092ae2e0a336.jjewelry-aigc-merchant-api.904usIItkk"

def get_token():
    """Получение токена авторизации"""
    username = keyring.get_password(APP_NAME, "username")
    password = keyring.get_password(APP_NAME, "password")
    
    if not username or not password:
        print("❌ Нет сохраненных учетных данных")
        return None
    
    response = requests.post(
        f"{AUTH_SERVICE_URL}/auth/token",
        data={"username": username, "password": password}
    )
    
    if response.status_code == 200 or response.status_code == 201:
        return response.json()
    else:
        print(f"❌ Ошибка авторизации: {response.status_code} - {response.text}")
        return None

def query_task_status(token, task_id):
    """Запрос статуса задачи с полным выводом ответа"""
    # Используем POST с телом запроса (Obj3dId)
    payload = {"task_id": task_id}
    response = requests.post(
        f"{MASTER_API_BASE_URL}/tools/v1/get-object",
        json=payload,
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=30
    )
    
    if response.status_code != 200:
        print(f"❌ Ошибка запроса: {response.status_code} - {response.text}")
        return None
    
    try:
        result = response.json()
        return result
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        print(f"   Ответ: {response.text[:500]}")
        return None

def main():
    print("=" * 60)
    print(f"Мониторинг задачи Hitem3D: {TASK_ID}")
    print("=" * 60)
    
    # Получаем токен
    token = get_token()
    if not token:
        return
    
    print("✅ Авторизация успешна\n")
    
    # Мониторим задачу
    attempt = 0
    max_attempts = 100  # Увеличиваем количество попыток
    
    while attempt < max_attempts:
        attempt += 1
        print(f"📊 Попытка {attempt}/{max_attempts}...")
        
        result = query_task_status(token, TASK_ID)
        if not result:
            break
        
        # Выводим полную структуру ответа
        print(f"\n📋 Полный ответ API:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Извлекаем основные поля
        state = result.get("state", "unknown")
        task_id = result.get("task_id", TASK_ID)
        message = result.get("message")
        url = result.get("url")
        cover_url = result.get("cover_url")
        
        print(f"\n📈 Статус: {state}")
        print(f"   Task ID: {task_id}")
        
        # Выводим процент выполнения и оставшееся время
        progress = result.get("progress")
        estimated_time = result.get("estimated_time")
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
            else:
                print(f"   ⏱️  Осталось: не указано")
        else:
            print(f"   📊 Прогресс: не указан")
        
        if message:
            print(f"   Message: {message}")
        if url:
            print(f"   URL: {url}")
        if cover_url:
            print(f"   Cover URL: {cover_url}")
        
        # Проверяем все ключи в ответе
        print(f"\n🔑 Все ключи в ответе: {list(result.keys())}")
        
        # Если задача завершена
        if state == "success":
            print("\n✅ Задача успешно завершена!")
            if url:
                print(f"   Скачать модель: {url}")
            break
        elif state == "failed":
            print("\n❌ Задача завершилась с ошибкой!")
            if message:
                print(f"   Ошибка: {message}")
            break
        
        print("\n" + "-" * 60 + "\n")
        time.sleep(5)  # Ждем 5 секунд перед следующим запросом
    
    if attempt >= max_attempts:
        print(f"\n⏱️ Достигнуто максимальное количество попыток ({max_attempts})")

if __name__ == "__main__":
    main()

