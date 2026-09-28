# Camera TTS EZVIZ HACS v2.3.2

Custom integration cho Home Assistant, kết nối tới Docker backend **Camera TTS EZVIZ** và tự tạo một `media_player` cho mỗi camera.

## Tính năng

- Tự đọc camera từ Docker qua `GET /cameras`.
- Tự tạo `media_player` khi thêm camera mới trong Docker.
- Phát TTS bằng `media_player.play_media` với `media_content_type: tts`.
- Phát nhạc/audio từ HTTP/HTTPS và Home Assistant Media Sources.
- `media_player.media_stop` dừng phát và xóa queue của camera.
- Trạng thái `idle`, `buffering`, `playing`.
- Camera bị xóa khỏi Docker chuyển `Unavailable`; device cũ có thể xóa trong Home Assistant.
- Có Diagnostics và tự che API key.

## Tối ưu cho Home Assistant

Bản `v2.3.2` được rà soát để hạn chế tải và tránh làm chậm Home Assistant:

- Chỉ dùng async `aiohttp` session dùng chung của Home Assistant; không dùng `requests`, `time.sleep`, subprocess hoặc file/network I/O đồng bộ trong event loop.
- `/cameras` có timeout tổng 4 giây và connect timeout tối đa 2 giây. Docker không hoạt động sẽ không giữ một request quá lâu.
- Dùng `async_config_entry_first_refresh()` theo cơ chế chuẩn của Home Assistant. Nếu Docker chưa sẵn sàng, config entry chuyển sang retry; event loop không bị block.
- Polling thích nghi: khoảng **3 giây khi playing/buffering**, **15 giây khi idle**, **30 giây khi backend offline**.
- `always_update=False`: dữ liệu không đổi thì không đánh thức/cập nhật lại tất cả entity.
- Sau TTS, `play_media` hoặc `stop`, trạng thái entity được cập nhật trong RAM ngay, không phát sinh thêm một request `/cameras` chỉ để refresh giao diện.
- API key sai dùng `ConfigEntryAuthFailed` + Re-authentication chuẩn, không retry vô hạn bằng key sai.
- Coordinator truyền `config_entry` rõ ràng, tương thích thay đổi DataUpdateCoordinator của Home Assistant 2026.8+.
- `runtime_data`, config entry unload, dynamic entities và local brand được dùng theo API Home Assistant hiện tại.

## Yêu cầu

Docker backend cần có:

```text
GET  /cameras
POST /say/<camera>
POST /media/<camera>
POST /stop/<camera>
```

Khuyến nghị Docker `v2.3.1` trở lên.

## Cài bằng HACS

1. Vào **HACS → Integrations → Custom repositories**.
2. Repository:

```text
https://github.com/khaisilk1910/camera_tts_ezviz_hacs
```

3. Category: **Integration**.
4. Cài **Camera TTS EZVIZ**.
5. Restart Home Assistant.
6. Vào **Settings → Devices & services → Add integration → Camera TTS EZVIZ**.

Nhập:

```text
Docker API URL: http://192.168.31.100:8124
API key:        API_KEY đang cấu hình trong Docker
```

Có thể dùng nút HACS:

[![Mở repository trong HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=khaisilk1910&repository=camera_tts_ezviz_hacs&category=integration)

## Camera tự đồng bộ

Nếu Docker có:

```env
CAMERAS_JSON={"gate":{"ip":"192.168.31.59","user":"admin","password":"PASS1"},"yard":{"ip":"192.168.31.60","user":"admin","password":"PASS2"}}
```

Home Assistant sẽ tạo media player tương ứng, ví dụ:

```text
media_player.camera_tts_gate
media_player.camera_tts_yard
```

Entity ID có thể được Home Assistant điều chỉnh nếu trùng tên; unique ID vẫn cố định theo config entry + camera ID.

Khi thêm camera vào Docker, integration tự phát hiện ở lần poll kế tiếp; không cần xóa và thêm lại integration.

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

Trong Automation/Script:

1. Chọn **Media player: Play media**.
2. Chọn media player của camera.
3. Browse **Media** và chọn file audio.

Integration resolve Media Source thành URL đầy đủ và gửi URL cho Docker backend.

## Dừng phát

```yaml
action: media_player.media_stop
target:
  entity_id: media_player.camera_tts_gate
```

## Khi Docker tạm thời offline

Không cần restart Home Assistant. Entity sẽ chuyển `Unavailable`; coordinator giảm polling xuống khoảng 30 giây. Khi Docker hoạt động lại, integration tự phục hồi ở lần update tiếp theo.

Nếu API key bị thay đổi, Home Assistant sẽ yêu cầu **Re-authenticate** thay vì phải xóa integration.

## Cài thủ công

Copy:

```text
custom_components/camera_tts_ezviz
```

vào:

```text
/config/custom_components/camera_tts_ezviz
```

sau đó restart Home Assistant và Add Integration.

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
│       ├── diagnostics.py
│       ├── media_player.py
│       ├── manifest.json
│       ├── strings.json
│       ├── brand/
│       │   └── icon.png
│       └── translations/
├── .github/workflows/validate.yml
├── hacs.json
├── LICENSE
└── README.md
```
