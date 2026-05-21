import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, X, ArrowRight } from 'lucide-react';

const DuplicateOverlay = ({
    showDuplicateOverlay,
    duplicateInfo,
    handleCancelDuplicate,
    handleForceLoad
}) => {
    return (
        <AnimatePresence>
            {showDuplicateOverlay && duplicateInfo && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="duplicate-overlay"
                >
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9, y: 20 }}
                        className="duplicate-card"
                    >
                        <div className="icon-wrapper">
                            <ShieldAlert size={30} />
                        </div>
                        <h3>URL đã được truy cập!</h3>
                        <p>URL này đã được xử lý trước đó trong tháng hiện tại.</p>

                        <div className="info-row">
                            <span className="label">URL:</span>
                            <span className="value truncate">{duplicateInfo.url}</span>
                        </div>
                        <div className="info-row">
                            <span className="label">Người thực hiện:</span>
                            <span className="value">{duplicateInfo.existing_visit?.user_id || 'Unknown'}</span>
                        </div>
                        <div className="info-row">
                            <span className="label">Thời gian:</span>
                            <span className="value">{duplicateInfo.existing_visit?.visited_at || 'Unknown'}</span>
                        </div>

                        <div className="actions">
                            <button className="btn-secondary" onClick={handleCancelDuplicate} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <X size={16} />
                                Hủy
                            </button>
                            <button className="btn-primary" onClick={handleForceLoad} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <ArrowRight size={16} />
                                Vẫn truy cập
                            </button>
                        </div>
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default DuplicateOverlay;
