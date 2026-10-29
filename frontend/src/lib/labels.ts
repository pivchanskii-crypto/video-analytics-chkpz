export const TYPE_LABELS: Record<string, string> = {
  no_pre: 'Без СИЗ',
  zone_entry: 'Вход в зону',
  unauthorized: 'Несанкционированный доступ',
};

export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(date);
}