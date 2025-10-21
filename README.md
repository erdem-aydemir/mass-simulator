# MASS Protocol Simulator

Haberleşme Ünitesi (Communication Unit) simülasyonu - Entegrasyon test amaçlı.

## 🚀 Hızlı Başlangıç

### 1. RabbitMQ MQTT Plugin'i Aktifleştir

```bash
# rabbitmq_enabled_plugins dosyası oluştur
echo "[rabbitmq_mqtt,rabbitmq_management]." > rabbitmq_enabled_plugins
```

### 2. Docker Compose ile Başlat

```bash
docker-compose up --build
```

Bu komut şunları başlatır:
- **RabbitMQ** (MQTT broker) - Port 1883
- **RabbitMQ Management UI** - http://localhost:15672 (guest/guest)
- **MASS Simulator** - Port 8000

### 3. Alternatif: Sadece Simülatör (Kendi RabbitMQ'nuzu kullanın)

```bash
# Build
docker build -t mass-simulator .

# Run
docker run -d \
  -p 8000:8000 \
  -e MQTT_BROKER=your-rabbitmq-host \
  -e MQTT_PORT=1883 \
  -e MQTT_USERNAME=your-user \
  -e MQTT_PASSWORD=your-pass \
  -e DEVICE_SERIAL=TEST001 \
  mass-simulator
```

## 📡 MQTT Topic Yapısı

### Simülatörün Yayınladığı Topic:
- `mass/device/to_server` - HÜ → Merkez (identification, heartbeat, alarm, vb.)

### Simülatörün Dinlediği Topic:
- `mass/server/to_device` - Merkez → HÜ (read, configuration, vb.)

## 🎮 Dışarıdan Kontrol (HTTP API)

Simülatör çalışırken dışarıdan komut verebilirsiniz:

### Health Check
```bash
curl http://localhost:8000/health
```

### Manuel Alarm Gönder
```bash
curl -X POST http://localhost:8000/trigger/alarm \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_type": "alarm",
    "level": "warning",
    "incident_code": 310,
    "description": "Röle söküldü",
    "meter_serial": "12345678",
    "meter_brand": "EMH"
  }'
```

### Manuel Heartbeat Gönder
```bash
curl -X POST http://localhost:8000/trigger/heartbeat
```

### Ölçüm Cihazı Ekle
```bash
curl -X POST http://localhost:8000/device/meter/add \
  -H "Content-Type: application/json" \
  -d '{
    "protocol": "IEC62056",
    "type": "electricity",
    "brand": "EMH",
    "serialNumber": "12345678",
    "serialPort": "rs485-1",
    "initBaud": 300,
    "fixBaud": false,
    "frame": "7E1"
  }'
```

### Cihaz Durumunu Gör
```bash
curl http://localhost:8000/device/state
```

### Cihaz Sinyalini Güncelle
```bash
curl -X POST "http://localhost:8000/device/config?signal=18&cpu_temp=22"
```

## 🧪 Test Senaryoları

### Senaryo 1: İlk Bağlantı ve Identification
1. Simülatör başlatılır
2. RabbitMQ'ya bağlanır
3. Otomatik olarak `identification` mesajı gönderir
4. Client tarafınızdan `identification` talebi geldiğinde tekrar gönderir

### Senaryo 2: Periyodik Heartbeat
- Her 60 saniyede bir otomatik `heartbeat` gönderir
- Manuel tetikleme: `curl -X POST http://localhost:8000/trigger/heartbeat`

### Senaryo 3: Pull Readout Testi
Client'ınızdan şu mesajı gönderin:
```json
{
  "device": {
    "flag": "SIM",
    "serialNumber": "SIM001ABCDE12345"
  },
  "function": "read",
  "referenceId": "test-read-001",
  "request": {
    "directive": "ReadoutDirective1",
    "parameters": {
      "METERSERIALNUMBER": "12345678"
    }
  }
}
```

**Beklenen Yanıt:**
1. ACK mesajı
2. Readout response mesajı (mock data ile)

### Senaryo 4: Configuration Update
Client'ınızdan:
```json
{
  "device": {
    "flag": "SIM",
    "serialNumber": "SIM001ABCDE12345"
  },
  "function": "configuration",
  "referenceId": "test-config-001",
  "request": {
    "registered": true,
    "deviceDate": "2024-10-21 10:30:00"
  }
}
```

**Beklenen Yanıt:**
1. ACK mesajı
2. Notification mesajı (başarılı güncelleme)

### Senaryo 5: Push Alarm (Tetikle)
```bash
curl -X POST http://localhost:8000/trigger/alarm \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_type": "danger",
    "level": "critical",
    "incident_code": 302,
    "description": "Enerji kesintisi oldu"
  }'
```

## 📊 Desteklenen Fonksiyonlar

| Fonksiyon | Tip | Durum | Açıklama |
|-----------|-----|-------|----------|
| `identification` | Push/Pull | ✅ | İlk bağlantıda otomatik, talep üzerine |
| `heartbeat` | Push | ✅ | 60 saniyede bir otomatik |
| `ack` | Response | ✅ | Tüm mesajlara otomatik |
| `alarm` | Push | ✅ | HTTP API ile tetiklenir |
| `read` (readout) | Pull | ✅ | Mock data döner |
| `configuration` | Pull | ✅ | State günceller, notification gönderir |
| `schedule` | Pull | ✅ | add/list/remove |
| `notification` | Pull | ✅ | add/list/remove |
| `log` | Pull | ✅ | Mock log data döner |
| `write` | Pull | ⏳ | Gelecek versiyon |
| `reset` | Pull | ⏳ | Gelecek versiyon |
| `firmwareUpdate` | Pull | ⏳ | Gelecek versiyon |
| `directive` | Pull | ⏳ | Gelecek versiyon |
| `relay` | Pull | ⏳ | Gelecek versiyon |

## 🔧 Environment Variables

| Variable | Default | Açıklama |
|----------|---------|----------|
| `MQTT_BROKER` | localhost | RabbitMQ host |
| `MQTT_PORT` | 1883 | MQTT port |
| `MQTT_USERNAME` | - | MQTT kullanıcı adı |
| `MQTT_PASSWORD` | - | MQTT şifre |
| `DEVICE_SERIAL` | 0123456789ABCDE | Cihaz seri numarası |
| `DEVICE_FLAG` | XYZ | Cihaz marka kodu |
| `HEARTBEAT_INTERVAL` | 60 | Heartbeat aralığı (saniye) |
| `API_PORT` | 8000 | HTTP API portu |

## 📝 Log Örnekleri

### Başarılı Başlatma:
```
============================================================
🚀 MASS Protocol Simulator Starting
============================================================
🔌 Connecting to MQTT broker rabbitmq:1883
✅ Connected to MQTT broker
📥 Subscribed to mass/server/to_device
📤 Sent: identification
🆔 Identification sent
💓 Heartbeat thread started
🌐 Starting HTTP API on port 8000
```

### Mesaj Alışverişi:
```
📩 Received: #234${"device":{"flag":"SIM"...
🔧 Handling function: read
📤 Sent: ack
📖 Readout response sent for directive: ReadoutDirective1
```

## 🐛 Troubleshooting

### Problem: "MQTT not connected"
**Çözüm:** RabbitMQ ayakta mı kontrol edin:
```bash
docker ps | grep rabbitmq
curl http://localhost:15672  # Management UI
```

### Problem: "Connection refused"
**Çözüm:** RabbitMQ MQTT plugin aktif mi kontrol edin:
```bash
docker exec mass-rabbitmq rabbitmq-plugins list | grep mqtt
# [E*] rabbitmq_mqtt olmalı
```

### Problem: Mesaj alınmıyor
**Çözüm:** Topic'leri kontrol edin:
- Simülatör: `mass/device/to_server` - PUBLISH
- Simülatör: `mass/server/to_device` - SUBSCRIBE
- Client'ınız bu topic'lere uygun mu?

## 🧪 Entegrasyon Testi Örneği (Java)

```java
import org.eclipse.paho.client.mqttv3.*;

public class MASSClientTest {
    private static final String BROKER = "tcp://localhost:1883";
    private static final String CLIENT_ID = "test-client";
    private static final String TOPIC_TO_DEVICE = "mass/server/to_device";
    private static final String TOPIC_FROM_DEVICE = "mass/device/to_server";
    
    @Test
    public void testIdentificationFlow() throws Exception {
        MqttClient client = new MqttClient(BROKER, CLIENT_ID);
        client.connect();
        
        // Subscribe to device messages
        client.subscribe(TOPIC_FROM_DEVICE, (topic, msg) -> {
            String payload = new String(msg.getPayload());
            System.out.println("Received: " + payload);
            
            // Parse and assert
            // ...
        });
        
        // Request identification
        String request = wrapMessage("""
            {
                "device": {"flag": "SIM", "serialNumber": "SIM001ABCDE12345"},
                "function": "identification",
                "referenceId": "test-001"
            }
            """);
        
        client.publish(TOPIC_TO_DEVICE, request.getBytes(), 1, false);
        
        // Wait for response
        Thread.sleep(2000);
        
        client.disconnect();
    }
    
    private String wrapMessage(String json) {
        return "#" + json.length() + "$" + json;
    }
}
```

## 📚 Mesaj Formatı Detayları

### Genel Yapı:
```
#<length>$<json>

Örnek:
#134${"device":{"flag":"XYZ","serialNumber":"0123456789ABCDE"},...}
```

### Header (Her mesajda):
```json
{
  "device": {
    "flag": "XYZ",              // 3 karakter marka kodu
    "serialNumber": "0123456..."  // 15 karakter seri no
  },
  "function": "identification",   // Fonksiyon adı
  "referenceId": "uuid-here",     // Benzersiz ID
  "streaming": false              // Opsiyonel
}
```

### Identification Response:
```json
{
  "device": {...},
  "function": "identification",
  "referenceId": "...",
  "response": {
    "registered": false,
    "brand": "SimulatorBrand",
    "model": "SimV1.0",
    "protocolVersion": "1.0.0",
    "firmware": "1.01",
    "signal": 13,
    "deviceDate": "2024-10-21 10:30:00",
    "meters": [...],
    "schedules": [...]
  }
}
```

## 🎯 Geliştirme Roadmap

- [x] Temel MQTT haberleşme
- [x] Identification, Heartbeat, ACK
- [x] Read/Readout mock yanıtları
- [x] Configuration handling
- [x] Schedule yönetimi
- [x] HTTP API kontrolü
- [x] Docker containerization
- [ ] Directive engine (IEC62056 simülasyonu)
- [ ] Profile okuma (tarih aralıklı)
- [ ] Write fonksiyonu
- [ ] Relay control
- [ ] Çoklu cihaz simülasyonu
- [ ] Web dashboard

## 🤝 Katkıda Bulunma

Yeni özellik veya iyileştirme için issue açabilirsiniz.

## 📄 Lisans

MIT License - Test amaçlı kullanım için tasarlanmıştır.