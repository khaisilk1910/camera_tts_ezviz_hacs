# Camera TTS Multi-Vendor — Home Assistant Marketplace v2.7.0

Custom integration cho **Home Assistant 2026.11+** và **Marketplace** (thay cho HACS độc lập ở Home Assistant 2026.11), kết nối với Docker backend `camera-tts-ezviz` để điều khiển loa/mic của EZVIZ/Hikvision, Imou và Dahua.

**Giữ nguyên domain `camera_tts_ezviz`, config entry và unique ID cũ**, không cần xóa cấu hình hoặc tạo lại automation khi cập nhật. Đây là bản mã nguồn integration; không chứa Docker backend.

## Tính năng

- Một `media_player` cho mỗi camera Docker, tự thêm camera mới ở lần coordinator refresh kế tiếp.
- TTS/media/queue; media URL dài dùng streaming khi backend v2.6.0+.
- `media_player` chuẩn Home Assistant có volume 0–100%, volume up/down, mute, Stop, Browse Media, Play Media và enqueue theo capability backend.
- Có button `Dừng phát ngay` riêng cho từng camera; đồng thời media player vẫn quảng cáo `STOP` để card chuẩn của Home Assistant hiển thị control Stop.
- `speaker_gain` cũ vẫn giữ làm **Playback gain (DSP)** nâng cao; không còn dùng nó thay cho volume chuẩn của media player.
- Hiển thị `vendor`, transport status, `volume_backend` và PTZ protocol trong entity attributes.
- Camera có PTZ sinh 6 button: trái/phải/lên/xuống/zoom in/zoom out.
- Service `camera_tts_ezviz.ptz` hỗ trợ thêm 4 hướng chéo, speed và duration.
- Service `camera_tts_ezviz.get_intercom_source` trả go2rtc backchannel source cho đàm thoại hai chiều.
- Camera có `mic_url` sinh native `assist_satellite`, pipeline select, VAD sensitivity select, mute mic, mic gain và wake acknowledgement sound.
- Assist đọc mic bằng ffmpeg local; reply TTS được upload WAV xuống Docker để Docker tự chọn talk adapter đúng vendor.
- Diagnostics che API key và `mic_url` (vì RTSP URL có thể chứa user/password).

## Không làm chậm khởi động Home Assistant

- `async_setup_entry` chỉ đăng ký platform và coordinator, **không thực hiện request mạng**. Poll `/cameras` đầu tiên được lên lịch **sau sự kiện Home Assistant STARTED**; nếu thêm integration trong khi HA đã chạy, poll thực hiện ngay trong background task.
- Nếu Docker chưa bật, HA vẫn tiếp tục khởi động. Các camera/entity xuất hiện sau lần poll đầu thành công, thay vì phải đợi backend online trong giai đoạn khởi động.
- Không gọi HCNetSDK, không probe PTZ và không mở RTSP trong config-entry setup.
- ffmpeg mic chỉ khởi chạy sau khi Assist entity đã được thêm vào HA. Có thể tắt tự khởi động listener qua nút **Configure** trong integration.
- Mic stream bị đứng/đứt sẽ reopen có delay; pipeline lỗi ngay khi khởi chạy có exponential backoff tới 60 giây để tránh vòng lặp CPU.
- Coordinator dùng `always_update=False`; poll idle **mặc định 20 giây** (có thể chỉnh **10–120 giây**), 3 giây khi đang phát và 60 giây khi Docker offline. Thay đổi capability backend cũng được nhận diện.
- PTZ/intercom chỉ tạo network traffic khi người dùng gọi action/service.

## Yêu cầu

Khuyến nghị Docker **v2.6.0+** để có media streaming, instant Stop và volume chuẩn. Backend v2.5.x vẫn dùng được PTZ/Assist/intercom theo capability negotiation nhưng chưa có các tính năng media-volume/streaming mới.

Docker cần trả các capability mới qua `GET /cameras`:

```text
queue_modes, runtime_gain, media_volume, streaming_media, instant_stop, multi_vendor, ptz, audio_upload, assist_mic, intercom_exec
```

## Cài đặt qua Home Assistant Marketplace (2026.11+)

1. Trong Home Assistant mở **Settings → Marketplace**.
2. Tìm **Camera TTS Multi-Vendor**. Nếu repository chưa được liệt kê, thêm repository tùy chỉnh `https://github.com/khaisilk1910/camera_tts_ezviz_hacs` với loại **Integration** (vị trí nút thêm repository tùy chỉnh tùy phiên bản giao diện Marketplace).
3. Cài integration. Với bản cài mới, Marketplace có thể nạp integration không cần restart; **sau khi cập nhật mã nguồn của integration đã cài, nên khởi động lại Home Assistant** để Python module mới có hiệu lực.
4. **Settings → Devices & services → Add integration → Camera TTS Multi-Vendor**.
5. Nhập URL Docker API (ví dụ `http://192.168.31.100:8124`) và `API_KEY` tương ứng. Kiểm tra kết nối được chạy lúc thêm/sửa cấu hình, không chạy khi HA khởi động lại.

**Nâng cấp từ HACS cũ:** Home Assistant 2026.11 **tự động chuyển HACS và các custom repositories đã cài sang Marketplace**. Không cần gỡ HACS hoặc xóa config entry thủ công; hãy cập nhật **cùng repository** để giữ entity/automation hiện có. Xem tài liệu Marketplace chính thức.

**Để phát hành trên Marketplace:** upload nội dung mã nguồn trong file ZIP này lên **repository GitHub public**, với `hacs.json` và `custom_components/camera_tts_ezviz/` ở thư mục gốc, sau đó tạo GitHub release/tag `2.7.0` đúng với `manifest.json`. ZIP tải trực tiếp này **không phải** file mà Marketplace tự cài từ máy tính người dùng.

**Cấu hình giao diện:** Settings → Devices & services → Camera TTS Multi-Vendor → **Configure** để chỉnh chu kỳ lấy dữ liệu và tự nghe Assist. Dùng menu **Reconfigure** để thay URL/API key và flow **Reauthenticate** khi key thay đổi. Cả ba dùng UI chuẩn, có bản dịch Việt/Anh.

**Giới hạn:** Tắt tự nghe Assist sẽ không mở ffmpeg/RTSP. Khi đó action Announce vẫn hoạt động nhưng action Start conversation sẽ không khả dụng cho đến khi bật lại tuỳ chọn.

## Camera Docker ví dụ

```env
CAMERAS_JSON={"gate":{"vendors":"ezviz","ip":"192.168.31.59","user":"admin","password":"PASS1","ptz":true,"mic_url":"rtsp://admin:PASS1@192.168.31.59:554/Streaming/Channels/102"},"yard":{"vendors":"imou","ip":"192.168.31.60","user":"admin","password":"PASS2","ptz":true,"mic_url":"rtsp://admin:PASS2@192.168.31.60:554/cam/realmonitor?channel=1&subtype=1"}}
```

Khi sửa/thêm camera trong Docker và restart/update container, HA sẽ nhận camera ở lần poll kế tiếp; không cần xóa rồi thêm integration.

## Media player / volume / Stop

`media_player` dùng đúng API hiện tại của Home Assistant: `volume_level` là `0.0..1.0` và chỉ quảng cáo các feature backend làm được. Không quảng cáo Pause/Seek/Resume vì camera VoiceTalk không có vị trí phát có thể resume chính xác.

- EZVIZ/Hikvision: slider ưu tiên volume phần cứng HCNetSDK; nếu camera từ chối lệnh volume, Docker fallback DSP software.
- Imou/Dahua: software-volume; với media streaming v2.6.0 thay đổi có hiệu lực trong khi bài đang phát.
- Stop gọi `/stop/<camera>` và Docker có thể hủy cả trạng thái Buffering.
- Home Assistant quyết định bố cục card, nên integration không thể ép một button entity nằm đúng pixel bên cạnh slider. Trên card media-player chuẩn, Stop/volume cùng thuộc một entity; button `Dừng phát ngay` riêng được cung cấp để bạn đặt cạnh slider trên dashboard nếu muốn.

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

Entry không chặn khởi động. Nếu backend không phản hồi, poll bất đồng bộ có timeout 4 giây; entity chuyển unavailable và coordinator backoff polling 60 giây. Khi Docker trở lại integration tự phục hồi. API key sai sẽ kích hoạt re-authentication.

## Logs và kiểm tra lỗi

1. **Settings → System → Logs** để xem lỗi Camera TTS, Docker offline, xác thực, hoặc Assist/ffmpeg bị gián đoạn.
2. Khi cần thông tin chi tiết, thêm vào `configuration.yaml`:

   ```yaml
   logger:
     default: warning
     logs:
       custom_components.camera_tts_ezviz: debug
   ```

   Restart HA sau khi lưu. Chỉ để DEBUG khi điều tra lỗi vì log nhiều hơn.
3. Vào integration → menu ba chấm → **Download diagnostics** để xuất trạng thái, version và feature backend, chu kỳ cập nhật và trạng thái transport. Chức năng này **không gọi HTTP**; các URL mic/RTSP, key và thông tin nhạy cảm không được xuất raw.
4. Đối chiếu Docker HTTP `/cameras`: phải trả JSON object chứa `cameras` là list, mỗi camera có `id` duy nhất; `features` nếu có phải là list string. JSON sai sẽ bị báo lỗi thay vì bị hiểu nhầm là camera đã bị xóa.

## Kiểm thử và giới hạn xác nhận

Bản 2.7.0 đã được biên dịch với Python 3.13, vượt qua **36 pytest** cho HTTP API, auth, response lỗi, timeout, che thông tin nhạy cảm, validation URL và các hợp đồng code cần để không chặn HA startup. Workflow GitHub Actions chạy **pytest + hassfest + HACS validator** để bắt lỗi khi commit. API đặc biệt của VAD selector đã được cập nhật theo chữ ký Home Assistant 2026.11.

**Lưu ý:** Không có hệ thống Home Assistant 2026.11 đang chạy, Docker backend hoặc thiết bị camera thực trong môi trường kiểm thử này; do đó **chưa thể xác nhận end-to-end Assist / PTZ / phát TTS / HACS Marketplace thực tế**. Cần chạy Actions và kiểm thử bằng camera thật sau khi triển khai.

Xem `CHANGES_2.7.0.md` để biết chi tiết.
