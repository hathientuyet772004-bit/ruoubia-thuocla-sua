import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Check, Info } from 'lucide-react';

const Toast = ({ message }) => {
    return (
        <AnimatePresence>
            {message && (
                <motion.div
                    initial={{ opacity: 0, y: 60, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 60, scale: 0.95 }}
                    className={`toast toast-${message.type}`}
                >
                    {message.type === 'error' && <AlertTriangle size={18} />}
                    {message.type === 'success' && <Check size={18} />}
                    {message.type === 'warning' && <AlertTriangle size={18} />}
                    {message.type === 'info' && <Info size={18} />}
                    <span>{message.text}</span>
                </motion.div>
            )}
        </AnimatePresence>
    );
};

export default Toast;
