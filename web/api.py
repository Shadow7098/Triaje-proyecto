import os
import requests

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


class ApiError(Exception):
    pass


def _resultado(resp):
    if resp.ok:
        return resp.json()
    try:
        detalle = resp.json().get("detail")
    except ValueError:
        detalle = resp.text
    if isinstance(detalle, list):  # errores de validación de FastAPI
        detalle = "; ".join(
            f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg']}" for e in detalle
        )
    raise ApiError(detalle or "Error desconocido")


def get(ruta, **params):
    params = {k: v for k, v in params.items() if v not in (None, "")}
    return _resultado(requests.get(API_URL + ruta, params=params, timeout=60))


def post(ruta, datos):
    return _resultado(requests.post(API_URL + ruta, json=datos, timeout=60))


def put(ruta, datos):
    return _resultado(requests.put(API_URL + ruta, json=datos, timeout=60))


def patch(ruta, datos):
    return _resultado(requests.patch(API_URL + ruta, json=datos, timeout=60))


def delete(ruta):
    return _resultado(requests.delete(API_URL + ruta, timeout=60))