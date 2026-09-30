# Camera TTS Multi-Vendor HACS v2.6.0

- Media player thêm `VOLUME_SET`, `VOLUME_STEP`, `VOLUME_MUTE` khi backend công bố `media_volume`.
- `volume_level` đọc/ghi theo chuẩn Home Assistant `0.0..1.0`.
- Thêm button Stop riêng theo camera và giữ `MediaPlayerEntityFeature.STOP` trên media player.
- Coordinator cập nhật volume/stop optimistic để UI phản hồi ngay, không chờ poll kế tiếp.
- Giữ Browse Media, Play Media và enqueue; không quảng cáo Pause/Seek/Resume không được backend hỗ trợ thật.
- `speaker_gain` được mô tả lại là Playback gain (DSP) để không nhầm với volume chuẩn.
- Manifest v2.6.0; tất cả Python/JSON đã được compile/parse kiểm tra.
