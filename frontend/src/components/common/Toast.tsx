import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { CheckCircle, AlertTriangle, XCircle, Info, X } from 'lucide-react';

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
}

interface ToastContextValue {
  showToast: (type: ToastType, title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const TOAST_CONFIG: Record<
  ToastType,
  { Icon: React.FC<{ className?: string }>; iconClass: string; borderClass: string }
> = {
  success: {
    Icon: CheckCircle,
    iconClass: 'text-recover-text',
    borderClass: 'border-l-[3px] border-l-[#059669]',
  },
  error: {
    Icon: XCircle,
    iconClass: 'text-halt-text',
    borderClass: 'border-l-[3px] border-l-[#E11D48]',
  },
  warning: {
    Icon: AlertTriangle,
    iconClass: 'text-risk-text',
    borderClass: 'border-l-[3px] border-l-[#D97706]',
  },
  info: {
    Icon: Info,
    iconClass: 'text-ai-text',
    borderClass: 'border-l-[3px] border-l-[#7C3AED]',
  },
};

const ToastItem: React.FC<{ toast: Toast; onDismiss: (id: string) => void }> = ({
  toast,
  onDismiss,
}) => {
  const { Icon, iconClass, borderClass } = TOAST_CONFIG[toast.type];

  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 4500);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div
      className={`
        flex items-start gap-3 w-80 p-3.5
        bg-surface-overlay border border-white/[0.10] rounded-lg
        shadow-[0_8px_32px_rgba(0,0,0,0.5)]
        animate-slide-in-right
        ${borderClass}
      `}
      role="alert"
    >
      <Icon className={`w-4 h-4 shrink-0 mt-0.5 ${iconClass}`} />
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-semibold text-[#F0F2F5] leading-tight">{toast.title}</div>
        {toast.message && (
          <div className="text-[11px] text-[#9CA3AF] mt-0.5 leading-relaxed">{toast.message}</div>
        )}
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="shrink-0 text-[#4B5563] hover:text-[#9CA3AF] transition-colors"
        aria-label="Dismiss notification"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((type: ToastType, title: string, message?: string) => {
    const id = `toast-${Date.now()}-${Math.random()}`;
    setToasts((prev) => {
      const next = [...prev, { id, type, title, message }];
      return next.slice(-3); // max 3 visible
    });
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {/* Toast container: bottom-right */}
      <div
        className="fixed bottom-6 right-6 flex flex-col gap-2 z-[9999]"
        aria-live="polite"
        aria-label="Notifications"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextValue => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
};
