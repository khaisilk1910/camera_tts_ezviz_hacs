# Camera TTS EZVIZ HACS v2.3.1

Home Assistant custom integration cho Docker backend **Camera TTS EZVIZ**.

Repository này chỉ chứa Home Assistant integration. HCNetSDK, Edge TTS, FFmpeg, queue và cache chạy trong Docker backend `camera-tts-ezviz`.

## Tính năng

- Tự đọc danh sách camera từ Docker qua `/cameras`.
- Tự tạo một `media_player` cho mỗi camera.
- Phát TTS trực tiếp bằng `media_player.play_media` với `media_content_type: tts`.
- Phát audio/nhạc từ HTTP/HTTPS URL.
- Browse và phát Home Assistant Media Sources.
- `media_player.media_stop` dừng phát và xóa queue camera.
- Hiển thị `idle`, `buffering`, `playing`.
- Camera thêm mới trong Docker được phát hiện tự động khi coordinator refresh.
- Camera đã xóa sẽ chuyển unavailable; có thể reload integration để dọn/đồng bộ giao diện.

## Yêu cầu

Docker backend phải chạy bản có các API:

```text
GET  /cameras
POST /say/<camera>
POST /media/<camera>
POST /stop/<camera>
```

Khuyến nghị Docker `v2.3.1` trở lên.




## Cài đặt qua HACS

Nhấn nút dưới đây để mở trực tiếp repository này trong HACS:

[![Mở repository trong HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=khaisilk1910&repository=camera_tts_ezviz_hacs&category=integration)

Sau đó:

1. Chọn **Download** trong HACS để cài đặt tích hợp.
2. Khởi động lại Home Assistant.
3. Vào **Settings → Devices & services → Add integration**.
4. Tìm **Camera TTS EZVIZ** và hoàn tất cấu hình theo giao diện.



## Cài bằng HACS

Trong HACS:

1. **Integrations** → menu → **Custom repositories**.
2. Repository: `https://github.com/khaisilk1910/camera_tts_ezviz_hacs`
3. Category: **Integration**.
4. Cài **Camera TTS EZVIZ**.
5. Restart Home Assistant.

Sau đó vào:

**Settings → Devices & services → Add integration → Camera TTS EZVIZ**

Nhập:

```text
Docker API URL: http://192.168.31.100:8124
API key:        API_KEY đang cấu hình trong Docker
```

Nếu Docker có:

```env
CAMERAS_JSON={"gate":{"ip":"192.168.31.59","user":"admin","password":"PASS1"},"yard":{"ip":"192.168.31.60","user":"admin","password":"PASS2"}}
```

Home Assistant sẽ tạo các entity dạng:

```text
media_player.camera_tts_gate
media_player.camera_tts_yard
```

Entity ID thực tế có thể được Home Assistant điều chỉnh nếu trùng tên; unique ID vẫn gắn theo config entry + camera ID.

## Phát TTS

```yaml
action: media_player.play_media
target:
  entity_id: media_player.camera_tts_gate
data:
  media_content_type: tts
  media_content_id: "Có người đang đứng trước cổng"
```

## Phát nhạc/audio URL

```yaml
action: media_player.play_media
target:
  entity_id: media_player.camera_tts_gate
data:
  media_content_type: music
  media_content_id: "https://example.com/music.mp3"
```

## Phát Home Assistant Media

Trong UI Automation/Script:

1. Chọn action **Media player: Play media**.
2. Chọn entity camera.
3. Browse **Media** và chọn file audio.

Integration resolve Media Source thành URL đầy đủ rồi gửi URL cho Docker để FFmpeg chuyển sang AAC camera.

## Dừng phát

```yaml
action: media_player.media_stop
target:
  entity_id: media_player.camera_tts_gate
```

## Cài thủ công

Copy:

```text
custom_components/camera_tts_ezviz
```

vào:

```text
/config/custom_components/camera_tts_ezviz
```

Restart Home Assistant rồi Add Integration như hướng dẫn trên.

## Cấu trúc repo

```text
camera_tts_ezviz_hacs/
├── custom_components/
│   └── camera_tts_ezviz/
│       ├── __init__.py
│       ├── api.py
│       ├── config_flow.py
│       ├── const.py
│       ├── coordinator.py
│       ├── media_player.py
│       ├── manifest.json
│       ├── strings.json
│       └── translations/
├── .github/workflows/validate.yml
├── hacs.json
└── README.md
```
