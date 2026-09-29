# Camera TTS Multi-Vendor HACS v2.5.1

Custom integration Home Assistant cho Docker backend `camera-tts-ezviz` nhưng giữ nguyên domain `camera_tts_ezviz` để **không phá config entry/entity cũ**. Bản 2.5.1 hỗ trợ EZVIZ/Hikvision, Imou và Dahua.

## Tính năng

- Một `media_player` cho mỗi camera Docker, tự thêm camera mới ở lần coordinator refresh kế tiếp.
- TTS/media/queue và speaker gain như v2.4.0.
- Hiển thị `vendor`, transport status và PTZ protocol trong entity attributes.
- Camera có PTZ sinh 6 button: trái/phải/lên/xuống/zoom in/zoom out.
- Service `camera_tts_ezviz.ptz` hỗ trợ thêm 4 hướng chéo, speed và duration.
- Service `camera_tts_ezviz.get_intercom_source` trả go2rtc backchannel source cho đàm thoại hai chiều.
- Camera có `mic_url` sinh native `assist_satellite`, pipeline select, VAD sensitivity select, mute mic, mic gain và wake acknowledgement sound.
- Assist đọc mic bằng ffmpeg local; reply TTS được upload WAV xuống Docker để Docker tự chọn talk adapter đúng vendor.
- Diagnostics che API key và `mic_url` (vì RTSP URL có thể chứa user/password).

## Không làm chậm khởi động Home Assistant

- Setup chỉ có **một GET `/cameras` bất đồng bộ** bằng shared aiohttp session; timeout LAN ngắn 4 giây.
- Không gọi HCNetSDK, không probe PTZ và không mở RTSP trong config-entry setup.
- ffmpeg mic chỉ khởi chạy sau khi Assist entity đã được thêm vào HA và camera thật sự có `mic_url`.
- Mic stream bị đứng/đứt sẽ reopen có delay; pipeline lỗi ngay khi khởi chạy có exponential backoff tới 60 giây để tránh vòng lặp CPU.
- Coordinator dùng `always_update=False`; poll 20 giây khi idle, 3 giây khi đang phát và 60 giây khi Docker offline.
- PTZ/intercom chỉ tạo network traffic khi người dùng gọi action/service.

## Yêu cầu

Khuyến nghị Docker **v2.5.1+**. Backend cũ vẫn dùng media player/gain theo capability negotiation nhưng sẽ không có PTZ, Assist hoặc intercom.

Docker cần trả các capability mới qua `GET /cameras`:

```text
multi_vendor, ptz, audio_upload, assist_mic, intercom_exec
```

## Cài đặt

1. HACS → Integrations → Custom repositories.
2. Repository: `https://github.com/khaisilk1910/camera_tts_ezviz_hacs`
3. Category: Integration.
4. Cài **Camera TTS Multi-Vendor** và restart HA.
5. Settings → Devices & services → Add integration → Camera TTS Multi-Vendor.
6. Nhập Docker API URL và cùng `API_KEY` với stack.

Domain cũ vẫn là `camera_tts_ezviz`; nâng cấp từ v2.4.0 không cần xóa integration.

## Camera Docker ví dụ

```env
CAMERAS_JSON={"gate":{"vendors":"ezviz","ip":"192.168.31.59","user":"admin","password":"PASS1","ptz":true,"mic_url":"rtsp://admin:PASS1@192.168.31.59:554/Streaming/Channels/102"},"yard":{"vendors":"imou","ip":"192.168.31.60","user":"admin","password":"PASS2","ptz":true,"mic_url":"rtsp://admin:PASS2@192.168.31.60:554/cam/realmonitor?channel=1&subtype=1"}}
```

Khi sửa/thêm camera trong Docker và restart/update container, HA sẽ nhận camera ở lần poll kế tiếp; không cần xóa rồi thêm integration.

## PTZ

Các button PTZ cơ bản xuất hiện khi camera báo `capabilities.ptz=true`.

Service đầy đủ:

```yaml
action: camera_tts_ezviz.ptz
data:
  entity_id: media_player.camera_gate
  direction: up_left
  speed: 50
  duration: 0.35
```

Direction: `left`, `right`, `up`, `down`, `up_left`, `up_right`, `down_left`, `down_right`, `zoom_in`, `zoom_out`.

## Assist / voice

Đặt `mic_url` trong camera Docker. Integration tự tạo:

- `assist_satellite` cho camera.
- Pipeline selector.
- VAD sensitivity selector.
- Microphone gain 0…30 dB.
- Mute microphone switch.
- Wake acknowledgement sound switch.

Mic path:

```text
camera/go2rtc RTSP -> ffmpeg của HA -> PCM16 16 kHz -> native Assist pipeline
```

Reply path:

```text
HA TTS (WAV) -> POST /audio/<camera> -> Docker vendor adapter -> loa camera
```

Đường này cho phép Piper/STT/wake word local nếu chính Assist pipeline của bạn dùng các engine local.

## Đàm thoại hai chiều với go2rtc

Gọi service có response:

```yaml
action: camera_tts_ezviz.get_intercom_source
data:
  entity_id: media_player.camera_gate
  docker_host: 192.168.31.100
response_variable: intercom
```

`intercom.source` là dòng cần thêm vào cuối source list của camera trong `go2rtc.yaml`. `docker_host` là IP/hostname mà máy/container go2rtc gọi được tới Docker; nếu go2rtc dùng cùng host network với Docker có thể bỏ trống.

Docker nhận PCMA 8 kHz trên cổng `8125`, voice-gate và chỉ mở talk session khi có tiếng nói. Cách này tránh giữ talk channel mở suốt làm camera tắt mic chiều nghe.

## TTS local

Với Piper:

```yaml
action: tts.speak
target:
  entity_id: tts.piper
data:
  media_player_entity_id: media_player.camera_gate
  message: "Có người trước cổng"
```

Nếu dùng `media_content_type: tts` gửi text trực tiếp xuống Docker thì Docker vẫn dùng Edge TTS và cần Internet.

## Khi Docker offline

Entry không chặn event loop. Nếu backend không phản hồi, request setup/update có timeout; entity chuyển unavailable và coordinator backoff polling. Khi Docker trở lại integration tự phục hồi. API key sai sẽ kích hoạt re-authentication.

## Kiểm tra trước khi đóng gói

- Tất cả file Python custom component đã qua `py_compile`.
- API/platform structure được đối chiếu với dự án `imou-homeassistant` cung cấp và Home Assistant Assist patterns hiện tại.
- Backend v2.5.1 dùng PTZ HCNetSDK local cho EZVIZ/Hikvision và tiếp tục dùng shared aiohttp bất đồng bộ ở Home Assistant.

Xem `CHANGES_2.5.1.md`.
