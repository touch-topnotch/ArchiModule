#!/usr/bin/env python3
"""
Kling multi-image2video: несколько картинок -> видео.

Требуется:
  - pip install requests PyJWT
  - env:
      KLING_ACCESS_KEY  = <ak>
      KLING_SECRET_KEY  = <sk>

Эндпоинты (официальный формат):
  - POST https://api.klingai.com/v1/videos/multi-image2video
  - GET  https://api.klingai.com/v1/videos/multi-image2video/{task_id}
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

import jwt
import requests


# =========================
#  Константы
# =========================

KLING_API_BASE = os.environ.get("KLING_API_BASE", "https://api.klingai.com")
# Только v1.6 поддерживает multi-image2video
DEFAULT_MODEL_NAME = "kling-v1-6"


class KlingError(Exception):
    pass


# =========================
#  JWT из ak/sk
# =========================

def get_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise KlingError(f"Env var {name} is not set")
    return value


def encode_jwt_token(ak: str, sk: str, ttl_seconds: int = 1800) -> str:
    now = int(time.time())
    headers = {
        "alg": "HS256",
        "typ": "JWT",
    }
    payload = {
        "iss": ak,
        "exp": now + ttl_seconds,
        "nbf": now - 5,
    }
    token = jwt.encode(payload, sk, algorithm="HS256", headers=headers)
    # В PyJWT>=2 возвращается str, в старых версиях — bytes
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def make_auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# =========================
#  API-вызовы
# =========================

def create_multi_image_task(
    token: str,
    image_urls: List[str],
    prompt: Optional[str],
    negative_prompt: Optional[str],
    mode: str,
    duration: int,
    aspect_ratio: str,
    model_name: str = DEFAULT_MODEL_NAME,
    image_tail: str = "",
    external_task_id: Optional[str] = None,
    callback_url: Optional[str] = None,
) -> str:
    """
    POST /v1/videos/multi-image2video

    body (официальный формат, по зеркалам доки):
      {
        "model_name": "kling-v1-6",
        "image_list": [{"image": "..."}],
        "mode": "std" | "pro",
        "prompt": "...",
        "negative_prompt": "",
        "image_tail": "",
        "aspect_ratio": "16:9" | "9:16" | "1:1" | ...,
        "duration": "5" | "10",
        "external_task_id": "...",
        "callback_url": "..."
      }
    Ответ:
      {
        "code": 0,
        "data": {
          "task_id": "string",
          "task_status": "submitted" | "processing" | "succeed" | "failed",
          ...
        }
      }
    """
    if len(image_urls) < 2:
        raise KlingError("multi-image2video требует минимум 2 изображения")
    if len(image_urls) > 4:
        raise KlingError("multi-image2video поддерживает максимум 4 изображения")

    url = f"{KLING_API_BASE}/v1/videos/multi-image2video"

    body: dict = {
        "model_name": model_name,
        "image_list": [{"image": u} for u in image_urls],
        "mode": mode,
        "duration": str(duration),       # API ожидает строку "5"/"10"
        "aspect_ratio": aspect_ratio,
        "image_tail": image_tail,
    }

    if prompt:
        body["prompt"] = prompt
    if negative_prompt is not None:
        body["negative_prompt"] = negative_prompt
    if external_task_id:
        body["external_task_id"] = external_task_id
    if callback_url:
        body["callback_url"] = callback_url

    headers = make_auth_headers(token)
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    try:
        data = resp.json()
    except Exception:
        raise KlingError(f"Bad JSON from create endpoint: {resp.status_code} {resp.text!r}")

    if resp.status_code != 200 or data.get("code") not in (0, "0", None):
        # У некоторых прокси code может быть null, у оф. API — 0
        raise KlingError(f"Create failed: HTTP {resp.status_code}, body={data}")

    data_block = data.get("data") or {}
    task_id = data_block.get("task_id")
    if not task_id:
        raise KlingError(f"No task_id in response: {data}")

    task_status = data_block.get("task_status")
    print(f"[create] task_id={task_id}, status={task_status}")
    return task_id


def poll_task_until_done(
    token: str,
    task_id: str,
    poll_interval: int = 5,
    timeout: int = 600,
) -> str:
    """
    GET /v1/videos/multi-image2video/{task_id}

    Ожидаем task_status == "succeed" и возвращаем URL первого видео:
      data.task_result.videos[0].url
    Формат по аналогии с text2video/image2video.
    """
    url = f"{KLING_API_BASE}/v1/videos/multi-image2video/{task_id}"
    headers = make_auth_headers(token)

    deadline = time.time() + timeout
    while True:
        if time.time() > deadline:
            raise KlingError(f"Timeout while waiting for task {task_id}")

        resp = requests.get(url, headers=headers, timeout=30)
        try:
            data = resp.json()
        except Exception:
            raise KlingError(f"Bad JSON from status endpoint: {resp.status_code} {resp.text!r}")

        if resp.status_code != 200 or data.get("code") not in (0, "0", None):
            raise KlingError(f"Status failed: HTTP {resp.status_code}, body={data}")

        d = data.get("data") or {}
        status = d.get("task_status")
        print(f"[poll] task_id={task_id}, status={status}")

        if status == "succeed":
            task_result = d.get("task_result") or {}
            videos = task_result.get("videos") or []
            if not videos:
                raise KlingError(f"task_status=succeed, но videos пуст: {data}")
            url = videos[0].get("url")
            if not url:
                raise KlingError(f"task_status=succeed, но нет video url: {videos[0]}")
            print(f"[done] video_url={url}")
            return url

        if status == "failed":
            msg = d.get("task_status_msg") or "unknown"
            raise KlingError(f"Task {task_id} failed: {msg}")

        time.sleep(poll_interval)


def download_file(url: str, output: Path) -> None:
    print(f"[download] {url} -> {output}")
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print("[download] done")


# =========================
#  CLI
# =========================

def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Kling multi-image2video: generate video from 2–4 images"
    )
    p.add_argument(
        "--images",
        nargs="+",
        required=True,
        help="Список URL картинок (2–4 шт.)",
    )
    p.add_argument(
        "--prompt",
        default=None,
        help="Позитивный промпт (опционально)",
    )
    p.add_argument(
        "--negative-prompt",
        default=None,
        help="Негативный промпт (опционально)",
    )
    p.add_argument(
        "--mode",
        default="std",
        choices=["std", "pro"],
        help="Режим генерации (std или pro, если pro доступен для твоего пакета)",
    )
    p.add_argument(
        "--duration",
        type=int,
        default=5,
        choices=[5, 10],
        help="Длительность видео в секундах (5 или 10)",
    )
    p.add_argument(
        "--aspect-ratio",
        default="16:9",
        help='Соотношение сторон, напр. "16:9", "9:16", "1:1"',
    )
    p.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help=f'Имя модели (по умолчанию "{DEFAULT_MODEL_NAME}")',
    )
    p.add_argument(
        "--image-tail",
        default="",
        help="Доп. контроль хвостовых кадров (image_tail), если используешь (опционально)",
    )
    p.add_argument(
        "--external-task-id",
        default=None,
        help="Произвольный external_task_id для трекинга (опционально)",
    )
    p.add_argument(
        "--callback-url",
        default=None,
        help="callback_url для вебхука (опционально)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Путь для сохранения mp4 (если не указан — только печать URL)",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    try:
        args = parse_args(argv)

        ak = get_env("KLING_ACCESS_KEY")
        sk = get_env("KLING_SECRET_KEY")
        token = encode_jwt_token(ak, sk)

        # 1) создать задачу
        task_id = create_multi_image_task(
            token=token,
            image_urls=args.images,
            prompt=args.prompt,
            negative_prompt=args.negative_prompt,
            mode=args.mode,
            duration=args.duration,
            aspect_ratio=args.aspect_ratio,
            model_name=args.model_name,
            image_tail=args.image_tail,
            external_task_id=args.external_task_id,
            callback_url=args.callback_url,
        )

        # 2) ждать завершения
        video_url = poll_task_until_done(token, task_id)

        print("\nFinal video URL:")
        print(video_url)

        # 3) при необходимости скачать
        if args.output:
            output_path = Path(args.output)
            download_file(video_url, output_path)

        return 0

    except KlingError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())


'''


export KLING_ACCESS_KEY="твой_ak"
export KLING_SECRET_KEY="твой_sk"

python kling_multi_image2video.py \
  --images "https://example.com/a.png" "https://example.com/b.png" \
  --prompt "A smooth 360-degree camera orbit around a single building, using the provided multi-view reference images. 
The camera slowly flies around the building and clearly shows the front, back, left, right and a slight top view. 
The building is centered on a flat white floor with a uniform white or light-gray background, like a clean studio product render. 
Soft neutral lighting, no camera shake, consistent scale, high clarity, suitable for 3D reconstruction." \
  -- negative_prompt "trees, grass, cars, people, props, other buildings, street furniture, sky, clouds, background environment, 
text, logos, reflections, motion blur, strong shadows, colored lights, dirt, damage, fog, film grain"
  --duration 5 \
  --aspect-ratio "16:9" \
  --output out.mp4
  
  
  
'''