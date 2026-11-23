"""Evaluacion sintetica LOCAL. No conecta a YouTube ni escribe archivos multimedia."""
import json
import pathlib
import subprocess
import threading
import time

DURACION = 20


def cpu():
    valores = dict(linea.split() for linea in pathlib.Path("/sys/fs/cgroup/cpu.stat").read_text().splitlines())
    return int(valores["usage_usec"]) / 1_000_000


def memoria():
    return int(pathlib.Path("/sys/fs/cgroup/memory.current").read_text())


# Fixture comprimida unicamente en RAM, fuera de la medicion de decodificacion.
fuente = subprocess.run([
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-filter_threads", "1",
    "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=24:duration={DURACION}",
    "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={DURACION}",
    "-c:v", "libvpx", "-threads", "1", "-deadline", "realtime", "-cpu-used", "8", "-b:v", "1200k",
    "-c:a", "libopus", "-b:a", "64k", "-f", "matroska", "pipe:1",
], capture_output=True, check=True).stdout


def medir(nombre, ancho, alto, negro=False):
    entrada = (["-re", "-f", "lavfi", "-i", f"color=c=black:s={ancho}x{alto}:r=20",
                "-re", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"] if negro else
               ["-threads", "1", "-re", "-i", "pipe:0"])
    comando = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-filter_threads", "1", *entrada,
               "-t", str(DURACION), "-vf", f"scale={ancho}:{alto},fps=20", "-c:v", "libx264",
               "-threads", "1", "-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p",
               "-b:v", "1200k", "-maxrate", "1200k", "-bufsize", "2400k", "-g", "40",
               "-c:a", "aac", "-b:a", "96k", "-ar", "48000", "-ac", "2",
               "-progress", "pipe:2", "-nostats", "-f", "flv", "pipe:1"]
    inicio, uso = time.monotonic(), cpu()
    proceso = subprocess.Popen(comando, stdin=subprocess.PIPE if not negro else subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    resultado = {}

    def comunicar():
        _, errores = proceso.communicate(input=fuente if not negro else None, timeout=90)
        resultado.update(codigo=proceso.returncode, progreso=errores.decode())

    hilo = threading.Thread(target=comunicar)
    hilo.start()
    pico = 0
    while hilo.is_alive():
        pico = max(pico, memoria())
        time.sleep(0.1)
    hilo.join()
    segundos, consumido = time.monotonic() - inicio, cpu() - uso
    datos = dict(linea.split("=", 1) for linea in resultado.get("progreso", "").splitlines() if "=" in linea)
    salida = int(datos.get("out_time_us", "0")) / 1_000_000
    print(json.dumps(dict(escenario=nombre, codigo=resultado.get("codigo"), duracion_s=round(segundos, 2),
        video_s=round(salida, 2), velocidad=round(salida / segundos, 3), cpu_un_nucleo_pct=round(consumido / segundos * 100, 1),
        memoria_contenedor_mib=round(pico / 1024**2, 1), frames=datos.get("frame"),
        nota=("Sintetico local, negro y silencio codificados a H264/AAC" if negro else
              "Sintetico local, decodificacion VP8/Opus y codificacion H264/AAC") + "; no mide conmutador ni RTMPS real")), flush=True)
    if resultado.get("codigo") != 0:
        raise SystemExit("Fallo el ensayo; no representa una medicion de capacidad valida")


for caso in (("negro_silencio_540p20", 960, 540, True),
             ("vp8_opus_a_540p20", 960, 540, False),
             ("vp8_opus_a_720p20", 1280, 720, False)):
    medir(*caso)
