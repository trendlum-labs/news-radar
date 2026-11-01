# News Radar

Experimento inicial de **YouTube Data API v3** para detectar qué cobertura existe en YouTube sobre una noticia reciente. No incluye todavía RSS, GDELT, X, seguimiento de canales, clasificación editorial ni notificaciones.

## Preparación

- Python 3.10 o superior (solo biblioteca estándar).
- Habilitar [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com) en Google Cloud y crear una API key. Restringirla a YouTube Data API.
- Configurar `YOUTUBE_API_KEY` en el entorno. **No subir la clave al repositorio.**

Windows PowerShell:

```powershell
$env:YOUTUBE_API_KEY = "TU_CLAVE"
python -m news_radar search "satellite unexpected reentry" --hours 24 --order date --max-results 50 --output results/search.json
```

Linux / macOS:

```bash
export YOUTUBE_API_KEY="TU_CLAVE"
python -m news_radar search "satellite unexpected reentry" --hours 24 --order relevance
```

Ejecutar los comandos desde la raíz del repositorio; no es necesario instalar paquetes.

## Comandos

**Una búsqueda** (1 llamada a `search.list`, hasta 50 vídeos devueltos):

```bash
python -m news_radar search "brief description of a specific event" --hours 6 --order date --with-details --output results/event.json
```

`--with-details` obtiene vistas y duración mediante **una llamada adicional** a `videos.list` (cuota general, distinta de la de búsquedas). `--language es` y `--region ES` son pistas para la relevancia, **no filtros estrictos por idioma**.

**Comparar actualidad e indexación** (2 llamadas a `search.list`):

```bash
python -m news_radar probe "brief description of a specific event" --hours 6 --output results/probe.json
```

Si ya tienes un vídeo público reciente que debería aparecer, pásalo explícitamente (solo el ID de 11 caracteres, sin playlist):

```bash
python -m news_radar probe "brief description of a specific event" --hours 6 --expected-id VIDEO_ID_11 --output results/probe.json
```

Puedes repetir `--expected-id` con varios vídeos; se verifican juntos en una única llamada a `videos.list`. El JSON indica si el vídeo está accesible por su ID y si aparece en la **primera página** de `relevance` y `date`.

## Interpretación y límites

- **0 vídeos devueltos no implica 0 vídeos publicados**. Los vídeos muy recientes pueden no aparecer en búsqueda; ambas ordenaciones pueden devolver resultados incompletos.
- `probe` solo inspecciona la **primera página** (hasta 50 resultados) de cada ordenación. No afirma que un vídeo ausente esté sin indexar.
- `relevanceLanguage` no limita estrictamente el idioma y `order=date` con filtros temporales puede devolver resultados incompletos.
- El programa **no descarta** una noticia por encontrar más de cinco vídeos; aún no evalúa competencia o potencial editorial.
- No hace llamadas automáticas: cada comando ejecuta exclusivamente las peticiones indicadas.
- Cuota predeterminada (junio de 2026): 100 llamadas diarias a `search.list`, 1 llamada por página de hasta 50 resultados; cuota general predeterminada de 10.000 unidades/día para `videos.list` y otros métodos. Comprueba las cuotas reales de tu proyecto en Google Cloud.
- Los horarios se guardan en UTC. Las claves quedan en el entorno, nunca en los JSON de salida.

## Pruebas sin API key

```bash
python -m unittest discover -s tests -v
```

Estas pruebas usan respuestas simuladas. **No validan todavía la cobertura real de YouTube ni la latencia de indexación**; eso requiere ejecutar los comandos anteriores con una clave propia.

Documentación oficial: [search.list](https://developers.google.com/youtube/v3/docs/search/list) · [videos.list](https://developers.google.com/youtube/v3/docs/videos/list) · [cuotas](https://developers.google.com/youtube/v3/determine_quota_cost).
