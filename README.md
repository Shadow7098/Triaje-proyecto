# Sistema de pre-triaje para IPS

Proyecto final de Bases de Datos II (Universidad Católica Luis Amigó).
Aplicación que clasifica pacientes en tres niveles de atención a partir de sus síntomas.

- `api/`: backend en FastAPI conectado a MongoDB Atlas.
- `web/`: interfaz en Streamlit que consume la API.

## Ejecución local
1. En `api/`, crear `.env` a partir de `.env.example`, instalar con
   `pip install -r requirements.txt` y ejecutar `uvicorn main:app --reload`.
2. En `web/`, instalar con `pip install -r requirements.txt` y ejecutar
   `streamlit run Inicio.py`.
3. Opcional: `python seed.py` (en `api/`) genera datos de prueba. Borra los datos existentes.