# 🚀 MASS Simulator - Hızlı Başlangıç (5 Dakika)

## Ön Gereksinimler

- Docker ve Docker Compose
- Make (opsiyonel, kolaylık için)
- curl (test için)

## 1️⃣ Adım: Klonla ve Başlat

```bash
# Proje dizinine git
cd mass-simulator

# Tek komutla başlat
make dev-setup
```

**Make yoksa:**
```bash
# RabbitMQ MQTT plugin aktifleştir
echo "[rabbitmq_mqtt,rabbitmq_management]." > rabbitmq_enabled_plugins

# Build ve başlat
docker-compose up --build -d

# Logları takip et
docker-compose logs -f
```

## 2️⃣ Adım: Doğrula

30 saniye bekledikten sonra:

```bash
# Health check
curl http://localhost:8000/health

# Beklenen çıktı:
# {
#   "status": "healthy",
#   "mqtt_connected": true,
#   "device_serial": "SIM001ABCDE12345"
# }
```

## 3️⃣ Adım: İlk Testler

### Manuel Heartbeat Tetikle
```bash
curl -X POST http://localhost:8000/trigger/heartbeat
```

### Alarm Gönder
```bash
curl -X POST http://localhost:8000/trigger/alarm \
  -H "Content-Type: application/json" \
  -d '{
    "alarm_type": "alarm",
    "level": "warning",
    "incident_code": 310,
    "description": "Röle söküldü"
  }'
```

### Cihaz Durumunu Görüntüle
```bash
curl http://localhost:8000/device/state
```

## 4️⃣ Adım: MQTT Mesajlarını Gözlemle

### RabbitMQ Management UI
- URL: http://localhost:15672
- Kullanıcı: `guest`
- Şifre: `guest`

**Exchanges** bölümünden `amq.topic` seçin ve:
- Publish topic: `mass/server/to_device`
- Subscribe topic: `mass/device/to_server`

### Örnek Mesaj Gönder (RabbitMQ UI'dan)

**Identification Talebi:**
```json
#134${"device":{"flag":"SIM","serialNumber":"SIM001ABCDE12345"},"function":"identification","referenceId":"test-001"}
```

**Read Talebi:**
```json
#234${"device":{"flag":"SIM","serialNumber":"SIM001ABCDE12345"},"function":"read","referenceId":"test-002","request":{"directive":"ReadoutDirective1","parameters":{"METERSERIALNUMBER":"12345678"}}}
```

## 5️⃣ Adım: Python Client ile Test

```bash
# Client'ı çalıştır
make client

# Veya
python example_client.py
```

Bu client otomatik olarak:
1. ✅ Identification talep eder
2. ✅ Configuration günceller
3. ✅ Schedule ekler
4. ✅ Read talebi gönderir
5. ✅ Log talep eder

## 🎯 Kendi Entegrasyonunuzu Test Edin

### Java ile Bağlanma
```java
String broker = "tcp://localhost:1883";
MqttClient client = new MqttClient(broker, "my-client");
client.connect();

// Subscribe
client.subscribe("mass/device/to_server", (topic, msg) -> {
    String payload = new String(msg.getPayload());
    // Parse ve işle
});

// Publish
String message = "#100${\"device\":{...},\"function\":\"identification\"}";
client.publish("mass/server/to_device", message.getBytes(), 1, false);
```

### .NET ile Bağlanma
```csharp
var factory = new MqttFactory();
var mqttClient = factory.CreateMqttClient();

var options = new MqttClientOptionsBuilder()
    .WithTcpServer("localhost", 1883)
    .Build();

await mqttClient.ConnectAsync(options);

// Subscribe
await mqttClient.SubscribeAsync("mass/device/to_server");

// Publish
var message = new MqttApplicationMessageBuilder()
    .WithTopic("mass/server/to_device")
    .WithPayload("#100${\"device\":{...}}")
    .Build();
    
await mqttClient.PublishAsync(message);
```

## 📊 Monitoring

### Logları İzle
```bash
# Tüm loglar
make logs

# Sadece simulator
make logs-sim

# Sadece RabbitMQ
make logs-rabbit
```

### Durumu Kontrol Et
```bash
make status
```

### Health Check (Sürekli)
```bash
watch -n 2 'curl -s http://localhost:8000/health | jq'
```

## 🛠️ Makefile Komutları

| Komut | Açıklama |
|-------|----------|
| `make up` | Servisleri başlat |
| `make down` | Servisleri durdur |
| `make logs` | Logları göster |
| `make restart` | Yeniden başlat |
| `make test` | Test suite çalıştır |
| `make clean` | Tümünü temizle |
| `make health` | Health check |
| `make state` | Cihaz durumu |
| `make trigger-alarm` | Test alarmı |
| `make rabbitmq-ui` | Management UI aç |

## 🐛 Sorun Giderme

### "Connection refused"
```bash
# RabbitMQ ayakta mı?
docker ps | grep rabbitmq

# MQTT plugin aktif mi?
docker exec mass-rabbitmq rabbitmq-plugins list | grep mqtt
# [E*] rabbitmq_mqtt olmalı
```

### "mqtt_connected: false"
```bash
# Simülatör loglarını kontrol et
docker logs mass-simulator

# RabbitMQ loglarını kontrol et
docker logs mass-rabbitmq

# Simülatörü yeniden başlat
make restart-sim
```

### Mesajlar Gözükmuyor
```bash
# Topic'leri kontrol et
# Varsayılan:
# - Device → Server: mass/device/to_server
# - Server → Device: mass/server/to_device

# Environment variable'ları kontrol et
docker exec mass-simulator env | grep TOPIC
```

## 🎓 Sonraki Adımlar

1. ✅ **README.md** - Detaylı dokümantasyon
2. ✅ **example_client.py** - Daha fazla örnek
3. ✅ **test_simulator.sh** - Otomatik testler
4. 📝 Kendi test senaryolarınızı yazın
5. 🔧 Simülatörü ihtiyacınıza göre customize edin

## 💡 Pro Tips

### Çoklu Cihaz Simülasyonu
```bash
# İkinci simülatör başlat
docker run -d \
  -p 8001:8000 \
  -e MQTT_BROKER=rabbitmq \
  -e DEVICE_SERIAL=SIM002 \
  -e API_PORT=8000 \
  --network mass-simulator_default \
  mass-simulator
```

### Debug Mode
```bash
# Simülatörü debug modda çalıştır
docker-compose up mass-simulator
# (Ctrl+C ile durdurun)
```

### Production-like Test
```bash
# Heartbeat'i 10 saniyeye düşür
docker run -d \
  -p 8000:8000 \
  -e MQTT_BROKER=your-broker.com \
  -e HEARTBEAT_INTERVAL=10 \
  mass-simulator
```

## ✅ Başarılı Kurulum Kontrolü

Aşağıdaki komutların hepsi başarılı dönmeli:

```bash
curl http://localhost:8000/health
curl http://localhost:15672  # RabbitMQ UI
curl -X POST http://localhost:8000/trigger/heartbeat
make test  # Tüm testler geçmeli
```

---

**🎉 Tebrikler! MASS Simulator çalışıyor.**

Sorularınız için GitHub Issues kullanabilirsiniz.