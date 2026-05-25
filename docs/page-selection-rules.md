# Quy tắc chọn trang để crawl

Tài liệu này mô tả cách quyết định nên lấy trang nào từ một website để phục vụ pipeline thu thập dữ liệu.

## Mục tiêu

- Lấy đúng trang có dữ liệu hữu ích.
- Tránh crawl lan sang các trang ít giá trị như chính sách, bài viết rời rạc, trang lỗi, hoặc trang lặp.
- Giữ bộ dữ liệu đủ cho 3 nhóm chính:
  - `listing` hoặc trang danh mục
  - `product_detail` hoặc trang chi tiết sản phẩm
  - `stores` / `branches` / `locations` hoặc trang chi nhánh/cửa hàng

## Bộ tiêu chuẩn tối thiểu để chấp nhận một website

Nếu đầu vào chỉ là một URL/domain và chưa biết có nên thu thập hay không, dùng các tiêu chuẩn tối thiểu sau để quyết định:

### Chấp nhận khi website có ít nhất 2 trong 4 tín hiệu

1. Có sản phẩm hoặc dịch vụ thể hiện rõ trên trang.
2. Có danh sách nhiều item cùng kiểu, không phải một trang đơn lẻ.
3. Có thông tin liên hệ hoặc hệ thống chi nhánh/cửa hàng.
4. Có cấu trúc HTML đủ ổn định để trích xuất bằng selector.

### Loại bỏ khi website chỉ có các đặc điểm sau

- Chỉ là landing page quảng cáo một lần, không có danh mục hoặc dữ liệu lặp.
- Chỉ có nội dung giới thiệu chung, không có sản phẩm hoặc địa điểm rõ ràng.
- Chỉ là trang tin tức, blog, hoặc bài viết độc lập, không có cấu trúc dữ liệu cần crawl.
- Chỉ có form, login, captcha, hoặc nội dung động khó lấy dữ liệu.
- Chỉ có sitemap, redirect, hoặc trang trung gian.

### Mức ưu tiên của website

- Ưu tiên cao: site bán hàng, site có listing + detail + store.
- Ưu tiên trung bình: site chỉ có listing hoặc chỉ có store/location.
- Ưu tiên thấp: site chỉ có một trang giới thiệu nhưng có thể suy ra dữ liệu từ link con.
- Loại bỏ: site không có tín hiệu dữ liệu lặp, không có sản phẩm, không có cửa hàng, không có chi nhánh.

## Nên lấy trang nào

### 1. Trang chủ

Nên lấy nếu trang chủ có ít nhất một trong các tín hiệu sau:

- Danh sách sản phẩm nổi bật, bán chạy, khuyến mãi, mới về.
- Link dẫn rõ đến danh mục, sản phẩm, hoặc chi nhánh.
- Khối giới thiệu hệ thống cửa hàng, hotline, địa chỉ.

Trang chủ thường dùng để:

- Khởi tạo discovery.
- Tìm link sang danh mục, sản phẩm, chi nhánh.
- Tìm dữ liệu tổng quan của site.

### 2. Trang danh mục / listing

Nên lấy nếu trang có danh sách nhiều item cùng kiểu.

Dấu hiệu thường gặp:

- Có grid/list sản phẩm.
- Có nhiều thẻ lặp lại với cùng cấu trúc.
- Có phân trang, load more, hoặc filter/sort.
- Có URL chứa từ khóa như `san-pham`, `product`, `category`, `danh-muc`, `collection`.

Đây là loại trang ưu tiên cao vì thường dẫn tới nhiều sản phẩm.

### 3. Trang chi tiết sản phẩm

Nên lấy nếu trang có dữ liệu chi tiết của một item duy nhất.

Dấu hiệu thường gặp:

- Có `h1` tên sản phẩm.
- Có giá bán, giá cũ, tình trạng hàng.
- Có mô tả, thuộc tính, dung tích, nồng độ, loại rượu.
- Có link mua hàng, hotline, fanpage, hoặc thông tin liên hệ.

Đây là trang bắt buộc nếu site có bán hàng theo sản phẩm.

### 4. Trang cửa hàng / chi nhánh / chi nhánh địa phương

Nên lấy nếu trang chứa danh sách địa điểm bán hàng.

Từ khóa và tín hiệu thường gặp:

- `chi nhánh`
- `cửa hàng`
- `store`
- `branch`
- `location`
- `showroom`
- `he thong cua hang`
- `he thong ban hang`

Trang này nên được coi là dữ liệu `stores`, kể cả khi source dùng tên `branches` hoặc `locations`.

### 5. Trang tin tức / hướng dẫn / blog

Chỉ nên lấy nếu nội dung có giá trị cho sản phẩm hoặc cửa hàng.

Ví dụ:

- Bài giới thiệu chi nhánh mới.
- Bài thông báo địa chỉ, hotline, giờ mở cửa.
- Bài có nhiều link trỏ về sản phẩm quan trọng.

Nếu chỉ là nội dung marketing chung, nên bỏ qua.

## Nên bỏ qua trang nào

Không nên crawl hoặc không nên đưa vào tập xử lý chính nếu trang có các đặc điểm sau:

- Trang chính sách, điều khoản, bảo mật, vận chuyển, đổi trả.
- Trang lỗi 404, 500, hoặc redirect vòng.
- Trang đăng nhập, đăng ký, quên mật khẩu.
- Trang kết quả tìm kiếm rỗng hoặc ít dữ liệu.
- Trang tag, archive, RSS, sitemap XML.
- Trang nội bộ không có dữ liệu sản phẩm/cửa hàng.

## Ưu tiên chọn trang

Nếu một site có nhiều loại trang, ưu tiên theo thứ tự:

1. `product_detail`
2. `listing`
3. `stores` / `branches`
4. Trang chủ
5. Tin tức hoặc bài viết liên quan

Nếu chỉ được crawl số lượng hạn chế, nên ưu tiên:

- Trang chi tiết sản phẩm mẫu
- Trang danh mục lớn nhất
- Trang chi nhánh/cửa hàng chính

## Cách nhận biết nhanh bằng HTML

### Có khả năng là listing khi:

- Có nhiều phần tử lặp.
- Có link sản phẩm lặp lại trong cùng một block.
- Có giá, ảnh, tên sản phẩm trên nhiều card giống nhau.

### Có khả năng là product detail khi:

- Chỉ có một tiêu đề chính.
- Có nhiều thông tin chi tiết cho cùng một sản phẩm.
- Có giá, mô tả, thuộc tính, tồn kho.

### Có khả năng là stores/branches khi:

- Có nhiều địa chỉ.
- Có nhiều số điện thoại.
- Có các thẻ lặp lại theo cơ sở.
- Có bản đồ, hotline, fanpage, hoặc giờ mở cửa theo chi nhánh.

## Quy tắc dành cho Admin Center

Khi phân tích một site trong Admin Center:

- Nếu có `listing` và `stores`, giữ cả hai.
- Nếu source dùng `branches` thay vì `stores`, vẫn coi đó là dữ liệu cửa hàng.
- Nếu một page type không có selector đáng tin, để trống thay vì tự bịa selector.
- Chỉ chấp nhận rule khi preview/validation có tín hiệu thật trên HTML.

## Quy tắc dành cho batch crawl

Khi chạy batch nhiều domain:

- Mỗi domain chỉ cần một trang đại diện để chẩn đoán ban đầu.
- Nếu trang đại diện không đủ tín hiệu, chuyển sang:
  - trang danh mục chính
  - trang chi tiết sản phẩm mẫu
  - trang chi nhánh hoặc liên hệ
- Không nên crawl tất cả link ngay từ đầu.
- Chỉ mở rộng crawl khi discovery cho thấy site có cấu trúc rõ.

## Gợi ý thực tế

Một site bán rượu như `ruoutot.net` thường nên lấy:

- Trang chủ
- Trang danh mục hoặc danh sách sản phẩm
- Một vài trang chi tiết sản phẩm tiêu biểu
- Trang chi nhánh / hệ thống bán hàng

Mục tiêu không phải lấy mọi trang, mà là lấy đủ trang để xác định:

- Sản phẩm có những trường nào
- Cửa hàng/chi nhánh có những trường nào
- Trang nào là nguồn chuẩn để khớp selector
