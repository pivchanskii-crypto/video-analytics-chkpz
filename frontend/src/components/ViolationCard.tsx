import { useState } from 'react';
import type { KeyboardEvent } from 'react';
import { motion } from 'motion/react';
import type {
  StatusUpdateHandler,
  Violation,
  ViolationDecision,
} from '../lib/types';
import { ApiError, sendFeedback } from '../lib/api';
import { CameraIcon } from './icons';
import { formatTime, TYPE_LABELS } from '../lib/labels';

const STATUS_LABELS: Record<string, string> = {
  open: 'Новое',
  confirmed: 'Подтверждено',
  false_alarm: 'Ложная тревога',
};

const STATUS_STYLES: Record<string, string> = {
  open: 'bg-amber-100 text-amber-800',
  confirmed: 'bg-emerald-100 text-emerald-700',
  false_alarm: 'bg-rose-100 text-rose-700',
};

function FramePreview({
  frameUrl,
  type,
}: {
  frameUrl: string | null | undefined;
  type: string;
}) {
  const [failed, setFailed] = useState(false);

  return (
    <div className="relative aspect-video w-full overflow-hidden bg-slate-900">
      {frameUrl && !failed ? (
        <img
          src={frameUrl}
          alt={`Кадр нарушения: ${TYPE_LABELS[type] ?? type}`}
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2 bg-slate-800 text-slate-400">
          <CameraIcon className="h-10 w-10" />
          <span className="text-xs font-medium uppercase tracking-wider">
            Фото недоступно
          </span>
          <span
            className="pointer-events-none absolute inset-x-6 bottom-8 top-8 rounded border-2 border-dashed border-amber-400/70"
            aria-hidden="true"
          />
        </div>
      )}
    </div>
  );
}

export default function ViolationCard({
  violation,
  onClick,
  onStatusUpdate,
}: {
  violation: Violation;
  onClick?: () => void;
  onStatusUpdate: StatusUpdateHandler;
}) {
  const [sending, setSending] = useState<ViolationDecision | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isOpen = violation.status === 'open';

  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (onClick && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      onClick();
    }
  }

  async function handleDecision(decision: ViolationDecision) {
    if (!isOpen || sending !== null) {
      return;
    }
    setSending(decision);
    setError(null);
    try {
      const updated = await sendFeedback(violation.id, decision);
      onStatusUpdate(violation.id, updated.status);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Не удалось отправить решение',
      );
    } finally {
      setSending(null);
    }
  }

  return (
    <motion.article
      onClick={onClick}
      onKeyDown={onClick ? handleKeyDown : undefined}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9 }}
      whileHover={{
        y: -4,
        boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)',
      }}
      transition={{ type: 'spring', stiffness: 400, damping: 17 }}
      className={`flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm transition ${
        onClick ? 'cursor-pointer hover:border-slate-300 hover:shadow-md' : ''
      }`}
    >
      <FramePreview frameUrl={violation.frame_url} type={violation.type} />

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              {violation.camera_name ?? `Камера #${violation.camera_id}`}
            </h3>
            {violation.zone_name && (
              <p className="mt-0.5 text-xs text-slate-500">
                Зона: {violation.zone_name}
              </p>
            )}
          </div>
          <span
            className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              STATUS_STYLES[violation.status] ?? 'bg-slate-100 text-slate-600'
            }`}
          >
            {STATUS_LABELS[violation.status] ?? violation.status}
          </span>
        </div>

        <div className="space-y-1.5 text-sm text-slate-600">
          <div className="flex items-center justify-between gap-3">
            <span className="text-slate-500">Время</span>
            <span className="font-medium text-slate-900">
              {formatTime(violation.timestamp)}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-slate-500">Тип</span>
            <span className="font-medium text-slate-900">
              {TYPE_LABELS[violation.type] ?? violation.type}
            </span>
          </div>
          {violation.track_id && (
            <div className="flex items-center justify-between gap-3">
              <span className="text-slate-500">Track ID</span>
              <span className="font-medium text-slate-900">
                {violation.track_id}
              </span>
            </div>
          )}
        </div>

        {error && <p className="text-xs font-medium text-rose-600">{error}</p>}

        <div className="mt-auto flex gap-2 pt-1">
          <button
            type="button"
            onClick={() => handleDecision('confirmed')}
            disabled={!isOpen || sending !== null}
            className="flex-1 rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sending === 'confirmed' ? '…' : 'Подтвердить'}
          </button>
          <button
            type="button"
            onClick={() => handleDecision('false_alarm')}
            disabled={!isOpen || sending !== null}
            className="flex-1 rounded-lg bg-rose-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {sending === 'false_alarm' ? '…' : 'Ложная тревога'}
          </button>
        </div>
      </div>
    </motion.article>
  );
}