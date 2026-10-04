// backend UTC veriyor, saat dilimi yoksa da UTC sayıyor
export function parseApiDate(iso: string): Date {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`);
}

// tarayıcının yerel saatiyle SS:DD
export function formatClock(value: number | string): string {
  return new Date(value).toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}
