#!/usr/bin/env python3
"""
Stream Watchdog - Ana Baslangic Noktasi
Tum servisler (RTMP Sunucu, ngrok TCP Tunnel, Watchdog) tek pencerede calisir.

Kullanim:
    python main.py
"""

import subprocess
import sys
import time
import logging
import signal
import threading
import re
from pathlib import Path
from datetime import datetime

# ─── LOG SISTEMI ────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LOG_DIR  = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_filename = LOG_DIR / f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG:    "\033[36m",
        logging.INFO:     "\033[32m",
        logging.WARNING:  "\033[33m",
        logging.ERROR:    "\033[31m",
        logging.CRITICAL: "\033[35m",
    }
    RESET = "\033[0m"
    BOLD  = "\033[1m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{color}{self.BOLD}{record.levelname:<8}{self.RESET}"
        record.name      = f"\033[37m{record.name}{self.RESET}"
        return super().format(record)

FMT      = "%(asctime)s [%(levelname)s] %(name)s » %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(ColorFormatter(FMT, datefmt=DATE_FMT))

file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setFormatter(logging.Formatter(FMT, datefmt=DATE_FMT))

logging.basicConfig(level=logging.DEBUG, handlers=[console_handler, file_handler])
log = logging.getLogger("Main")

# ─── YAPILANDIRMA ───────────────────────────────────────────────────────────
CONFIG = {
    # Kamera RTMP giris adresi (ngrok uzerinden gelecek)
    # Bu adres ngrok basladiktan sonra otomatik guncellenir
    "camera_url": "rtmp://localhost:1935/live/camera",

    # LOCAL MODE:
    #   True  → FFmpeg ciktisi localhost'a yazar, Streamlabs Media Source ile izlenir
    #   False → Dogrudan Twitch/YouTube'a yayinlar (output_url gerekli)
    "local_mode": True,

    # Harici platform URL (local_mode=False ise doldur)
    "output_url": "rtmp://live.twitch.tv/app/<YOUR_STREAM_KEY_HERE>",

    # Kamera baglantisi kopunca gosterilecek fallback gorsel
    "fallback_image": "fallback.jpg",

    # Kamera kontrol araligi (saniye)
    "probe_interval": 3,

    # Video ayarlari
    "width":         1920,
    "height":        1080,
    "fps":           30,
    "video_bitrate": "4000k",
    "audio_bitrate": "128k",
}
# ────────────────────────────────────────────────────────────────────────────


class ManagedProcess:
    """Alt surec yoneticisi."""

    def __init__(self, name: str, log_tag: str = None):
        self.name    = name
        self._tag    = log_tag or name
        self._proc   = None
        self._logger = logging.getLogger(self._tag)

    def start(self, cmd: list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL):
        self.stop()
        self._logger.info(f"Baslatiliyor: {' '.join(str(c) for c in cmd[:3])}...")
        self._proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
        self._logger.info(f"PID={self._proc.pid}")

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._logger.info(f"Durduruluyor (PID={self._proc.pid})")
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def pid(self):
        return self._proc.pid if self._proc else None


# ─── RTMP SUNUCU ────────────────────────────────────────────────────────────
class RTMPServer:
    """Node.js node-media-server sureci."""

    def __init__(self):
        self._proc   = ManagedProcess("RTMP", "RTMP")
        self._logger = logging.getLogger("RTMP")

    def start(self):
        script = BASE_DIR / "rtmp-server.js"
        if not script.exists():
            self._logger.error(f"rtmp-server.js bulunamadi: {script}")
            sys.exit(1)
        self._proc.start(["node", str(script)])
        self._logger.info("RTMP sunucu port 1935'te dinliyor")
        self._logger.info("HTTP panel: http://localhost:8000")

    def stop(self):
        self._proc.stop()

    def is_running(self) -> bool:
        return self._proc.is_running()


# ─── NGROK TCP TUNNEL ───────────────────────────────────────────────────────
class NgrokTunnel:
    """ngrok TCP tunnel sureci — RTMP icin gercek TCP destegi saglar."""

    def __init__(self, port: int = 1935):
        self._port   = port
        self._proc   = None
        self._host   = None
        self._tport  = None
        self._logger = logging.getLogger("ngrok")
        self._ready  = threading.Event()

    def start(self):
        self._logger.info(f"ngrok TCP tunnel baslatiliyor (port {self._port})...")
        self._proc = subprocess.Popen(
            ["ngrok", "tcp", str(self._port), "--log", "stdout", "--log-format", "logfmt"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        t = threading.Thread(target=self._read_output, daemon=True)
        t.start()

    def _read_output(self):
        """ngrok cikti satirlarini okur, tunnel adresini yakalar."""
        for line in self._proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            self._logger.debug(line)

            # ngrok logfmt formatinda url=tcp://X.tcp.ngrok.io:PORT satirini yakala
            match = re.search(r'url=tcp://([\w.\-]+):(\d+)', line)
            if match and not self._host:
                self._host  = match.group(1)
                self._tport = match.group(2)
                self._ready.set()
                rtmp = f"rtmp://{self._host}:{self._tport}/live/camera"
                self._logger.info("=" * 60)
                self._logger.info("  ngrok TCP Tunnel HAZIR!")
                self._logger.info(f"  TCP   : tcp://{self._host}:{self._tport}")
                self._logger.info(f"  RTMP  : {rtmp}")
                self._logger.info(f"  Kamerana su adresi gir:")
                self._logger.info(f"  >>> {rtmp} <<<")
                self._logger.info("=" * 60)

    def wait_for_url(self, timeout: int = 30) -> str | None:
        self._logger.info(f"ngrok tunnel URL bekleniyor (max {timeout}s)...")
        if self._ready.wait(timeout=timeout):
            return f"rtmp://{self._host}:{self._tport}/live/camera"
        self._logger.error("ngrok URL zamaninda alinamadi! Token dogru mu?")
        return None

    def stop(self):
        if self._proc and self._proc.poll() is None:
            self._logger.info("ngrok tunnel kapatiliyor...")
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def rtmp_url(self) -> str | None:
        if self._host and self._tport:
            return f"rtmp://{self._host}:{self._tport}/live/camera"
        return None


# ─── WATCHDOG ───────────────────────────────────────────────────────────────
class Watchdog:
    """Kamera RTMP akisini izler, canliya veya fallback'e gecer."""

    def __init__(self, cfg: dict):
        self.cfg         = cfg
        self._output_url = (
            "rtmp://localhost:1935/live/output"
            if cfg.get("local_mode")
            else cfg["output_url"]
        )
        self._live     = ManagedProcess("Canli Yayin", "FFmpeg-Live")
        self._fallback = ManagedProcess("Fallback",    "FFmpeg-Fallback")
        self._online   = False
        self._stop     = threading.Event()
        self._logger   = logging.getLogger("Watchdog")

    def update_camera_url(self, url: str):
        """ngrok adresi alindiktan sonra kamera URL'sini guncelle."""
        self.cfg["camera_url"] = url
        self._logger.info(f"Kamera URL guncellendi: {url}")

    def _probe(self) -> bool:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error",
                 "-i", self.cfg["camera_url"],
                 "-show_entries", "stream=codec_type",
                 "-of", "default=noprint_wrappers=1"],
                capture_output=True, timeout=5,
            )
            return r.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _live_cmd(self):
        c = self.cfg
        return [
            "ffmpeg", "-y", "-fflags", "+genpts",
            "-i", c["camera_url"],
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            "-b:v", c["video_bitrate"],
            "-vf", f"scale={c['width']}:{c['height']},fps={c['fps']}",
            "-c:a", "aac", "-b:a", c["audio_bitrate"],
            "-f", "flv", self._output_url,
        ]

    def _fallback_cmd(self):
        c = self.cfg
        img = Path(c["fallback_image"])
        if img.exists():
            vin = ["-loop", "1", "-framerate", str(c["fps"]), "-i", str(img)]
        else:
            self._logger.warning(f"'{img}' bulunamadi — siyah ekran kullaniliyor")
            vin = ["-f", "lavfi", "-i",
                   f"color=c=black:s={c['width']}x{c['height']}:r={c['fps']}"]
        return [
            "ffmpeg", "-y", *vin,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
            "-b:v", "500k",
            "-vf", f"scale={c['width']}:{c['height']},fps={c['fps']}",
            "-c:a", "aac", "-b:a", "64k",
            "-f", "flv", self._output_url,
        ]

    def _to_live(self):
        if self._online:
            return
        self._logger.info("Kamera CEVRIMICI — canli yayina gecildi")
        self._fallback.stop()
        self._live.start(self._live_cmd())
        self._online = True

    def _to_fallback(self):
        if not self._online:
            return
        self._logger.warning("Kamera CEVRIMDISI — fallback ekranina gecildi")
        self._live.stop()
        self._fallback.start(self._fallback_cmd())
        self._online = False

    def _ensure(self):
        if self._online and not self._live.is_running():
            self._logger.warning("Canli yayin coktu, yeniden baslatiliyor...")
            self._live.start(self._live_cmd())
        elif not self._online and not self._fallback.is_running():
            self._logger.warning("Fallback coktu, yeniden baslatiliyor...")
            self._fallback.start(self._fallback_cmd())

    def request_stop(self):
        self._stop.set()

    def run(self):
        self._logger.info(f"Kamera  : {self.cfg['camera_url']}")
        self._logger.info(f"Cikis   : {self._output_url}")
        self._logger.info("Fallback ekrani baslatiliyor, kamera bekleniyor...")
        self._fallback.start(self._fallback_cmd())

        while not self._stop.is_set():
            try:
                if self._probe():
                    self._to_live()
                else:
                    self._to_fallback()
                self._ensure()
                self._stop.wait(timeout=self.cfg["probe_interval"])
            except KeyboardInterrupt:
                break

        self._logger.info("Durduruluyor...")
        self._live.stop()
        self._fallback.stop()
        self._logger.info("Temiz cikis.")


# ─── ANA PROGRAM ────────────────────────────────────────────────────────────
def check_dependencies():
    deps = {
        "node":   "https://nodejs.org",
        "ngrok":  "https://ngrok.com/download",
        "ffmpeg": "https://ffmpeg.org/download.html",
        "ffprobe":"https://ffmpeg.org/download.html",
    }
    ok = True
    for tool, url in deps.items():
        r = subprocess.run(
            ["where" if sys.platform == "win32" else "which", tool],
            capture_output=True
        )
        if r.returncode != 0:
            log.error(f"'{tool}' bulunamadi! Yukle: {url}")
            ok = False
        else:
            log.debug(f"'{tool}' bulundu")
    return ok


def print_banner():
    print()
    print("\033[1;36m" + "=" * 60)
    print("   Stream Watchdog v2.1  —  ngrok TCP Modu")
    print("=" * 60 + "\033[0m")
    print(f"   Log dosyasi: {log_filename}")
    print("=" * 60)
    print()


def main():
    print_banner()

    log.info("Bagimliliklar kontrol ediliyor...")
    if not check_dependencies():
        log.critical("Eksik bagimliliklar var. Lutfen yukleyip tekrar deneyin.")
        sys.exit(1)

    if not CONFIG.get("local_mode") and "<YOUR_STREAM_KEY_HERE>" in CONFIG["output_url"]:
        log.error("main.py icindeki 'output_url' ayarina stream key'ini gir!")
        sys.exit(1)

    rtmp     = RTMPServer()
    tunnel   = NgrokTunnel(port=1935)
    watchdog = Watchdog(CONFIG)

    def shutdown(sig, frame):
        log.info("Kapatma sinyali alindi...")
        watchdog.request_stop()
        tunnel.stop()
        rtmp.stop()
        log.info("Tum servisler durduruldu. Cikiliyor.")
        sys.exit(0)

    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 1. RTMP Sunucu
    log.info("[1/3] RTMP Sunucu baslatiliyor...")
    rtmp.start()
    time.sleep(2)

    # 2. ngrok TCP Tunnel
    log.info("[2/3] ngrok TCP Tunnel baslatiliyor...")
    tunnel.start()
    ngrok_url = tunnel.wait_for_url(timeout=30)

    if ngrok_url:
        # Kamera URL'sini ngrok adresiyle guncelle
        watchdog.update_camera_url(ngrok_url)
        log.info(f"Kamerana su RTMP adresini gir:")
        log.info(f">>> {ngrok_url} <<<")
    else:
        log.warning("ngrok URL alinamadi. Kamera localhost uzerinden denenecek.")

    # 3. Watchdog
    log.info("[3/3] Watchdog baslatiliyor...")
    watchdog.run()

    tunnel.stop()
    rtmp.stop()
    log.info("Tum servisler durduruldu.")


if __name__ == "__main__":
    main()
