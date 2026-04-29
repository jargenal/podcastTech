# PodcastTech Offline TTS

Aplicacion web local para convertir texto a audio profesional tipo podcast, completamente offline, optimizada para espanol y preparada para macOS Apple Silicon.

Importante: para una instalacion estable de Coqui XTTS v2 en macOS, usa Python 3.10. La combinacion con Python 3.13 o 3.14 no es una base fiable para este proyecto.

## 1. Arquitectura

### Objetivos

- interfaz web local con FastAPI y Jinja2
- sintesis offline con Coqui XTTS v2
- pipeline desacoplado para futuro soporte de otros motores
- procesamiento por segmentos para guiones largos
- historial local sin base de datos compleja

### Componentes

- `app/main.py`: inicializa FastAPI, servicios y static assets
- `app/routes/web.py`: rutas HTTP, carga de archivos, SSE, reproduccion y descargas
- `app/services/base.py`: contrato comun para motores TTS
- `app/services/xtts_service.py`: integracion con Coqui XTTS v2
- `app/services/generation_service.py`: orquestacion de parsing, segmentacion, sintesis y persistencia
- `app/services/audio_pipeline.py`: concatenacion, silencios, normalizacion y exportaciones
- `app/services/disk_audio_assembler.py`: ensamblado en disco para renders largos con FFmpeg concat
- `app/services/audio_segment_validator.py`: validacion de WAV generados por segmento
- `app/services/render_manifest.py`: manifiesto/checkpoints persistentes de renders largos
- `app/services/history_service.py`: historial JSON en `output/history.json`
- `app/services/job_manager.py`: estado en memoria y eventos SSE por job
- `app/config/default_lexicons.py`: lexico base de pronunciacion y tildes frecuentes
- `app/config/lexicons/pronunciation_overrides.json`: overrides editables de pronunciacion
- `app/config/lexicons/accent_overrides.json`: overrides editables de tildes frecuentes
- `app/utils/text_parser.py`: parser del formato enriquecido con etiquetas
- `app/utils/text_processing.py`: limpieza markdown, normalizacion y segmentacion inteligente
- `settings.json`: configuracion operativa editable

### Flujo de generacion

1. El usuario sube un `.txt` o `.md`, o pega texto manualmente.
2. El backend parsea etiquetas opcionales como `[TITULO]`, `[IDIOMA]`, `[VOZ]`, `[TEXTO]`, `[PAUSA]`.
3. El texto se limpia y se divide en segmentos seguros por parrafo y puntuacion.
4. XTTS sintetiza cada segmento con una voz de referencia WAV.
5. Para renders cortos, `audio_pipeline.py` inserta silencios, concatena, normaliza si aplica y exporta WAV.
6. Para renders largos, `long_render` guarda segmentos persistentes, valida/reintenta chunks, escribe manifiesto y ensambla desde disco con FFmpeg concat.
7. Si FFmpeg existe, exporta MP3 y M4A opcionales.
8. El resultado se persiste en historial y se expone en la UI.

### Consideraciones de dialecto

XTTS v2 utiliza `language="es"` para espanol. La diferenciacion entre `es_latam`, `es_neutro` y `es_es` en esta app se resuelve mediante:

- configuracion separada por variante
- voz de referencia distinta por variante
- fallback automatico de voz si la variante elegida no tiene muestra disponible

## 2. Arbol del proyecto

```text
podcastTech/
├── app/
│   ├── config/
│   │   └── settings.py
│   ├── main.py
│   ├── models/
│   │   └── domain.py
│   ├── routes/
│   │   └── web.py
│   ├── services/
│   │   ├── audio_pipeline.py
│   │   ├── base.py
│   │   ├── generation_service.py
│   │   ├── history_service.py
│   │   ├── job_manager.py
│   │   └── xtts_service.py
│   ├── static/
│   │   ├── css/app.css
│   │   └── js/app.js
│   ├── templates/
│   │   ├── base.html
│   │   ├── history.html
│   │   └── index.html
│   └── utils/
│       ├── files.py
│       ├── system.py
│       ├── text_parser.py
│       └── text_processing.py
├── input/
│   └── example_podcast.md
├── output/
│   └── history.json
├── temp/
├── voices/
│   └── README.md
├── requirements.txt
├── settings.json
└── README.md
```

## 3. Codigo y ejecucion

### Requisitos del sistema

- macOS Apple Silicon
- Python 3.10 recomendado
- entorno virtual local
- FFmpeg opcional para MP3/M4A

### Instalacion base

```bash
brew install python@3.10
/opt/homebrew/bin/python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

Nota: `requirements.txt` fija `setuptools<81` porque dependencias actuales de Coqui TTS y `librosa` siguen usando `pkg_resources`.
Tambien fija `transformers<5` porque Coqui XTTS v2 en `TTS 0.22.0` no es compatible con `transformers 5.x`.

### Arranque

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8040
```

Abrir:

- `http://127.0.0.1:8040`

### Desarrollo con autoreload

No uses `--reload` apuntando al proyecto completo si el entorno virtual `.venv` vive dentro de la carpeta del proyecto. En macOS, `watchfiles` puede detectar cambios dentro de `.venv/site-packages` durante imports o compilacion de bytecode y reiniciar Uvicorn en mitad del render.

Si necesitas autoreload, limita el watch al codigo fuente:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8040 --reload --reload-dir app --reload-include '*.py'
```

### Rutas expuestas

- `GET /`
- `POST /generate`
- `POST /preview-text`
- `GET /events/{job_id}`
- `GET /audio/{filename}`
- `GET /download/{filename}`
- `GET /history`
- `GET /health`

## 4. Setup XTTS v2 offline

### Importante

La app es 100% offline durante ejecucion, pero XTTS v2 necesita estar ya instalado y con el modelo disponible en cache local antes de desconectar la maquina de internet.

Coqui documenta `TTS` con soporte de Python `<3.11`. En la practica, Python 3.10 es la opcion mas estable para este stack.

### Preparacion recomendada

1. Crear el entorno virtual con Python 3.10 e instalar dependencias.
2. Con conexion, ejecutar una carga unica del modelo para poblar el cache:

```bash
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
```

3. Confirmar que el cache local existe en la carpeta de usuario de Coqui/Hugging Face segun tu entorno.
4. Despues ya puedes ejecutar la app sin red.

### Ajustes para Apple Silicon

- `settings.json` usa `device_preference: "auto"` y elegira `mps` si PyTorch lo soporta.
- Si observas inestabilidad o errores en `mps`, cambia a `cpu`.
- Para renders largos de 20 a 25 minutos, conviene usar segmentos de `180` a `260` caracteres para reducir degradacion local de XTTS.
- El proyecto incluye `eco_mode` activo por defecto para limitar hilos de PyTorch y enfriar `250 ms` entre segmentos.
- Puedes ajustar `eco_mode.max_torch_threads`, `eco_mode.max_interop_threads` y `eco_mode.inter_segment_cooldown_ms` en `settings.json`.

### Render seguro automatico

Cada generacion pasa primero por `RenderPlanner`, que clasifica el job en una estrategia:

- `standard_memory_render`: solo para audios pequenos y simples.
- `safe_disk_render`: audios medianos, tecnicos o bilingues que conviene ensamblar en disco.
- `long_disk_render`: audios largos, muchos segmentos o mas de 20 minutos estimados.
- `critical_disk_render`: renders muy extensos o de alto riesgo.

La decision es automatica. El usuario no necesita activar manualmente `long_render`; si un render supera los limites seguros de memoria, el sistema usa disco aunque la solicitud intente desactivar `long_render`. La seccion `render_safety` de `settings.json` define los limites centrales de duracion, caracteres, cantidad de items, segmentos de voz y densidad tecnica/bilingue.

En este modo:

- cada segmento XTTS se escribe como WAV persistente en `output/renders/<job_id>/segments/`
- cada segmento se valida antes de ensamblar
- los segmentos sospechosos se reintentan hasta `long_render.max_segment_retries`
- el manifiesto queda en `output/renders/<job_id>/manifest.json` e incluye `render_plan`, razones, metricas y politica de calidad
- los chunks procesados para concat quedan en `output/renders/<job_id>/processed/`
- el debug completo queda en `output/debug/<job_id>.json`
- el WAV final se ensambla con FFmpeg concat sin construir un `AudioSegment` gigante en RAM
- si se pide MP3 o M4A, primero se genera un WAV estable y luego se convierte con FFmpeg

Configuracion recomendada para audios de mas de 25 minutos:

```json
"long_render": {
  "enabled": true,
  "force": false,
  "auto_enable_min_estimated_seconds": 1200,
  "auto_enable_min_segments": 80,
  "keep_temp_segments": true,
  "enable_resume": true,
  "checkpoint_every_segments": 1,
  "max_segment_retries": 2,
  "validate_segments": true,
  "assemble_with_ffmpeg_concat": true,
  "normalize_per_segment": false,
  "normalize_final_with_ffmpeg": false,
  "cleanup_after_success": false,
  "cleanup_after_failure": false
}
```

```json
"render_safety": {
  "memory_max_estimated_seconds": 600,
  "memory_max_speech_segments": 35,
  "memory_max_total_items": 55,
  "memory_max_characters": 9000,
  "safe_disk_min_estimated_seconds": 420,
  "long_disk_min_estimated_seconds": 1200,
  "critical_disk_min_estimated_seconds": 2400,
  "safe_disk_min_speech_segments": 30,
  "long_disk_min_speech_segments": 80,
  "critical_disk_min_speech_segments": 180,
  "technical_density_high_ratio": 0.025,
  "english_span_high_ratio": 0.12,
  "sensitive_segment_high_ratio": 0.18
}
```

Para normalizar un render largo sin cargar todo en memoria, activa `normalize_final_with_ffmpeg`. Si FFmpeg no esta instalado y el plan requiere disco, el render falla de forma explicita porque no puede garantizar ensamblado seguro. `DiskAudioAssembler` no vuelve silenciosamente a `AudioPipeline.assemble()` en memoria.

### Si fallaste con Python 3.13 o 3.14

Eso es esperable. Debes borrar ese entorno virtual y recrearlo con Python 3.10:

```bash
deactivate 2>/dev/null || true
rm -rf .venv
brew install python@3.10
/opt/homebrew/bin/python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel
pip install -r requirements.txt
python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"
uvicorn app.main:app --host 127.0.0.1 --port 8040 --reload
```

### FFmpeg opcional

Si quieres MP3/M4A:

```bash
brew install ffmpeg
```

Si FFmpeg no esta instalado, la app sigue funcionando y exporta WAV.

## 5. Formato de entrada enriquecido

Ejemplo disponible en `input/example_podcast.md`.

Etiquetas soportadas:

- `[TITULO]`
- `[IDIOMA]`
- `[VOZ]`
- `[VOZ_EN]`
- `[TEXTO]`
- `[PAUSA]`

Etiquetas inline soportadas dentro de `[TEXTO]` o texto libre:

- `[PRON]termino|pronunciacion[/PRON]`
- `[EN]english phrase[/EN]`

Comportamiento:

- si no hay etiquetas, todo el contenido se trata como texto continuo
- las lineas vacias se ignoran
- las pausas se convierten en silencio en milisegundos
- si faltan datos, se usan defaults de `settings.json`
- el sistema aplica un lexico configurable para terminos tecnicos anglosajones como `OpenAI`, `backend`, `frontend`, `API`, `SDK`, `CI/CD` y similares
- tambien intenta adaptar automaticamente tokens tecnicos no marcados como `CloudWatch`, `S3`, `EC2`, `Node.js`, `Next.js`, `AccessKeyId` y siglas encerradas entre corchetes como `[MFA]`
- el sistema puede restaurar tildes frecuentes en palabras como `despues`, `generacion`, `puntuacion`, `terminos` o `mas` antes de sintetizar
- los acronimos en mayusculas pueden deletrearse automaticamente en estilo spanglish
- `[PRON]` fuerza la pronunciacion exacta que escribas
- `[EN]` marca una frase en ingles para sintetizarla como ingles real usando la misma voz clonada o una voz inglesa opcional, sin pasar por el lexico ni la adaptacion fonetica del espanol
- el sistema inserta una micro pausa configurable al entrar y salir de spans `[EN]` para que la transicion se sienta mas natural
- puedes ajustar `default_english_speed`, `default_english_temperature` y `audio_tuning.bilingual_transition_pause_ms` en `settings.json`
- puedes fijar una voz exclusiva para ingles desde la UI o con la etiqueta `[VOZ_EN]`
- la interfaz incluye una previsualizacion del texto adaptado para revisar pronunciaciones antes de generar el audio

Configuracion de pronunciacion:

- `settings.json -> speech.enabled`: activa o desactiva la adaptacion
- `settings.json -> speech.restore_spanish_accents`: activa o desactiva la restauracion de tildes frecuentes
- `settings.json -> speech.accent_lexicon_overrides_file`: archivo JSON editable de correccion de tildes
- `settings.json -> speech.spell_acronyms`: controla el deletreo automatico
- `settings.json -> speech.pronunciation_lexicon_overrides_file`: archivo JSON editable de terminos y pronunciaciones

Actualizacion dinamica:

- si editas `app/config/lexicons/pronunciation_overrides.json`, el cambio entra en la siguiente generacion sin reiniciar el servidor
- si editas `app/config/lexicons/accent_overrides.json`, la correccion entra en la siguiente generacion sin reiniciar el servidor

## 6. Manejo de errores

La app contempla:

- validacion de texto vacio
- validacion de `voice_upload` solo `.wav`
- fallback de variante y voz por defecto
- advertencia clara si FFmpeg no esta disponible
- errores de carga de XTTS con diagnostico en `/health` y en los logs del job
- historial persistente aunque el job falle despues de iniciarse

## 7. Mejoras futuras

- integrar `MeloTTSService` bajo el mismo contrato `BaseTTSService`
- cola de trabajos persistente
- perfiles de locucion por proyecto
- preprocesado de numeros, siglas y terminos tecnicos
- mezcla con musica de cama y ducking
- waveform visual y corte manual de segmentos
