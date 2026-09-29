# Camera TTS Multi-Vendor

Tích hợp Home Assistant dành cho Docker backend `camera-tts-ezviz`, hỗ trợ điều khiển âm thanh và các tính năng camera theo từng hãng.

## Tính năng

- Hỗ trợ **EZVIZ / Hikvision / Imou / Dahua**.
- Tạo `media_player` riêng cho từng camera.
- Phát TTS và media ra loa camera.
- Điều chỉnh âm lượng loa camera.
- Hỗ trợ PTZ với các camera/model tương thích.
- Hỗ trợ đàm thoại hai chiều qua go2rtc với camera tương thích.
- Hỗ trợ microphone camera cho Home Assistant Assist khi đã cấu hình `mic_url`.
- Tự nhận camera mới từ Docker sau khi backend được cập nhật, không cần xóa rồi thêm lại integration.
- Giao tiếp với Docker qua mạng nội bộ và được thiết kế để không mở RTSP/SDK camera trong quá trình Home Assistant khởi động.

## Yêu cầu

- Home Assistant **2026.9.0 trở lên**.
- Docker backend `camera-tts-ezviz` **v2.5.0 trở lên** được khuyến nghị.
- Home Assistant phải truy cập được địa chỉ IP và cổng API của Docker backend.
- `API_KEY` trong integration phải giống `API_KEY` cấu hình ở Docker.

## Cài đặt qua HACS

### Cài nhanh

1. Nhấn nút bên dưới để thêm vào HACS trên Home Assistant.

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=khaisilk1910&repository=camera_tts_ezviz_hacs&category=integration)

   - Sau khi thêm trong HACS và khởi động lại Home Assistant
     
   - Vào Settings -> Integrations -> Add integration nhập `Camera TTS Multi-Vendor` để thêm


### Cài thủ công
1. Mở **HACS** → **Integrations**.
2. Chọn **Custom repositories**.
3. Thêm repository:

   `https://github.com/khaisilk1910/camera_tts_ezviz_hacs`

4. Chọn loại **Integration**.
5. Tìm và cài **Camera TTS Multi-Vendor**.
6. Khởi động lại Home Assistant.
7. Vào **Settings → Devices & services → Add integration**.
8. Tìm **Camera TTS Multi-Vendor**.
9. Nhập:
   - **Docker API URL**: ví dụ `http://192.168.31.100:8124`
   - **API Key**: đúng với `API_KEY` của Docker backend.

Sau khi kết nối thành công, Home Assistant sẽ tự tạo các entity tương ứng với những camera đã khai báo trong Docker.

## Cập nhật

Khi có phiên bản mới:

1. Cập nhật Docker backend trước.
2. Cập nhật integration trong HACS.
3. Khởi động lại Home Assistant nếu HACS yêu cầu.

Không cần xóa integration hoặc cấu hình lại camera khi chỉ cập nhật phiên bản.
