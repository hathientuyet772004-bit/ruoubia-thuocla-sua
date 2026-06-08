import React from 'react';
import { ExternalLink, MapPin, Tag } from 'lucide-react';

const ProductCard = ({ product }) => {
    const formatPrice = (p) => {
        const price = Number(p);
        if (!Number.isFinite(price) || price <= 0) return "Chưa có giá";
        return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(price);
    };
    const price = product.price_numeric ?? product.price;

    return (
        <div className="product-card glass-morphism animate-fade-in">
            <div className="product-image-container">
                {product.image ? (
                    <img src={product.image} alt={product.name} className="product-image" />
                ) : (
                    <div className="product-image-placeholder">Chưa có ảnh</div>
                )}
                <span className="source-badge">{product.source}</span>
            </div>

            <div className="product-info">
                <div className="product-category-row">
                    <span className="category-tag"><Tag size={10} /> {product.category}</span>
                    {product.brand && <span className="brand-tag">{product.brand}</span>}
                </div>

                <h3 className="product-title" title={product.name}>{product.name}</h3>
                <div className="store-row"><MapPin size={12} />{product.store_name || product.store_url || 'Chưa có thông tin cửa hàng'}</div>
                {product.store_address ? <div className="store-meta">{product.store_address}</div> : null}
                {product.store_phone ? <div className="store-meta">{product.store_phone}</div> : null}

                <div className="price-row">
                    <span className={`current-price ${Number(price) > 0 ? '' : 'missing'}`}>{formatPrice(price)}</span>
                    {product.original_price && (
                        <span className="original-price">{formatPrice(product.original_price)}</span>
                    )}
                </div>

                <div className="product-footer">
                    <span className="update-time">Cập nhật: {new Date(product.updated_at).toLocaleDateString()}</span>
                    <a href={product.url} target="_blank" rel="noreferrer" className="view-btn">
                        Xem <ExternalLink size={12} />
                    </a>
                </div>
            </div>

            <style>{`
        .product-card {
          background: rgba(22, 27, 34, 0.5);
          border: 1px solid #30363d;
          border-radius: 12px;
          overflow: hidden;
          transition: transform 0.2s, border-color 0.2s;
        }
        .product-card:hover {
          transform: translateY(-4px);
          border-color: #58a6ff;
        }
        .product-image-container {
          height: 160px;
          background: #0d1117;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .product-image {
          width: 100%;
          height: 100%;
          object-fit: contain;
          padding: 10px;
        }
        .product-image-placeholder {
          color: #484f58;
          font-size: 12px;
          text-transform: uppercase;
        }
        .source-badge {
          position: absolute;
          top: 8px; right: 8px;
          background: rgba(88, 166, 255, 0.2);
          color: #58a6ff;
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 10px;
          font-weight: bold;
          backdrop-filter: blur(4px);
        }
        .product-info { padding: 16px; }
        .product-category-row { display: flex; gap: 8px; margin-bottom: 8px; }
        .category-tag {
          font-size: 10px;
          background: rgba(255,255,255,0.05);
          color: #8b949e;
          padding: 2px 6px;
          border-radius: 4px;
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .brand-tag {
          font-size: 10px;
          color: var(--accent-amber);
          font-weight: bold;
        }
        .product-title {
          font-size: 14px;
          margin: 0 0 12px 0;
          color: white;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
          height: 38px;
          line-height: 1.4;
        }
        .store-row {
          display: flex;
          align-items: center;
          gap: 5px;
          color: #8b949e;
          font-size: 11px;
          margin-bottom: 10px;
          min-height: 16px;
        }
        .store-meta {
          overflow: hidden;
          color: #6e7681;
          font-size: 10px;
          margin: -6px 0 8px;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .price-row { display: flex; align-items: baseline; gap: 8px; margin-bottom: 12px; }
        .current-price { color: #23d38a; font-size: 18px; font-weight: bold; }
        .current-price.missing { color: #8b949e; font-size: 14px; }
        .original-price { color: #6e7681; font-size: 12px; text-decoration: line-through; }
        .product-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-top: 1px solid #30363d;
          padding-top: 12px;
          margin-top: 4px;
        }
        .update-time { font-size: 10px; color: #484f58; }
        .view-btn {
          font-size: 11px;
          color: #58a6ff;
          text-decoration: none;
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .view-btn:hover { text-decoration: underline; }
      `}</style>
        </div>
    );
};

export default ProductCard;
