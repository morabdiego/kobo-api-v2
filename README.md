# py-kobotoolbox

Cliente Python sincrónico para la [KoboToolbox API v2](https://kf.kobotoolbox.org/api/v2/docs/).

---

## Instalación

Requiere Python ≥ 3.14. Dependencias: `requests`, `python-dotenv`.

```bash
uv sync          # o: pip install requests python-dotenv
```

---

## Inicio rápido

**1.** Crea un archivo `.env` con tu API token (KoboToolbox → Account Settings → Security → API key):

```env
KEY=<tu_api_token>
```

**2.** Descarga los datos de una encuesta en dos líneas:

```python
import os
from dotenv import load_dotenv
from kobo import KoboClient

load_dotenv()
client = KoboClient(api_token=os.environ["KEY"])

surveys = client.get_surveys()
client.get_excel(surveys[0]["uid"])   # → data_survey.xlsx
```

---

## `get_excel` — exportación en un solo método

```python
client.get_excel(asset_uid, export_uid=None, path="data_survey.xlsx")
```

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `asset_uid` | — | UID de la encuesta |
| `export_uid` | `None` | UID de un export ya lanzado; si se omite, se lanza uno nuevo |
| `path` | `"data_survey.xlsx"` | Ruta local donde guardar el archivo |

Sin argumentos opcionales, el método:
1. Crea (o reutiliza) una configuración de exportación llamada `"python-client"`
2. Lanza un export XLS con nombres internos del XLSForm (`lang="_xml"`)
3. Espera hasta que el servidor lo genere (polling cada 3 s, timeout 120 s)
4. Descarga el archivo y devuelve su `Path` absoluto

```python
# Mínimo
saved = client.get_excel("atXzmELZmQgQkWD4cAnumv")

# Con ruta personalizada
saved = client.get_excel(uid, path="outputs/encuesta.xlsx")

# Reutilizar un export ya lanzado
saved = client.get_excel(uid, export_uid="eNHpF8SxT9oP2752mj8UJQ")
```

---

## Referencia completa

### Listar encuestas

```python
surveys = client.get_surveys()                    # todas
surveys = client.get_surveys(search="censo")      # filtradas
```

Devuelve `list[dict]` con `uid`, `name`, `deployment_status`, `date_modified`.

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `limit` | `100` | Resultados por página (máx. 300) |
| `offset` | `0` | Desplazamiento para paginación |
| `search` | `None` | Texto libre para filtrar |

---

### Inspeccionar una encuesta

```python
# Metadata completa
survey = client.get_survey(uid)

# Estructura XLSForm (preguntas, opciones, settings)
content = client.get_survey_content(uid)
for row in content["survey"]:
    print(row["type"], row.get("$autoname"))
```

---

### Export settings (configuraciones reutilizables)

Una export setting es una configuración guardada en KoboToolbox que puede reutilizarse en múltiples exportaciones.

```python
# Crear (falla si ya existe un nombre igual)
setting_uid = client.create_export_setting(uid, name="mi_config")

# Crear o reutilizar si ya existe — recomendado para scripts recurrentes
setting_uid, created = client.get_or_create_export_setting(uid, name="mi_config")

# Listar las existentes
settings = client.list_export_settings(uid)
```

**Defaults aplicados** (todos sobreescribibles con `**overrides`):

| Campo | Default | Descripción |
|-------|---------|-------------|
| `type` | `"xls"` | Formato: `"xls"`, `"csv"`, `"geojson"` |
| `lang` | `"_xml"` | `"_xml"` = nombres internos del XLSForm; o nombre del idioma, p.ej. `"Spanish"` |
| `fields_from_all_versions` | `True` | Incluye campos de versiones anteriores |
| `group_sep` | `"/"` | Separador de grupos en los nombres de columna |
| `hierarchy_in_labels` | `False` | Incluye jerarquía en las etiquetas |
| `multiple_select` | `"summary"` | `"summary"`, `"both"` o `"details"` |
| `flatten` | `False` | Aplana la estructura de grupos |
| `xls_types_as_text` | `False` | Exporta todos los tipos como texto |
| `include_media_url` | `False` | Incluye URLs de archivos adjuntos |

```python
# Con overrides
setting_uid = client.create_export_setting(
    uid,
    name="csv_espanol",
    type="csv",
    lang="Spanish",
)
```

---

### Exportaciones async (control manual)

Para mayor control sobre el proceso de exportación:

```python
# 1. Lanzar un export
export_uid = client.trigger_export(uid, type="xls", lang="_xml")

# Filtrar por fecha
export_uid = client.trigger_export(
    uid,
    query={"$and": [{"_submission_time": {"$gte": "2024-01-01"}}]},
)

# Solo ciertas submissions o campos
export_uid = client.trigger_export(uid, submission_ids=[101, 102])
export_uid = client.trigger_export(uid, fields=["nombre", "edad"])

# 2. Esperar y obtener la URL de descarga
result = client.wait_for_export(uid, export_uid)
print(result["result"])   # URL directa del archivo

# 3. O esperar y descargar directamente
saved = client.download_export(uid, export_uid, dest_path="datos/encuesta.xlsx")
```

| Método | Devuelve |
|--------|----------|
| `trigger_export(uid, ...)` | `export_uid: str` |
| `wait_for_export(uid, export_uid)` | `dict` con `result` (URL de descarga) |
| `download_export(uid, export_uid, path)` | `Path` del archivo guardado |

---

## Instancia self-hosted

```python
client = KoboClient(api_token="...", base_url="https://kobo.miinstancia.org")
```

---

## Errores

| Excepción | Cuándo se lanza |
|-----------|-----------------|
| `KoboError` | La API devuelve un error HTTP (4xx / 5xx) |
| `ExportTimeoutError` | El export no completó dentro del `timeout` (default: 120 s) |

```python
from kobo.client import KoboError, ExportTimeoutError

try:
    saved = client.get_excel(uid, path="out.xlsx")
except ExportTimeoutError:
    print("La exportación tardó demasiado")
except KoboError as e:
    print(f"Error de API: {e}")
```
