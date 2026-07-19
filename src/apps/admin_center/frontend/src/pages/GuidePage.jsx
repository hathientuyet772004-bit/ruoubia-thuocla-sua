import React from 'react';
import { BookOpen, CheckCircle2, Database, Globe, PlayCircle, Settings, Tags } from 'lucide-react';
import { Page, Panel, RouteLink } from '../shared/ui';

const steps = [
  {
    icon: Globe,
    title: '1. Khai báo nguồn dữ liệu',
    body: 'Vào Nguồn dữ liệu để thêm website cần thu thập. Với nguồn online để kênh bán là Online; với cửa hàng tiện lợi hoặc chuỗi có chi nhánh chọn Online + chi nhánh và nhập URL trang store locator.',
    links: [['/sources', 'Mở Nguồn dữ liệu']],
  },
  {
    icon: PlayCircle,
    title: '2. Chạy thu thập thật',
    body: 'Bấm Chạy ở từng nguồn. Hệ thống sẽ crawl trang nguồn, lưu trang thô, gọi AI học rule khi cần và ghi sản phẩm/giá hoặc chi nhánh vào PostgreSQL.',
    links: [['/runs', 'Xem Lượt chạy']],
  },
  {
    icon: Settings,
    title: '3. Kiểm tra rule trích xuất',
    body: 'Nếu lượt chạy có trang thô nhưng chưa ra sản phẩm, mở Quy tắc trích xuất để kiểm thử selector theo domain. Duyệt Rule AI chỉ dùng khi có candidate đạt chất lượng.',
    links: [['/extraction/rules', 'Mở Quy tắc trích xuất']],
  },
  {
    icon: Tags,
    title: '4. Ghép sản phẩm cùng loại',
    body: 'Vào Sản phẩm & giá bán và bấm Ghép sản phẩm để sinh canonical_product_id. Sau bước này cùng một sản phẩm ở nhiều nguồn mới so giá được với nhau.',
    links: [['/products', 'Mở Sản phẩm & giá bán']],
  },
  {
    icon: Database,
    title: '5. Theo dõi dữ liệu đầu ra',
    body: 'Dữ liệu sản phẩm nằm trong sc_products và sc_offers. Địa chỉ chi nhánh thật nằm trong sc_store_locations. Trang thô dùng để đối chiếu bằng chứng crawl.',
    links: [] /* [['/tasks/latest/raw', 'Xem trang thô']] */,
  },
];

const checks = [
  'Nguồn online không cần địa chỉ chi nhánh; hệ thống hiển thị Online.',
  'Nguồn physical/hybrid cần store_locator_url hoặc store_address thật.',
  'Không nhập địa chỉ suy đoán. Nếu website không lộ dữ liệu trong HTML, cần bổ sung parser/API hoặc browser-render extractor.',
  'Gemini có thể bị quota 429; các fallback parser vẫn có thể ghi dữ liệu nếu HTML có cấu trúc rõ.',
  'Sau khi crawl xong nên kiểm tra Lượt chạy, số sản phẩm, số store_fields và bảng sc_store_locations.',
];

export default function GuidePage({ navigate }) {
  return (
    <Page
      title="Hướng dẫn sử dụng"
      subtitle="Quy trình vận hành nền tảng thu thập giá thị trường và địa chỉ chi nhánh tại Việt Nam."
      actions={<RouteLink to="/sources" navigate={navigate}>Bắt đầu từ nguồn dữ liệu</RouteLink>}
    >
      <section className="guide-grid">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <Panel key={step.title} title={step.title} className="guide-panel" actions={<Icon />}>
              <p>{step.body}</p>
              <div className="guide-links">
                {step.links.map(([to, label]) => <RouteLink key={to} to={to} navigate={navigate}>{label}</RouteLink>)}
              </div>
            </Panel>
          );
        })}
      </section>

      <Panel title="Checklist trước khi coi là chạy production" className="guide-checklist" actions={<CheckCircle2 />}>
        <ul>
          {checks.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </Panel>

      <Panel title="Luồng xử lý chuẩn" className="guide-flow" actions={<BookOpen />}>
        <ol>
          <li>Thêm hoặc sửa nguồn, kiểm tra đúng domain và category.</li>
          <li>Nếu nguồn có cửa hàng vật lý, nhập store locator và chọn phạm vi Theo chi nhánh.</li>
          <li>Bấm Chạy, sau đó mở Lượt chạy để xem raw_artifacts, products_written và store_fields_attached.</li>
          <li>Nếu chưa có sản phẩm, mở Quy tắc trích xuất để xem trang thô và kiểm thử selector.</li>
          <li>Sau khi có sản phẩm, bấm Ghép sản phẩm ở trang Sản phẩm & giá bán.</li>
          <li>Đối chiếu giá bằng link Mở nguồn và đối chiếu địa chỉ trong sc_store_locations khi cần.</li>
        </ol>
      </Panel>
    </Page>
  );
}
