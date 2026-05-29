# stream-Watchdog

Osmo Pocket 3 kamerasından **taşınabilir modem** üzerinden RTMP protokolü ile ev bilgisayarına görüntü gönderilir. Ev bilgisayarı bu görüntüyü alıp **Streamlabs** aracılığıyla Twitch/YouTube'a yayınlar. Kamera bağlantısı kesildiğinde Streamlabs'in yayını düşmemesi için bir **RTMP Watchdog Relay** sistemi kurar.

## Mimari

```
[Osmo Pocket 3 - Taşınabilir Modem]
      |
      | RTMP → Cloudflare Tunnel URL
      ↓
[Ev PC - Node-Media-Server (RTMP Sunucu) :1935]
      |
      | Watchdog izler
      | Kamera bağlı   → canlı stream iletir
      | Kamera kesildi → fallback ekranı yayınlar
      ↓
[FFmpeg Watchdog → Streamlabs RTMP]
      |
      ↓
[Twitch / YouTube]
```

## Gereksinimler

- **Node.js** (v16 veya üzeri) → [nodejs.org](https://nodejs.org)
- **Python** (3.8 veya üzeri) → [python.org](https://python.org)
- **FFmpeg** (PATH'te kurulu) → [ffmpeg.org](https://ffmpeg.org/download.html)
- **Cloudflare Tunnel** (`cloudflared`) → [Cloudflare Download](https://github.com/cloudflare/cloudflared/releases)

### FFmpeg PATH'e Ekleme (Windows)

1. FFmpeg'i indir ve bir klasöre çıkar (örn: `C:\ffmpeg`)
2. Sistem ortam değişkenlerine git: `Başlat → Ortam Değişkenleri → PATH`
3. `C:\ffmpeg\bin` yolunu ekle
4. Terminal'i yeniden aç ve `ffmpeg -version` ile doğrula

## Kurulum

### 1. Depoyu Klonla

```bash
git clone https://github.com/zraile/stream-Watchdog.git
cd stream-Watchdog
```

### 2. Node.js Bağımlılıklarını Yükle

```bash
npm install
```

### 3. Python Bağımlılıklarını Yükle

```bash
pip install -r requirements.txt
```

### 4. Fallback Görselini Oluştur

```bash
python create_fallback.py
```

Bu komut `fallback.jpg` dosyasını oluşturur. Kamera bağlantısı kesildiğinde bu görsel yayında gösterilir.

### 5. Stream Key'i Ayarla

`watchdog.py` dosyasını aç ve `CONFIG` bölümündeki `streamlabs_url` satırını düzenle:

**Twitch için:**
```python
"streamlabs_url": "rtmp://live.twitch.tv/app/YOUR_STREAM_KEY",
```

**YouTube için:**
```python
"streamlabs_url": "rtmp://a.rtmp.youtube.com/live2/YOUR_STREAM_KEY",
```

`YOUR_STREAM_KEY` yerine kendi stream key'ini yaz.

## Kamera RTMP Ayarı

### Cloudflare Tunnel URL'sini Alma

`start.bat` dosyasını çalıştırdıktan sonra **Cloudflare Tunnel** penceresinde şuna benzer bir URL görürsün:

```
https://abc123.trycloudflare.com
```

Bu URL TCP tüneli olduğu için kamerana girilecek RTMP adresi:

```
rtmp://abc123.trycloudflare.com:1935/live/camera
```

### Osmo Pocket 3 Ayarı

1. Kamerada **Ayarlar → Canlı Yayın → Platform** seç
2. Platform olarak **Custom RTMP** seç
3. RTMP URL olarak Cloudflare'den aldığın adresi gir:
   ```
   rtmp://abc123.trycloudflare.com:1935/live/camera
   ```
4. Stream key: `camera` (veya URL'ye dahil)

## Streamlabs Ayarı

Streamlabs'te herhangi bir değişiklik **gerekmez**. Watchdog, Streamlabs'e doğrudan bağlanır ve sürekli kesintisiz görüntü gönderir.

Mevcut Streamlabs ayarların (Twitch/YouTube stream key) olduğu gibi kalır.

## Başlatma Sırası

### Otomatik (Önerilen)

```
start.bat
```

Bu dosya tüm servisleri doğru sırayla başlatır.

### Manuel

```bash
# 1. RTMP Sunucuyu başlat
node rtmp-server.js

# 2. Cloudflare Tunnel başlat (yeni terminal)
cloudflared tunnel --url tcp://localhost:1935

# 3. Watchdog başlat (yeni terminal)
python watchdog.py
```

## Çalışma Mantığı

| Durum | Ne Olur |
|---|---|
| Kamera bağlandı | Watchdog fark eder (3 sn içinde), canlı yayına geçer |
| Kamera kesildi | Watchdog fark eder, fallback ekranı yayına girer |
| Kamera geri geldi | Otomatik olarak canlı yayına döner |
| FFmpeg çöktü | Watchdog süreci otomatik yeniden başlatır |
| Streamlabs | Hiçbir şekilde bağlantısı kesilmez |

## Sorun Giderme

### Kamera bağlantısı tanınmıyor

- Cloudflare Tunnel URL'sinin doğru girildiğinden emin ol
- `ffprobe rtmp://localhost:1935/live/camera` komutu ile yerel bağlantıyı test et
- Kameranın RTMP akışını başlattığından emin ol

### FFmpeg bulunamıyor hatası

- `ffmpeg -version` komutu çalışıyor mu kontrol et
- FFmpeg'in `PATH`'e eklendiğinden emin ol (kurulum adımına bak)

### Fallback ekranı görünmüyor

- `python create_fallback.py` ile `fallback.jpg` dosyasını oluştur
- `watchdog.py` ile aynı klasörde olduğundan emin ol

### Cloudflare Tunnel çalışmıyor

- `cloudflared` dosyasının indirildiğinden ve PATH'te olduğundan emin ol
- Güvenlik duvarının 1935 portuna izin verdiğini kontrol et

## Dosya Yapısı

```
stream-Watchdog/
├── rtmp-server.js      # Node-Media-Server RTMP sunucusu
├── watchdog.py         # Kamera izleme ve FFmpeg yönetimi
├── create_fallback.py  # Fallback görsel oluşturucu
├── start.bat           # Windows başlatma scripti
├── package.json        # Node.js bağımlılıkları
├── requirements.txt    # Python bağımlılıkları
├── .gitignore
└── README.md
```