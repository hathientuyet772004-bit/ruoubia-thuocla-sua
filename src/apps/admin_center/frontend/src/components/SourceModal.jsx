import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';

const SourceModal = ({ isOpen, onClose, onSave, editingSource }) => {
    const [formData, setFormData] = useState({
        name: '',
        url: '',
        type: 'E-commerce',
        category: 'Rượu bia',
        note: ''
    });

    useEffect(() => {
        if (editingSource) {
            setFormData(editingSource);
        } else {
            setFormData({
                name: '',
                url: '',
                type: 'E-commerce',
                category: 'Rượu bia',
                note: ''
            });
        }
    }, [editingSource, isOpen]);

    if (!isOpen) return null;

    return (
        <div className="modal-overlay animate-fade-in">
            <div className="modal-content glass-morphism">
                <div className="modal-header">
                    <h2>{editingSource ? 'Edit Source' : 'Add New Source'}</h2>
                    <button className="btn-close" onClick={onClose}><X size={20} /></button>
                </div>

                <form className="modal-form" onSubmit={(e) => {
                    e.preventDefault();
                    onSave(formData);
                }}>
                    <div className="form-group">
                        <label>Website Name</label>
                        <input
                            type="text"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            placeholder="e.g. Tiki, Lazada, Winemart"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label>Homepage URL</label>
                        <input
                            type="url"
                            value={formData.url}
                            onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                            placeholder="https://..."
                            required
                        />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label>Type</label>
                            <select value={formData.type} onChange={(e) => setFormData({ ...formData, type: e.target.value })}>
                                <option value="E-commerce">E-commerce</option>
                                <option value="Brand Site">Brand Site</option>
                                <option value="Directory">Directory</option>
                                <option value="Social">Social</option>
                            </select>
                        </div>

                        <div className="form-group">
                            <label>Category</label>
                            <select value={formData.category} onChange={(e) => setFormData({ ...formData, category: e.target.value })}>
                                <option value="Rượu bia">Rượu bia</option>
                                <option value="Thuốc lá">Thuốc lá</option>
                                <option value="Sữa">Sữa</option>
                                <option value="Khác">Khác</option>
                            </select>
                        </div>
                    </div>

                    <div className="form-group">
                        <label>Notes (Optional)</label>
                        <textarea
                            value={formData.note}
                            onChange={(e) => setFormData({ ...formData, note: e.target.value })}
                            placeholder="Any special notes..."
                        />
                    </div>

                    <div className="modal-footer">
                        <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
                        <button type="submit" className="btn-save">
                            <Save size={16} /> Save Source
                        </button>
                    </div>
                </form>
            </div>

            <style>{`
        .modal-overlay {
          position: fixed;
          top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.8);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          backdrop-filter: blur(5px);
        }
        .modal-content {
          background: #161b22;
          width: 500px;
          border-radius: 12px;
          border: 1px solid #30363d;
          padding: 24px;
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
        .modal-header h2 { margin: 0; font-size: 20px; color: white; }
        .btn-close { background: transparent; border: none; color: #8b949e; cursor: pointer; }
        
        .modal-form { display: flex; flex-direction: column; gap: 16px; }
        .form-group { display: flex; flex-direction: column; gap: 8px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        
        label { font-size: 14px; color: #8b949e; }
        input, select, textarea {
          background: #0d1117;
          border: 1px solid #30363d;
          padding: 10px;
          border-radius: 6px;
          color: white;
          outline: none;
        }
        input:focus, select:focus { border-color: #58a6ff; }
        textarea { height: 80px; resize: none; }

        .modal-footer { display: flex; justify-content: flex-end; gap: 12px; margin-top: 10px; }
        .btn-cancel { background: transparent; border: 1px solid #30363d; color: #8b949e; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
        .btn-save { background: #23d38a; border: none; color: #0d1117; padding: 10px 20px; border-radius: 6px; font-weight: bold; cursor: pointer; display: flex; align-items: center; gap: 8px; }
      `}</style>
        </div>
    );
};

export default SourceModal;
