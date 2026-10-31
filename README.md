# Ghiền Đọc Comment Studio (ThreadViral v2)

Ứng dụng tự động hóa tạo video ngắn 9:16 (TikTok, Facebook Reels, YouTube Shorts) chuẩn phong cách kênh **Ghiền Đọc Comment** từ link bài viết Threads.

---

## 🚀 Tính năng nổi bật
- **Cào tự động 1-Click**: Tự động trích xuất bài viết gốc (Topic) + các bình luận nhiều tương tác nhất trên Threads bằng Playwright.
- **Dual-Text Card**: Thẻ trắng Threads giữ nguyên chữ viết tắt teen-code, nhưng giọng đọc AI (Edge TTS) đọc thành tiếng Việt tự nhiên, lách từ nhạy cảm.
- **Render Siêu Tốc Direct FFmpeg (~5s)**: Ghép video nền, nhạc nền BGM, avatar, watermark và meme reaction với tốc độ cực nhanh.
- **Hỗ trợ Điện thoại (iPhone & Android)**: Giao diện chuẩn PWA (Progressive Web App), có thể cài đặt trực tiếp lên màn hình chính điện thoại và dùng toàn màn hình.

---

## 📱 Cách chạy và dùng trên Điện thoại (iPhone / Android)

### Cách 1: Chạy trên máy tính và kết nối qua Wi-Fi (Nhanh nhất)
1. Chạy file `Mo_Ket_Noi_Dien_Thoai.bat` bằng quyền Administrator (chỉ làm 1 lần).
2. Chạy file `Chay_Server_Web_Va_Dien_Thoai.bat`.
3. Bấm **📱 Dùng trên Điện thoại** trên thanh điều hướng để quét mã QR hoặc truy cập địa chỉ IP LAN (`http://192.168.x.x:8000`).

### Cách 2: Deploy lên Cloud (Render.com / Hugging Face) để dùng 24/7 mọi lúc mọi nơi
1. Đẩy code lên GitHub.
2. Đăng nhập [Render.com](https://render.com) hoặc [Hugging Face Spaces](https://huggingface.co/spaces).
3. Chọn Repository này ➔ Deploy với môi trường **Docker**.
4. Bạn sẽ nhận được đường link HTTPS vĩnh viễn (ví dụ: `https://threadviral.onrender.com`), mở trên điện thoại bất cứ lúc nào qua 4G/5G!
