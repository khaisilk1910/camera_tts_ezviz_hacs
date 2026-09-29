# Camera TTS Multi-Vendor HACS v2.5.0

- Giữ domain `camera_tts_ezviz` để nâng cấp không phá entity/config cũ; đổi tên hiển thị thành Camera TTS Multi-Vendor.
- Thêm Assist Satellite native cho camera có `mic_url`.
- Thêm pipeline/VAD selectors, mic gain, mute mic và wake sound.
- Thêm PTZ buttons và service PTZ đầy đủ 10 hướng/zoom.
- Thêm service trả go2rtc intercom source.
- API client thêm PTZ, upload WAV, job wait và intercom source; toàn bộ dùng shared aiohttp bất đồng bộ.
- Thiết bị hiển thị manufacturer/model theo vendor.
- Diagnostics che `mic_url`.
- Polling/coordinator cũ vẫn giữ: 20 s idle, 3 s active, 60 s offline; không mở RTSP/PTZ trong startup.
- Assist announcement resolve `media-source://` và ký URL Home Assistant trước khi Docker tải media.
