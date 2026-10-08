import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    import yt_dlp
except ImportError:
    print("\n[ERROR] No se encontro yt-dlp.")
    print("Ejecuta primero el archivo EJECUTAR_DESCARGADOR_WINDOWS.bat para instalar dependencias.")
    input("\nPresiona ENTER para salir...")
    sys.exit(1)

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None


# ==========================
# CONFIGURACION GENERAL
# ==========================

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "descargas"
ARCHIVE_FILE = BASE_DIR / "historial_descargas.txt"
RAVEYARD_ARCHIVE_FILE = BASE_DIR / "historial_raveyard.txt"

DOWNLOAD_DIR.mkdir(exist_ok=True)

TOR_ENABLED = os.environ.get("DESCARGADOR_USAR_TOR", "").strip().lower() in {"1", "true", "s", "si", "y", "yes"}
TOR_PROXY = os.environ.get("DESCARGADOR_TOR_PROXY", "socks5h://127.0.0.1:9050").strip()
_TOR_SOCKET_CONFIGURADO = False

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

RAVEYARD_PRODUCT_PLAYERS = {
    "grind-hardgroove-samples": "https://grindhardgroove.vercel.app/",
    "rift-fx-suite": "https://riftfxsuite.vercel.app/",
}

RAVEYARD_PRODUCT_LIBRARIES = {
    "grind": "grindLibrary",
    "rift": "riftLibrary",
}

AUDIO_URL_RE = re.compile(r"\.(?:mp3|wav|flac|m4a|aac|ogg)(?:[?#]|$)", re.IGNORECASE)

FORMATOS = {
    "1": {
        "codec": "mp3",
        "quality": "320",
        "name": "MP3 320 kbps",
        "desc": "Recomendado para Serato: buena compatibilidad y tamano razonable.",
    },
    "2": {
        "codec": "wav",
        "quality": "0",
        "name": "WAV",
        "desc": "Archivo pesado. No mejora la calidad si la fuente viene comprimida.",
    },
    "3": {
        "codec": "flac",
        "quality": "0",
        "name": "FLAC",
        "desc": "Buena opcion si quieres conservar maxima calidad disponible.",
    },
    "4": {
        "codec": "m4a",
        "quality": "256",
        "name": "M4A/AAC",
        "desc": "Liviano y buena calidad, aunque menos universal que MP3.",
    },
}


def limpiar_url(texto: str) -> str:
    return texto.strip().strip('"').strip("'")


def limpiar_link(link: str) -> str:
    link = link.strip().strip("<>()[]{}").strip('"').strip("'")
    link = link.rstrip(".,;")
    return link.strip().strip('"').strip("'")


def extraer_links(texto: str):
    texto = limpiar_url(texto)
    links = re.findall(r"https?://\S+", texto)
    return [limpiar_link(link) for link in links]


def mostrar_header():
    print("=" * 70)
    print(" DESCARGADOR DE AUDIO - YOUTUBE / SOUNDCLOUD / BANDCAMP / RAVEYARD")
    print("=" * 70)
    print("Uso permitido: musica propia, libre, Creative Commons o con permiso.")
    print("Los archivos quedaran dentro de la carpeta: descargas/")
    if TOR_ENABLED:
        print(f"Modo Tor/proxy activo para HTTP/HTTPS: {TOR_PROXY}")
    print("=" * 70)


def pedir_texto(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        print("\nEntrada cerrada. Saliendo...")
        raise SystemExit(0)


def obtener_ffmpeg():
    if imageio_ffmpeg is not None:
        try:
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            if ffmpeg and Path(ffmpeg).exists():
                return ffmpeg
        except Exception:
            pass

    return shutil.which("ffmpeg")


def verificar_ffmpeg():
    ffmpeg = obtener_ffmpeg()

    if not ffmpeg:
        print("\n[ERROR] No se detecto FFmpeg.")
        print("Vuelve a ejecutar EJECUTAR_DESCARGADOR_WINDOWS.bat para instalar dependencias.")
        return None

    print(f"\nFFmpeg listo: {ffmpeg}")
    return ffmpeg


def configurar_proxy_tor():
    global _TOR_SOCKET_CONFIGURADO

    if not TOR_ENABLED or _TOR_SOCKET_CONFIGURADO:
        return True

    parsed = urlparse(TOR_PROXY)
    scheme = parsed.scheme.lower()
    if scheme not in {"socks5", "socks5h"}:
        print(f"\n[ERROR] Proxy no soportado para Tor: {TOR_PROXY}")
        print("Usa un proxy SOCKS5, por ejemplo: socks5h://127.0.0.1:9050")
        return False

    try:
        import socket
        import socks
    except ImportError:
        print("\n[ERROR] Falta PySocks para usar Tor desde Python.")
        print("En Ubuntu ejecuta: .venv/bin/python -m pip install PySocks")
        return False

    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9050
    rdns = scheme == "socks5h"

    try:
        with socket.create_connection((host, port), timeout=5):
            pass
    except OSError as error:
        print(f"\n[ERROR] No pude conectar al proxy SOCKS de Tor en {host}:{port}: {error}")
        print("Revisa que Tor este activo con: systemctl status tor")
        return False

    socks.set_default_proxy(
        socks.SOCKS5,
        host,
        port,
        rdns=rdns,
        username=parsed.username,
        password=parsed.password,
    )
    socket.socket = socks.socksocket
    _TOR_SOCKET_CONFIGURADO = True
    return True


def elegir_formato():
    print("\nElige formato de salida:\n")

    for key, data in FORMATOS.items():
        print(f"{key}) {data['name']}")
        print(f"   {data['desc']}")

    while True:
        opcion = pedir_texto("\nOpcion [1-4] | Recomendado para Serato: 1 = MP3 320: ").strip()

        if opcion == "":
            opcion = "1"

        if opcion in FORMATOS:
            formato = FORMATOS[opcion]
            print(f"\nFormato elegido: {formato['name']}")
            return formato

        print("Opcion invalida. Intenta nuevamente.")


def elegir_playlist():
    print("\nSi pegas una playlist o set completo:")
    respuesta = pedir_texto("Quieres descargar la playlist completa? [s/N]: ").strip().lower()
    return respuesta in ["s", "si", "y", "yes"]


def es_url_raveyard(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host in {"raveyardsounds.com", "www.raveyardsounds.com"} or host.endswith(".vercel.app")


def obtener_texto_url(url: str, timeout: int = 30) -> str:
    request = Request(url, headers=HTTP_HEADERS)

    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, "replace")


def descargar_url_a_archivo(url: str, destino: Path, timeout: int = 60):
    request = Request(url, headers=HTTP_HEADERS)

    with urlopen(request, timeout=timeout) as response:
        with destino.open("wb") as archivo:
            shutil.copyfileobj(response, archivo)


def extension_desde_url(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix
    if suffix and re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix):
        return suffix
    return ".audio"


def decodificar_js_string(valor: str) -> str:
    try:
        return json.loads(f'"{valor}"')
    except json.JSONDecodeError:
        return valor


def nombre_seguro(texto: str, predeterminado: str = "audio") -> str:
    texto = texto or predeterminado
    texto = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" .")

    if not texto:
        texto = predeterminado

    return texto[:180]


def obtener_slug_producto(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1].lower() if path else ""


def resolver_player_raveyard(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if host.endswith(".vercel.app"):
        return url

    html = obtener_texto_url(url)
    players = re.findall(r"https?://[A-Za-z0-9.-]+\.vercel\.app/?(?:\?[^\"'<>\s]*)?", html)

    if players:
        return players[0]

    slug = obtener_slug_producto(url)
    if slug in RAVEYARD_PRODUCT_PLAYERS:
        return RAVEYARD_PRODUCT_PLAYERS[slug]

    raise RuntimeError("No se encontro el reproductor de previews de Raveyard en esta pagina.")


def resolver_js_principal(player_url: str) -> tuple[str, str]:
    html = obtener_texto_url(player_url)
    script = re.search(r'<script[^>]+src=["\']([^"\']+index-[^"\']+\.js)["\']', html)

    if not script:
        raise RuntimeError("No se encontro el archivo JavaScript del reproductor.")

    js_url = urljoin(player_url, script.group(1))
    return js_url, obtener_texto_url(js_url)


def resolver_clave_producto(player_url: str, js_principal: str) -> str:
    parsed = urlparse(player_url)
    query = parse_qs(parsed.query)
    clave = (query.get("product") or query.get("genre") or [""])[0].strip().lower()

    if clave:
        return clave

    host = parsed.netloc.lower()
    match = re.search(rf'"{re.escape(host)}":"([^"]+)"', js_principal)

    if match:
        return match.group(1)

    raise RuntimeError("No se pudo identificar que pack de Raveyard usa este reproductor.")


def resolver_libreria_raveyard(player_url: str, js_principal_url: str, js_principal: str) -> tuple[str, str]:
    clave_producto = resolver_clave_producto(player_url, js_principal)

    config_match = re.search(
        rf"(?<![A-Za-z0-9_$]){re.escape(clave_producto)}:\{{load:z\(\"\.\/libraries\/([^\"]+)\"",
        js_principal,
    )
    nombre_libreria = None

    if config_match:
        nombre_libreria = config_match.group(1)
    elif clave_producto in RAVEYARD_PRODUCT_LIBRARIES:
        nombre_libreria = RAVEYARD_PRODUCT_LIBRARIES[clave_producto]

    if not nombre_libreria:
        raise RuntimeError(f"No se encontro la libreria del pack Raveyard: {clave_producto}")

    modulo_match = re.search(
        rf'"\.\/libraries\/{re.escape(nombre_libreria)}\.js":\(\)=>D\(\(\)=>import\("\.\/([^"]+\.js)"',
        js_principal,
    )

    if not modulo_match:
        raise RuntimeError(f"No se encontro el modulo descargable de la libreria: {nombre_libreria}")

    libreria_url = urljoin(js_principal_url, modulo_match.group(1))
    return libreria_url, obtener_texto_url(libreria_url)


def extraer_samples_desde_js(js_libreria: str):
    samples = []
    vistos = set()
    objetos = re.findall(r'\{id:"(?:\\.|[^"\\])*".*?\}', js_libreria)

    for objeto in objetos:
        campos = {
            key: decodificar_js_string(value)
            for key, value in re.findall(r'([A-Za-z_$][\w$]*):"((?:\\.|[^"\\])*)"', objeto)
        }
        link = campos.get("link", "")

        if not link or not AUDIO_URL_RE.search(link) or link in vistos:
            continue

        vistos.add(link)
        samples.append(
            {
                "id": campos.get("id") or link,
                "name": campos.get("name") or campos.get("filename") or "Raveyard sample",
                "filename": campos.get("filename") or campos.get("name") or "Raveyard sample",
                "link": link,
                "pack_name": campos.get("packName") or campos.get("pack") or "Raveyard",
                "type": campos.get("type") or "",
            }
        )

    return samples


def obtener_samples_raveyard(url: str):
    player_url = resolver_player_raveyard(url)
    js_principal_url, js_principal = resolver_js_principal(player_url)
    libreria_url, js_libreria = resolver_libreria_raveyard(player_url, js_principal_url, js_principal)
    samples = extraer_samples_desde_js(js_libreria)

    if not samples:
        raise RuntimeError("No se encontraron audios disponibles en el reproductor de Raveyard.")

    return {
        "player_url": player_url,
        "library_url": libreria_url,
        "samples": samples,
    }


def leer_historial_raveyard():
    if not RAVEYARD_ARCHIVE_FILE.exists():
        return set()

    return {
        line.strip()
        for line in RAVEYARD_ARCHIVE_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip()
    }


def registrar_historial_raveyard(registro: str):
    with RAVEYARD_ARCHIVE_FILE.open("a", encoding="utf-8") as archivo:
        archivo.write(registro + "\n")


def destino_sample_raveyard(sample, formato):
    codec = formato["codec"]
    carpeta = DOWNLOAD_DIR / codec.upper() / "Raveyard" / nombre_seguro(sample["pack_name"], "Raveyard")
    carpeta.mkdir(parents=True, exist_ok=True)

    base = Path(sample["filename"]).stem or sample["name"]
    return carpeta / f"{nombre_seguro(base, 'sample')}.{codec}"


def crear_comando_ffmpeg_raveyard(sample, destino: Path, formato, ffmpeg: str, entrada_audio: str | None = None):
    codec = formato["codec"]
    comando = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        entrada_audio or sample["link"],
        "-vn",
        "-metadata",
        f"title={sample['name']}",
        "-metadata",
        f"album={sample['pack_name']}",
        "-metadata",
        "artist=Raveyard Sounds",
    ]

    if codec == "mp3":
        comando.extend(["-codec:a", "libmp3lame", "-b:a", f"{formato['quality']}k"])
    elif codec == "m4a":
        comando.extend(["-codec:a", "aac", "-b:a", f"{formato['quality']}k"])
    elif codec == "wav":
        comando.extend(["-codec:a", "pcm_s16le"])
    elif codec == "flac":
        comando.extend(["-codec:a", "flac"])

    comando.append(str(destino))
    return comando


def descargar_raveyard_audio(url: str, formato, ffmpeg: str) -> bool:
    print("\nDetecte link de Raveyard. Buscando previews disponibles...")

    try:
        datos = obtener_samples_raveyard(url)
    except (RuntimeError, URLError, TimeoutError, OSError) as error:
        print(f"\n[ERROR] No pude leer los previews de Raveyard: {error}")
        return False

    samples = datos["samples"]
    historial = leer_historial_raveyard()
    codec = formato["codec"]
    descargados = 0
    omitidos = 0
    errores = 0

    print(f"Player detectado: {datos['player_url']}")
    print(f"Samples encontrados: {len(samples)}")
    print("Nota: Raveyard publica previews MP3; WAV/FLAC seran conversiones de esos previews.")

    for indice, sample in enumerate(samples, start=1):
        destino = destino_sample_raveyard(sample, formato)
        registro = f"{codec}\t{sample['id']}"

        if registro in historial and destino.exists():
            omitidos += 1
            continue

        if destino.exists() and destino.stat().st_size > 0:
            registrar_historial_raveyard(registro)
            historial.add(registro)
            omitidos += 1
            continue

        print(f"[{indice}/{len(samples)}] {sample['name']}")
        temporal = None
        entrada_audio = sample["link"]

        if TOR_ENABLED:
            descriptor, temporal_nombre = tempfile.mkstemp(
                suffix=extension_desde_url(sample["link"]),
                dir=BASE_DIR,
            )
            os.close(descriptor)
            temporal = Path(temporal_nombre)
            try:
                descargar_url_a_archivo(sample["link"], temporal)
                entrada_audio = str(temporal)
            except (URLError, TimeoutError, OSError) as error:
                errores += 1
                print(f"[ERROR] No pude descargar este sample por Tor: {error}")
                try:
                    temporal.unlink(missing_ok=True)
                except OSError:
                    pass
                continue

        comando = crear_comando_ffmpeg_raveyard(sample, destino, formato, ffmpeg, entrada_audio)
        resultado = subprocess.run(comando, cwd=BASE_DIR)

        if temporal is not None:
            try:
                temporal.unlink(missing_ok=True)
            except OSError:
                pass

        if resultado.returncode != 0:
            errores += 1
            print(f"[ERROR] Fallo este sample. Codigo: {resultado.returncode}")
            try:
                if destino.exists() and destino.stat().st_size == 0:
                    destino.unlink()
            except OSError:
                pass
            continue

        registrar_historial_raveyard(registro)
        historial.add(registro)
        descargados += 1

    print(
        f"\nRaveyard terminado: {descargados} descargado(s), "
        f"{omitidos} omitido(s), {errores} error(es)."
    )
    print(f"Carpeta: {DOWNLOAD_DIR / codec.upper() / 'Raveyard'}")
    return errores == 0


def crear_comando_yt_dlp(url, formato, descargar_playlist, ffmpeg):
    codec = formato["codec"]
    quality = formato["quality"]

    carpeta_formato = DOWNLOAD_DIR / codec.upper()
    carpeta_formato.mkdir(parents=True, exist_ok=True)

    comando = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--format",
        "bestaudio/best",
        "--output",
        str(carpeta_formato / "%(title).180B [%(id)s].%(ext)s"),
        "--windows-filenames",
        "--download-archive",
        str(ARCHIVE_FILE),
        "--retries",
        "10",
        "--fragment-retries",
        "10",
        "--continue",
        "--extract-audio",
        "--audio-format",
        codec,
        "--embed-metadata",
        "--ffmpeg-location",
        ffmpeg,
    ]

    if codec in {"mp3", "m4a"}:
        comando.extend(["--audio-quality", f"{quality}K"])

    if TOR_ENABLED:
        comando.extend(["--proxy", TOR_PROXY, "--downloader", "native"])

    if descargar_playlist:
        comando.append("--yes-playlist")
    else:
        comando.append("--no-playlist")

    comando.append(url)
    return comando


def descargar_audio(urls, formato, descargar_playlist, ffmpeg):
    print("\nIniciando descarga...")
    print("Carpeta:", DOWNLOAD_DIR)
    print("-" * 70)

    errores = 0

    for indice, url in enumerate(urls, start=1):
        if len(urls) > 1:
            print(f"\nDescargando {indice}/{len(urls)}: {url}")

        if es_url_raveyard(url):
            if not descargar_raveyard_audio(url, formato, ffmpeg):
                errores += 1
            continue

        comando = crear_comando_yt_dlp(url, formato, descargar_playlist, ffmpeg)
        resultado = subprocess.run(comando, cwd=BASE_DIR)

        if resultado.returncode != 0:
            errores += 1
            print(f"\n[ERROR] Fallo la descarga de este link. Codigo: {resultado.returncode}")

    if errores:
        print(f"\nTerminado con errores: {errores} de {len(urls)} link(s) fallaron.")
        print("\nSoluciones rapidas:")
        print("1) Vuelve a ejecutar el .bat para actualizar dependencias.")
        print("2) Verifica que el link sea publico o que tengas acceso.")
        print("3) Revisa que tu conexion a internet este funcionando.")
        return

    print("\nDescarga finalizada.")
    print(f"Revisa la carpeta: {DOWNLOAD_DIR}")


def main():
    if sys.version_info < (3, 10):
        print("[ERROR] Necesitas Python 3.10 o superior.")
        pedir_texto("Presiona ENTER para salir...")
        return

    mostrar_header()
    if not configurar_proxy_tor():
        pedir_texto("Presiona ENTER para salir...")
        return

    ffmpeg = verificar_ffmpeg()
    if not ffmpeg:
        pedir_texto("Presiona ENTER para salir...")
        return

    formato = elegir_formato()
    descargar_playlist = elegir_playlist()

    while True:
        print("\n" + "=" * 70)
        entrada = pedir_texto("Pega link de YouTube/SoundCloud/Bandcamp/Raveyard o escribe SALIR: ").strip()

        if entrada.lower() in ["salir", "exit", "q", "quit"]:
            print("\nSaliendo...")
            break

        urls = extraer_links(entrada)

        if not urls:
            print("\nNo detecte ningun link valido. Intenta nuevamente.")
            continue

        print("\nLinks detectados:")
        for i, url in enumerate(urls, start=1):
            print(f"{i}) {url}")

        descargar_audio(urls, formato, descargar_playlist, ffmpeg)


if __name__ == "__main__":
    main()
