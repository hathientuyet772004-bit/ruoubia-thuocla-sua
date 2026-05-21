# Thuộc tính Tự Động Hóa (Automation Behaviors Strategies)

Khác với các hệ thống cào dữ liệu cũ đặt hardcode-rule (CSS/XPath) vào thư mục này,
Kiến trúc Smart Crawler sử dụng thư mục này để chứa **CÁC CHIẾN LƯỢC HÀNH VI (BEHAVIORAL STRATEGIES)**
áp dụng trên các trang thương mại điện tử với độ phức tạp cao.

## Danh sách Chiến lược (Vũ khí)

1. `/behavior_ai_fallback`
   Chứa AI Selector Generator (Gemini): Cơ chế tự sinh rule khi website bị gãy (UI Drift).
2. `/behavior_network_intercept`
   Chứa API Interceptor (Playwright): Cơ chế đánh chặn gói tin JSON, vượt qua việc cào HTML (Tốc độ x10).
3. `/behavior_headless_scroll`
   Cơ chế Navigation: Cuộn trang vô tận (Infinite Scroller) kéo Lazy-load elements.
4. `/behavior_anti_bot`
   Cơ chế Vượt tường: Băm Stealth plugins, xoay Proxy (Rotator), vượt Cloudflare, Datadog.

Kiến trúc này đảm bảo tính "Plug-and-play". Vị Tướng quân (Core Collector) chỉ việc
rút vũ khí từ đây ra chiến đấu tùy thuộc vào "độ cứng" của website, không cần IF/ELSE.
