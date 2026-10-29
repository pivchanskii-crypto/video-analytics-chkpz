import { useEffect, useMemo, useState } from 'react';
import { type LucideIcon, AlertTriangle, Camera, Clock } from 'lucide-react';
import { listCameras, listViolations } from '@/lib/api';
import type { Violation } from '@/lib/types';
import { BarChart } from '@/components/charts/bar-chart';
import { RingChart } from '@/components/charts/ring-chart';
import { Bar } from '@/components/charts/bar';
import { BarXAxis } from '@/components/charts/bar-x-axis';
import { Grid } from '@/components/charts/grid';
import { Ring } from '@/components/charts/ring';
import { RingCenter } from '@/components/charts/ring-center';
import { ChartTooltip, TooltipContent } from '@/components/charts/tooltip';

interface Stats {
  cameras: number;
  activeViolations: number;
  eventsToday: number;
}

const EMPTY_STATS: Stats = {
  cameras: 0,
  activeViolations: 0,
  eventsToday: 0,
};

const STAT_CARDS: {
  key: keyof Stats;
  label: string;
  icon: LucideIcon;
  iconClass: string;
}[] = [
  {
    key: 'cameras',
    label: 'Всего камер',
    icon: Camera,
    iconClass: 'bg-blue-50 text-blue-600',
  },
  {
    key: 'activeViolations',
    label: 'Активные нарушения',
    icon: AlertTriangle,
    iconClass: 'bg-amber-50 text-amber-600',
  },
  {
    key: 'eventsToday',
    label: 'Событий за сегодня',
    icon: Clock,
    iconClass: 'bg-emerald-50 text-emerald-600',
  },
];

const HOURLY_WINDOW_HOURS = 12;

function hourLabel(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:00`;
}

function dateHourKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}-${date.getHours()}`;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>(EMPTY_STATS);
  const [violations, setViolations] = useState<Violation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    Promise.all([listCameras(), listViolations()])
      .then(([cameras, violationsResponse]) => {
        if (!active) {
          return;
        }

        const items = violationsResponse.items;
        const now = new Date();

        setViolations(items);
        setStats({
          cameras: cameras.length,
          activeViolations: items.filter((v) => v.status === 'open').length,
          eventsToday: items.filter((v) => {
            const date = new Date(v.timestamp);
            return (
              date.getFullYear() === now.getFullYear() &&
              date.getMonth() === now.getMonth() &&
              date.getDate() === now.getDate()
            );
          }).length,
        });
      })
      .catch(() => {
        // 401 обрабатывается глобально через api.request();
        // прочие ошибки оставляем нулевые значения.
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const chartData = useMemo(() => {
    const now = new Date();

    const buckets = Array.from({ length: HOURLY_WINDOW_HOURS }, (_, i) => {
      const date = new Date(
        now.getFullYear(),
        now.getMonth(),
        now.getDate(),
        now.getHours() - (HOURLY_WINDOW_HOURS - 1 - i),
      );
      return { date, hour: hourLabel(date), count: 0 };
    });

    const indexByKey = new Map(
      buckets.map((bucket) => [dateHourKey(bucket.date), bucket]),
    );

    for (const violation of violations) {
      const date = new Date(violation.timestamp);
      if (Number.isNaN(date.getTime())) {
        continue;
      }
      const bucket = indexByKey.get(dateHourKey(date));
      if (bucket) {
        bucket.count += 1;
      }
    }

    return buckets.map(({ hour, count }) => ({ hour, count }));
  }, [violations]);

  const ringData = useMemo(() => {
    const total = violations.length;
    const maxValue = Math.max(total, 1);

    return [
      {
        label: 'Новые',
        value: violations.filter((v) => v.status === 'open').length,
        maxValue,
        color: '#f59e0b',
      },
      {
        label: 'Подтверждённые',
        value: violations.filter((v) => v.status === 'confirmed').length,
        maxValue,
        color: '#10b981',
      },
      {
        label: 'Ложные',
        value: violations.filter((v) => v.status === 'false_alarm').length,
        maxValue,
        color: '#f43f5e',
      },
    ];
  }, [violations]);

  return (
    <div className="h-full overflow-y-auto bg-slate-50 p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Обзор системы видеонаблюдения
        </p>
      </header>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {STAT_CARDS.map(({ key, label, icon: Icon, iconClass }) => (
          <div
            key={key}
            className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-slate-500">{label}</p>
                <p
                  className={`mt-2 text-3xl font-bold tabular-nums ${
                    loading ? 'animate-pulse text-slate-300' : 'text-slate-800'
                  }`}
                >
                  {loading ? '—' : stats[key]}
                </p>
              </div>
              <span
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-lg ${iconClass}`}
              >
                <Icon className="h-6 w-6" />
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-slate-800">
            События по часам
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Количество нарушений за выбранный период
          </p>

          <div className="mt-4">
            <BarChart data={chartData} xDataKey="hour" aspectRatio="16 / 9">
              <Grid />
              <Bar dataKey="count" fill="#2563eb" stroke="#2563eb" />
              <BarXAxis />
              <ChartTooltip
                showDatePill={false}
                showDots={false}
                content={({ point }) => (
                  <TooltipContent
                    title={String(point.hour)}
                    rows={[
                      { color: '#2563eb', label: 'Событий', value: Number(point.count) },
                    ]}
                  />
                )}
              />
            </BarChart>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-base font-semibold text-slate-800">
            Нарушения по статусам
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Соотношение обработанных и новых тревог
          </p>

          <div className="mx-auto mt-4 w-full max-w-xs">
            <RingChart data={ringData}>
              <Ring index={0} />
              <Ring index={1} />
              <Ring index={2} />
              <RingCenter defaultLabel="Всего" />
            </RingChart>
          </div>

          <ul className="mx-auto mt-4 w-full max-w-xs space-y-2">
            {ringData.map((item) => (
              <li
                key={item.label}
                className="flex items-center justify-between text-sm"
              >
                <span className="flex items-center gap-2 text-slate-500">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  {item.label}
                </span>
                <span className="font-medium tabular-nums text-slate-800">
                  {item.value}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}