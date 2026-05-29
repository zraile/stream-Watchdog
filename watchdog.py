import subprocess
import sys
import time
import logging
import signal
import threading
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("Watchdog")

# ─── YAPILANDIRMA ───────────────────────────────────────────────
CONFIG = {
    # Ev PC'deki RTMP sunucudan gelen kamera görüntüsü
    "camera_url":     "rtmp://localhost:1935/live/camera",

    # Streamlabs RTMP adresi ve stream key
    # Twitch için: rtmp://live.twitch.tv/app/YOUR_STREAM_KEY
    # YouTube için: rtmp://a.rtmp.youtube.com/live2/YOUR_STREAM_KEY
    # YOUR_STREAM_KEY yerine kendi stream key'ini gir
    "streamlabs_url": "rtmp://live.twitch.tv/app/<YOUR_STREAM_KEY_HERE>",

    # Bağlantı kopunca gösterilecek fallback görsel
    "fallback_image": "fallback.jpg",

    # Kaç saniyede bir kamera kontrol edilsin
    "probe_interval": 3,

    # Video çözünürlük ve FPS
    "width":  1920,
    "height": 1080,
    "fps":    30,

    # RTMP çıkış kalitesi
    "video_bitrate": "4000k",
    "audio_bitrate": "128k",
}
# ────────────────────────────────────────────────────────────────


class StreamProcess:
    """FFmpeg süreç yöneticisi."""

    def __init__(self, name: str):
        self.name = name
        self._proc = None

    def start(self, cmd: list):
        self.stop()
        log.info(f"[{self.name}] Başlatılıyor...")
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info(f"[{self.name}] PID={self._proc.pid}")

    def stop(self):
        if self._proc and self._proc.poll() is None:
            log.info(f"[{self.name}] Durduruluyor (PID={self._proc.pid})")
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None


class Watchdog:
    """RTMP kamera bağlantısını izler ve Streamlabs'e sürekli yayın yapar."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._live = StreamProcess("Canlı Yayın")
        self._fallback_proc = StreamProcess("Fallback")
        self._camera_online = False
        self._stop_event = threading.Event()

    def _probe_camera(self) -> bool:
        """ffprobe ile kameranın RTMP stream'inin aktif olup olmadığını kontrol et."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-i", self.cfg["camera_url"],
                    "-show_entries", "stream=codec_type",
                    "-of", "default=noprint_wrappers=1",
                ],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _live_cmd(self) -> list:
        """Canlı kamera yayınını Streamlabs'e aktaran FFmpeg komutu."""
        cfg = self.cfg
        return [
            "ffmpeg", "-y",
            "-fflags", "+genpts",
            "-i", cfg["camera_url"],
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-b:v", cfg["video_bitrate"],
            "-vf", f"scale={cfg['width']}:{cfg['height']},fps={cfg['fps']}",
            "-c:a", "aac",
            "-b:a", cfg["audio_bitrate"],
            "-f", "flv",
            cfg["streamlabs_url"],
        ]

    def _fallback_cmd(self) -> list:
        """Fallback görselini Streamlabs'e gönderen FFmpeg komutu."""
        cfg = self.cfg
        if Path(cfg["fallback_image"]).exists():
            video_input = [
                "-loop", "1",
                "-framerate", str(cfg["fps"]),
                "-i", cfg["fallback_image"],
            ]
        else:
            log.warning(f"'{cfg['fallback_image']}' bulunamadı — siyah ekran kullanılıyor")
            video_input = [
                "-f", "lavfi",
                "-i", f"color=c=black:s={cfg['width']}x{cfg['height']}:r={cfg['fps']}",
            ]

        return [
            "ffmpeg", "-y",
            *video_input,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-b:v", "500k",
            "-vf", f"scale={cfg['width']}:{cfg['height']},fps={cfg['fps']}",
            "-c:a", "aac",
            "-b:a", "64k",
            "-f", "flv",
            cfg["streamlabs_url"],
        ]

    def _switch_to_live(self):
        if self._camera_online:
            return
        log.info("📹 Kamera ÇEVRIMIÇI — canlı yayına geçildi")
        self._fallback_proc.stop()
        self._live.start(self._live_cmd())
        self._camera_online = True

    def _switch_to_fallback(self):
        if not self._camera_online:
            return
        log.warning("⚠️  Kamera ÇEVRIMDIŞI — fallback ekranına geçildi")
        self._live.stop()
        self._fallback_proc.start(self._fallback_cmd())
        self._camera_online = False

    def _ensure_running(self):
        """FFmpeg süreci çökmüşse yeniden başlat."""
        if self._camera_online and not self._live.is_running():
            log.warning("Canlı yayın çöktü, yeniden başlatılıyor...")
            self._live.start(self._live_cmd())
        elif not self._camera_online and not self._fallback_proc.is_running():
            log.warning("Fallback çöktü, yeniden başlatılıyor...")
            self._fallback_proc.start(self._fallback_cmd())

    def request_stop(self):
        """Watchdog döngüsünü güvenli şekilde durdur."""
        self._stop_event.set()

    def run(self):
        log.info("🚀 Watchdog başlatıldı")
        log.info(f"   Kamera  : {self.cfg['camera_url']}")
        log.info(f"   Çıkış   : {self.cfg['streamlabs_url']}")
        log.info("Kamera bağlantısı bekleniyor, fallback ekranı yayında...")
        self._fallback_proc.start(self._fallback_cmd())

        while not self._stop_event.is_set():
            try:
                if self._probe_camera():
                    self._switch_to_live()
                else:
                    self._switch_to_fallback()
                self._ensure_running()
                self._stop_event.wait(timeout=self.cfg["probe_interval"])
            except KeyboardInterrupt:
                break

        log.info("Kapatılıyor...")
        self._live.stop()
        self._fallback_proc.stop()
        log.info("Temiz çıkış.")


def main():
    wd = Watchdog(CONFIG)

    # Placeholder stream key kontrolü
    if "<YOUR_STREAM_KEY_HERE>" in CONFIG["streamlabs_url"]:
        log.error("❌ watchdog.py içindeki 'streamlabs_url' ayarına kendi stream key'ini girmeyi unutma!")
        sys.exit(1)

    signal.signal(signal.SIGINT, lambda s, f: wd.request_stop())
    signal.signal(signal.SIGTERM, lambda s, f: wd.request_stop())
    wd.run()


if __name__ == "__main__":
    main()
