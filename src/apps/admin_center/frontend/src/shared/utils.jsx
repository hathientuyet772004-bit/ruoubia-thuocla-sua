export function hostFromUrl(url = '') {
  try { return new URL(url).hostname.replace(/^www\./, ''); }
  catch { return url || 'không rõ'; }
}

export function jobStatusLabel(status) {
  return ({ Completed: 'Hoàn tất', Failed: 'Thất bại', Pending: 'Đang chờ' })[status] || status || '-';
}

export function priceStatus(product) {
  const price = Number(product.price_numeric ?? product.price);
  if (Number.isFinite(price) && price > 0) return 'FOUND';
  return product.price_status || 'MISSING';
}

export function priceStatusLabel(status) {
  return ({ FOUND: 'Giá hợp lệ', MISSING: 'Thiếu giá', PARSE_ERROR: 'Lỗi parse', BLOCKED: 'Bị chặn', JS_RENDER_REQUIRED: 'Cần JS' })[status] || status || 'Thiếu giá';
}

export function priceStatusTone(status) {
  return status === 'FOUND' ? 'good' : (status === 'PARSE_ERROR' || status === 'BLOCKED') ? 'bad' : 'warning';
}

export function formatProductPrice(product) {
  const price = Number(product.price_numeric ?? product.price);
  if (!Number.isFinite(price) || price <= 0) return 'N/A';
  return `${price.toLocaleString('vi-VN')} VND`;
}

export function dedupStatusLabel(status) {
  return ({ pending: 'Đang chờ', merged: 'Đã gộp', rejected: 'Đã loại', approved: 'Đã duyệt', needs_review: 'Cần rà soát', all: 'Tất cả' })[status] || status;
}

export function sourceTypeLabel(type) {
  return ({ 'E-commerce': 'Thương mại điện tử', 'Brand Site': 'Trang thương hiệu', Directory: 'Danh bạ', Social: 'Mạng xã hội' })[type] || type || '-';
}

export function extractionTargetLabel(target) {
  return ({ product_detail: 'Chi tiết sản phẩm', product_listing: 'Danh sách sản phẩm', store_detail: 'Chi tiết cửa hàng', store_listing: 'Danh sách cửa hàng' })[target] || target;
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename;
  document.body.appendChild(link); link.click(); link.remove();
  URL.revokeObjectURL(url);
}

export function filenameFromDisposition(header, fallback) {
  const match = /filename="?([^"]+)"?/i.exec(header || '');
  return match?.[1] || fallback;
}

export function storeLabel(row = {}) { return row.store_name || row.store_url || ''; }

export function storeAddressLabel(row = {}) {
  if (row.store_address) return row.store_address;
  if (row.address_status === 'NOT_APPLICABLE' || row.store_channel === 'online') return 'Online';
  return 'Chưa có địa chỉ';
}

export function splitList(value = '') {
  return value.split(/[\n,]+/).map((item) => item.trim()).filter(Boolean);
}
