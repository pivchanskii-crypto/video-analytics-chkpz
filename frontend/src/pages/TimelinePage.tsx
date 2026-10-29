import { useCallback, useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { useViolationStream } from '../hooks/useViolationStream';
import type { ConnectionStatus } from '../hooks/useViolationStream';
import type { Camera, Violation } from '../lib/types';
import ViolationCard from '../components/ViolationCard';
import EventDetails from '../components/EventDetails';
import { CameraIcon } from '../components/icons';
import { clearTokens } from '../lib/auth';
import { listCameras } from '../lib/api';

const STATUS_META: Record<
  ConnectionStatus,
  { label: string; dot: string }
> = {
  connecting: { label: 'Подключение…', dot: 'bg-amber-400' },
  open: { label: 'В сети', dot: 'bg-emerald-500' },
  closed: { label: 'Переподключение…', dot: 'bg-amber-400' },
  error: { label: 'Нет связи', dot: 'bg-rose-500' },
};

const FIELD_CLASS =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20';

const FIELD_LABEL_CLASS =
  'mb-1 block text-xs font-medium uppercase tracking-wide text-slate-500';

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 py-16 text-slate-500">
      <CameraIcon className="h-10 w-10" />
      <p className="mt-3 text-sm font-medium">{message}</p>
    </div>
  );
}

export default function TimelinePage() {
  const navigate = useNavigate();
  const [selectedEvent, setSelectedEvent] = useState<Violation | null>(null);

  const [cameras, setCameras] = useState<Camera[]>([]);
  const [cameraFilter, setCameraFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');

  useEffect(() => {
    let active = true;

    listCameras()
      .then((items) => {
        if (active) {
          setCameras(items);
        }
      })
      .catch(() => {
        // 401 обрабатывается глобально через api.request();
        // прочие ошибки оставляем пустой список камер.
      });

    return () => {
      active = false;
    };
  }, []);

  const onAuthError = useCallback(() => {
    clearTokens();
    navigate('/login', { replace: true });
  }, [navigate]);

  const { violations, status, loadingInitial, setViolations } =
    useViolationStream(onAuthError);

  const handleStatusUpdate = useCallback(
    (eventId: number, newStatus: string) => {
      setViolations((prev) =>
        prev.map((item) =>
          item.id === eventId ? { ...item, status: newStatus } : item,
        ),
      );
      setSelectedEvent((prev) =>
        prev && prev.id === eventId ? { ...prev, status: newStatus } : prev,
      );
    },
    [setViolations],
  );

  const meta = STATUS_META[status];

  return (
    <div className="grid grid-cols-[260px_1fr_360px] h-[calc(100vh-64px)] overflow-hidden">
      <aside className="overflow-y-auto border-r border-slate-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-slate-800">Фильтры</h2>

        <div className="mt-4 space-y-4">
          <div>
            <label htmlFor="filter-camera" className={FIELD_LABEL_CLASS}>
              Камера
            </label>
            <select
              id="filter-camera"
              value={cameraFilter}
              onChange={(event) => setCameraFilter(event.target.value)}
              className={FIELD_CLASS}
            >
              <option value="">Все камеры</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="filter-type" className={FIELD_LABEL_CLASS}>
              Тип нарушения
            </label>
            <select
              id="filter-type"
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value)}
              className={FIELD_CLASS}
            >
              <option value="">Все</option>
              <option value="no_pre">Без СИЗ</option>
              <option value="zone_entry">Вход в зону</option>
              <option value="unauthorized">Посторонний</option>
            </select>
          </div>

          <div>
            <label htmlFor="filter-date" className={FIELD_LABEL_CLASS}>
              Дата
            </label>
            <input
              id="filter-date"
              type="date"
              value={dateFilter}
              onChange={(event) => setDateFilter(event.target.value)}
              className={FIELD_CLASS}
            />
          </div>
        </div>
      </aside>

      <section className="overflow-y-auto bg-slate-50 p-4">
        <header className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold text-slate-800">Лента</h2>
          <span className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-slate-700 ring-1 ring-slate-200">
            <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
            {meta.label}
          </span>
        </header>

        {loadingInitial && violations.length === 0 ? (
          <EmptyState message="Загрузка нарушений…" />
        ) : violations.length === 0 ? (
          <EmptyState message="Нарушений пока нет" />
        ) : (
          <motion.div
            layout
            className="relative grid grid-cols-1 gap-4 xl:grid-cols-2"
          >
            <AnimatePresence mode="popLayout">
              {violations.map((violation) => (
                <ViolationCard
                  key={violation.id}
                  violation={violation}
                  onClick={() => setSelectedEvent(violation)}
                  onStatusUpdate={handleStatusUpdate}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </section>

      <aside className="overflow-y-auto border-l border-slate-200 bg-white p-4">
        <EventDetails
          event={selectedEvent}
          onStatusUpdate={handleStatusUpdate}
        />
      </aside>
    </div>
  );
}