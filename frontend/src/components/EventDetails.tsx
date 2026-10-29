import { useState } from 'react';
import { motion } from 'motion/react';
import {
  AlertTriangle,
  Camera,
  Clock,
  Hash,
  MousePointerClick,
} from 'lucide-react';
import type {
  StatusUpdateHandler,
  Violation,
  ViolationDecision,
} from '../lib/types';
import { ApiError, sendFeedback } from '../lib/api';
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

function EventDetailsPanel({
  event,
  onStatusUpdate,
}: {
  event: Violation;
  onStatusUpdate: StatusUpdateHandler;
}) {
  const [sending, setSending] = useState<ViolationDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imageFailed, setImageFailed] = useState(false);

  const isOpen = event.status === 'open';

  async function handleDecision(decision: ViolationDecision) {
    if (!isOpen || sending !== null) {
      return;
    }
    setSending(decision);
    setError(null);
    try {
      const updated = await sendFeedback(event.id, decision);
      onStatusUpdate(event.id, updated.status);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'Не удалось отправить решение',
      );
    } finally {
      setSending(null);
    }
  }

  const statusStyle =
    STATUS_STYLES[event.status] ?? 'bg-slate-100 text-slate-600';

  return (
    <motion.div
      className="flex h-full flex-col gap-4"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-800">Детали события</h2>
        <span
          className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusStyle}`}
        >
          {STATUS_LABELS[event.status] ?? event.status}
        </span>
      </div>

      <div className="relative h-56 w-full overflow-hidden rounded-xl bg-slate-900">
        {event.frame_url && !imageFailed ? (
          <img
            src={event.frame_url}
            alt={`Кадр нарушения: ${TYPE_LABELS[event.type] ?? event.type}`}
            onError={() => setImageFailed(true)}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-slate-400">
            <Camera className="h-12 w-12" />
            <span className="text-xs font-medium uppercase tracking-wider">
              Фото недоступно
            </span>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <dl className="space-y-3 text-sm">
          <div className="flex items-center gap-3">
            <Camera className="h-4 w-4 shrink-0 text-slate-400" />
            <dt className="text-slate-500">Камера</dt>
            <dd className="ml-auto text-right font-medium text-slate-900">
              {event.camera_name ?? `Камера #${event.camera_id}`}
            </dd>
          </div>
          <div className="flex items-center gap-3">
            <Clock className="h-4 w-4 shrink-0 text-slate-400" />
            <dt className="text-slate-500">Время</dt>
            <dd className="ml-auto text-right font-medium text-slate-900">
              {formatTime(event.timestamp)}
            </dd>
          </div>
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-4 w-4 shrink-0 text-slate-400" />
            <dt className="text-slate-500">Тип нарушения</dt>
            <dd className="ml-auto text-right font-medium text-slate-900">
              {TYPE_LABELS[event.type] ?? event.type}
            </dd>
          </div>
          <div className="flex items-center gap-3">
            <Hash className="h-4 w-4 shrink-0 text-slate-400" />
            <dt className="text-slate-500">Track ID</dt>
            <dd className="ml-auto text-right font-medium text-slate-900">
              {event.track_id ?? '—'}
            </dd>
          </div>
        </dl>
      </div>

      {error && (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs font-medium text-rose-600">
          {error}
        </p>
      )}

      <div className="mt-auto flex gap-3">
        <motion.button
          type="button"
          disabled={!isOpen || sending !== null}
          onClick={() => handleDecision('confirmed')}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="flex-1 rounded-lg bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {sending === 'confirmed' ? 'Отправка…' : 'Подтвердить'}
        </motion.button>
        <motion.button
          type="button"
          disabled={!isOpen || sending !== null}
          onClick={() => handleDecision('false_alarm')}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="flex-1 rounded-lg bg-rose-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {sending === 'false_alarm' ? 'Отправка…' : 'Ложная тревога'}
        </motion.button>
      </div>
    </motion.div>
  );
}

export default function EventDetails({
  event,
  onStatusUpdate,
}: {
  event: Violation | null;
  onStatusUpdate: StatusUpdateHandler;
}) {
  if (!event) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-slate-400">
        <MousePointerClick className="h-10 w-10" />
        <p className="text-sm font-medium">Выберите событие из ленты</p>
      </div>
    );
  }

  return (
    <EventDetailsPanel
      key={event.id}
      event={event}
      onStatusUpdate={onStatusUpdate}
    />
  );
}