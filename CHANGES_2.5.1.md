# Camera TTS Multi-Vendor HACS v2.5.1

- Tăng timeout riêng cho PTZ theo thời lượng lệnh để tránh timeout giả ở lần lazy-start HCNetSDK đầu tiên.
- Không đổi polling/startup architecture: shared `aiohttp`, DataUpdateCoordinator, không RTSP/PTZ probe trong setup.
- Giữ domain/entity IDs và config entry tương thích ngược.
