# UGC Agents — Dịch vụ AI

Đây là service **agents** của NodeZ Hub — tập hợp các trợ lý AI giúp **tự động hóa kiểm duyệt và nghiệp vụ nghiệm thu** cho nền tảng quản lý nội dung UGC.

Service này không lưu trữ dữ liệu nghiệp vụ; nó nhận yêu cầu từ frontend/backend, gọi mô hình ngôn ngữ và trả kết quả về cho backend xử lý tiếp.

## Service này làm gì

### 1. Trợ lý hỏi đáp thống kê (AI Chatbot)
Cho phép **Quản trị viên** và **Nhà kiểm duyệt** đặt câu hỏi bằng ngôn ngữ tự nhiên về tình hình hệ thống — ví dụ "tuần này có bao nhiêu bài chờ duyệt?", "QC nào duyệt nhiều nhất?", "creator X đã đăng những bài nào?".

- Tự hiểu câu hỏi và truy xuất đúng số liệu (tổng hợp bài viết theo trạng thái, hiệu suất từng QC, danh sách creator/bài viết...).
- Trả lời theo thời gian thực, kèm bảng/danh sách dễ đọc.
- **Giá trị:** tra cứu số liệu tức thì, không cần mở dashboard hay file Excel.

### 2. Hỗ trợ kiểm duyệt bằng AI (AI-Review)
Hỗ trợ **Nhà kiểm duyệt** đánh giá bài viết dựa trên bộ tiêu chí (rubric) tùy chỉnh.

- Nhận nội dung bài viết + bộ tiêu chí kiểm duyệt, tự rà soát cả phần chữ và hình ảnh.
- Đối chiếu với feedback ở vòng duyệt trước để kiểm tra creator đã sửa đúng chưa.
- Trả về các gợi ý/nhận xét ngắn gọn để QC tham khảo trước khi quyết định.
- **Giá trị:** rút ngắn thời gian duyệt, giảm bỏ sót, đảm bảo nhất quán theo tiêu chí.

### 3. Biên dịch quy tắc nghiệm thu (Rule Analyzer)
Hỗ trợ **Quản trị viên** thiết lập quy tắc tính điểm/thưởng cho Biên bản nghiệm thu (BBNT) mà không cần lập trình.

- Admin viết quy tắc bằng tiếng Việt (ví dụ "nếu lượt xem > 10.000 thì cộng thưởng").
- AI tự chuyển quy tắc thành định dạng máy hiểu được để backend áp dụng khi tạo báo cáo.
- Cảnh báo những chỗ quy tắc còn mơ hồ để admin làm rõ.
- **Giá trị:** thay đổi cách tính thưởng linh hoạt, nhanh, không phụ thuộc kỹ thuật.

## Đối tượng phục vụ

| Chức năng | Phục vụ |
|---|---|
| Hỏi đáp thống kê | Quản trị viên, Nhà kiểm duyệt |
| Hỗ trợ kiểm duyệt | Nhà kiểm duyệt |
| Biên dịch quy tắc nghiệm thu | Quản trị viên |

## Liên kết trong hệ thống

Agents nằm giữa **frontend** (gửi câu hỏi/yêu cầu của người dùng) và **backend** (nguồn dữ liệu nghiệp vụ và nơi lưu kết quả).
