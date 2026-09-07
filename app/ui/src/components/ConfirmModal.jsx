import React, { useEffect } from 'react';
import './ConfirmModal.css';

/**
 * Reusable confirmation/alert modal — replacement for window.confirm/alert.
 * Set hideCancel to render a single-button "alert" style dialog.
 */
export function ConfirmModal({
  open,
  title = 'Подтверждение',
  message,
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  danger = false,
  hideCancel = false,
  onConfirm,
  onCancel,
}) {
  const dismiss = onCancel || onConfirm;

  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') dismiss?.();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, dismiss]);

  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={dismiss}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h4>{title}</h4>
          <button className="modal-close" onClick={dismiss}>✕</button>
        </div>

        <div className="modal-body confirm-modal-body">
          <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{message}</p>
        </div>

        <div className="modal-actions confirm-modal-actions">
          {!hideCancel && (
            <button type="button" className="btn-secondary" onClick={onCancel}>
              {cancelLabel}
            </button>
          )}
          <button type="button" className={danger ? 'btn-primary btn-danger' : 'btn-primary'} onClick={onConfirm} autoFocus>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmModal;
