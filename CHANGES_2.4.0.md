# Camera TTS EZVIZ HACS 2.4.0 — reviewed

- Thêm entity `number` **Speaker gain / Khuếch đại loa** cho từng camera; không tạo polling riêng, dùng chung coordinator.
- Thêm Reconfigure để đổi Docker URL/API key mà không xóa integration, device hay entity.
- Media player quảng bá `MEDIA_ENQUEUE` khi backend báo hỗ trợ `queue_modes`. `MEDIA_ANNOUNCE` không được quảng bá vì backend chưa thể resume chính xác nội dung bị ngắt.
- Ánh xạ đầy đủ Home Assistant `ADD / NEXT / PLAY / REPLACE` sang Docker.
- `announce: true` vẫn được nhận như fallback `play` (ngắt hiện tại, giữ queue), nhưng không được khai báo là full announcement capability.
- Diagnostics có backend version/features; API key vẫn được che.
- Idle polling tăng từ 15 s lên 20 s, offline polling từ 30 s lên 60 s để giảm tải Home Assistant; khi đang phát vẫn 3 s.
- Giữ nguyên cơ chế tự phát hiện camera mới; entity gain mới cũng được tạo động ở lần coordinator refresh tiếp theo.
- Với Docker cũ không có `features`, gain entity chưa được tạo và queue capability mới không được quảng bá; sau khi nâng Docker, entity gain xuất hiện ở lần refresh kế tiếp.

## QA

- Python compile pass cho toàn bộ custom component.
- Manifest, strings, translations và HACS metadata parse pass.
- GitHub Actions workflow YAML parse pass.
- Môi trường rà soát không có Home Assistant runtime nên chưa chạy hassfest tại chỗ.
