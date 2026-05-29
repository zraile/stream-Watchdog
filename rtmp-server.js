const NodeMediaServer = require('node-media-server');

const config = {
  rtmp: {
    port: 1935,
    chunk_size: 60000,
    gop_cache: false,
    ping: 30,
    ping_timeout: 60
  },
  http: {
    port: 8000,
    allow_origin: '*'
  }
};

const nms = new NodeMediaServer(config);
nms.run();

console.log('✅ RTMP Sunucu başlatıldı → rtmp://localhost:1935/live/camera');
console.log('📊 HTTP Yönetim paneli → http://localhost:8000');
