# Phiếu rà soát audit

Nhãn do trợ lý đề xuất, tác giả đã rà soát và xác nhận qua hội thoại; xem artifacts/author_review.json.
Các mẫu đầy đủ nằm trong JSON đi kèm. Không sửa kết quả truy xuất khi điều chỉnh nhãn; xác nhận hiện tại chỉ áp dụng cho hash đã lưu.

## Coherence: 10 vị trí nguồn đã chọn trước

| Cấu hình | Trang vật lý | Điểm đề xuất /2 | Lý do |
|---|---:|---:|---|
| A | 5 | 1 | Định nghĩa và mục đích ban đầu đọc được, nhưng cửa sổ kết thúc giữa từ 'assist' ở đoạn tiếp theo. |
| A | 6 | 1 | Có ngữ cảnh GAI PWG và bốn chủ đề; câu nói về các bản cập nhật tương lai bị cắt cuối chunk. |
| A | 7 | 1 | Bắt đầu bằng phần câu từ trang trước và kết thúc giữa danh sách đặc điểm; ý Time scale vẫn đọc được. |
| A | 8 | 1 | Các định nghĩa CBRN và Confabulation đủ, nhưng định nghĩa Data Privacy ở cuối bị cắt. |
| A | 9 | 1 | Đầu chunk là phần tiếp nối Information Security, cuối lại cắt mục Value Chain; chỉ một số định nghĩa ở giữa đầy đủ. |
| A | 10 | 1 | Định nghĩa Confabulation đầy đủ, nhưng đoạn giải thích cơ chế mô hình bị cắt giữa từ ở cuối. |
| A | 11 | 1 | Đầu là mảnh câu từ trang trước; đoạn jailbreaking có ý nghĩa nhưng câu cuối chưa kết thúc. |
| A | 12 | 1 | Trộn phần Trustworthy Characteristics của mục trước với Environmental Impacts và cắt giữa câu so sánh năng lượng. |
| A | 13 | 1 | Đầu thiếu phần câu trang trước; đoạn model collapse đọc được nhưng nhãn Trustworthy Characteristics bị cắt cuối. |
| A | 14 | 1 | Phân biệt misinformation/disinformation rõ, nhưng đoạn deepfakes tiếp theo bị cắt giữa từ. |
| B | 5 | 2 | Có heading Introduction và đoạn mở đầu hoàn chỉnh, nêu rõ bối cảnh cùng mục đích AI RMF. |
| B | 6 | 2 | Hai đoạn về GAI PWG và bốn chủ đề kết thúc trọn câu, có chủ thể và ngữ cảnh. |
| B | 7 | 1 | Mục Time scale hoàn chỉnh nhưng đầu chunk vẫn là phần câu từ trang trước. |
| B | 8 | 2 | Giữ trọn một định nghĩa CBRN với tên mục và các đối tượng được định nghĩa. |
| B | 9 | 0 | Chỉ còn phần cuối định nghĩa Information Security từ trang trước; không có tên rủi ro và thiếu chủ thể để hiểu độc lập. |
| B | 10 | 2 | Heading và định nghĩa Confabulation cùng các cách gọi tương đương đầy đủ. |
| B | 11 | 1 | Có các câu về text-to-image và media khác, nhưng mở đầu bằng mảnh câu 'unethical behavior' thiếu ngữ cảnh trước. |
| B | 12 | 2 | Heading Environmental Impacts và hai đoạn liên quan kết thúc trọn ý; còn lỗi tách chữ từ PDF nhưng vẫn hiểu nội dung. |
| B | 13 | 1 | Đoạn model collapse đầy đủ nhưng mở đầu là phần tiếp nối câu chưa có ở chunk này. |
| B | 14 | 2 | Giữ đầy đủ hai đoạn phân biệt misinformation và disinformation, đủ điều kiện về chủ ý. |
| C | 5 | 2 | Có heading Introduction và đoạn mở đầu hoàn chỉnh, nêu rõ bối cảnh cùng mục đích AI RMF. |
| C | 6 | 2 | Hai đoạn về GAI PWG và bốn chủ đề kết thúc trọn câu, có chủ thể và ngữ cảnh. |
| C | 7 | 1 | Mục Time scale hoàn chỉnh nhưng đầu chunk vẫn là phần câu từ trang trước. |
| C | 8 | 2 | Giữ trọn một định nghĩa CBRN với tên mục và các đối tượng được định nghĩa. |
| C | 9 | 0 | Chỉ còn phần cuối định nghĩa Information Security từ trang trước; không có tên rủi ro và thiếu chủ thể để hiểu độc lập. |
| C | 10 | 2 | Heading và định nghĩa Confabulation cùng các cách gọi tương đương đầy đủ. |
| C | 11 | 1 | Có các câu về text-to-image và media khác, nhưng mở đầu bằng mảnh câu 'unethical behavior' thiếu ngữ cảnh trước. |
| C | 12 | 2 | Heading Environmental Impacts và hai đoạn liên quan kết thúc trọn ý; còn lỗi tách chữ từ PDF nhưng vẫn hiểu nội dung. |
| C | 13 | 1 | Đoạn model collapse đầy đủ nhưng mở đầu là phần tiếp nối câu chưa có ở chunk này. |
| C | 14 | 2 | Giữ đầy đủ hai đoạn phân biệt misinformation và disinformation, đủ điều kiện về chủ ý. |

## Grounding: 5 câu test cho mỗi cấu hình

| Cấu hình | Câu | Điểm đề xuất /2 | Lý do |
|---|---|---:|---|
| A | T01 | 0 | Top-3 ở trang 16, 12, 40, không có bằng chứng về sự khác biệt phòng thí nghiệm và thực tế; còn ngoài phạm vi Appendix A được yêu cầu. |
| A | T02 | 2 | Rank 1 trang 54 có đủ focus groups, small user studies và anonymous surveys, truy được nguồn. |
| A | T03 | 2 | Rank 1 trang 55 nêu đủ người tạo, thời gian, địa điểm, thay đổi và nguồn; hai kết quả còn lại ngoài Appendix A là hạn chế filter riêng. |
| A | T04 | 0 | Top-3 trang 8, 26, 49 nói về rủi ro hoặc xử lý incidents, không xác nhận tình trạng kênh chính thức và database theo bản tài liệu. |
| A | T05 | 2 | Rank 2 trang 57 có đủ logging, recording, analyzing, sharing, change records, version history và metadata. |
| B | T01 | 0 | Top-3 là footnote trang 14 và đoạn trang 7, 12; không trả đoạn measurement gaps ở Appendix A. |
| B | T02 | 2 | Rank 1 trang 54 chứa đủ ba hình thức lấy phản hồi được hỏi. |
| B | T03 | 2 | Rank 1 trang 55 chứa đầy đủ các trường provenance metadata; top-3 còn gồm phần chính nên filter compliance không đạt. |
| B | T04 | 2 | Rank 1 trang 56 nêu cả việc chưa có kênh chính thức và sự tồn tại các database công khai, đúng thời điểm tài liệu. |
| B | T05 | 2 | Rank 1 trang 57 chứa toàn bộ các thực hành được hỏi và có nguồn/trang. |
| C | T01 | 2 | Filter Appendix A đưa đoạn trang 53 vào rank 3; đoạn này nêu trực tiếp laboratory và real-world settings. |
| C | T02 | 2 | Câu không có filter nên C giữ kết quả B; rank 1 trang 54 đủ ba hình thức phản hồi. |
| C | T03 | 2 | Rank 1 trang 55 đủ các trường metadata; cả top-3 đều thuộc Appendix A. |
| C | T04 | 2 | Câu không có filter, kết quả giống B; rank 1 trang 56 đủ cả hai vế của đáp án. |
| C | T05 | 2 | Câu không có filter, kết quả giống B; rank 1 trang 57 đủ các thực hành và truy được nguồn. |

## Metadata và filter

| Cấu hình | Metadata đủ/đúng (kiểm tra máy) | Top-3 tuân thủ yêu cầu filter |
|---|---:|---:|
| A | 15/15 | 0/2 |
| B | 15/15 | 0/2 |
| C | 15/15 | 2/2 |

Đối chiếu đầy đủ: coherence_proposals.json, grounding_proposals.json, metadata_checks.json, filter_checks.json.
Điểm 0/1/2 không được suy ra tự động từ Hit@3. Các mẫu C coherence có cùng text với B, không phải lần chấm độc lập.
Trạng thái xác nhận: author_reviewed
