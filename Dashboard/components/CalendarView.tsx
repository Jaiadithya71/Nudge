import { Event } from "@/types";

export default function CalendarView({ events }: { events: Event[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-gray-400">No events today.</p>;
  }

  return (
    <ul className="space-y-1">
      {events.map((e) => (
        <li key={e.id} className="text-sm">
          <span className="font-medium">{e.title}</span>
          <span className="text-gray-400 ml-2">
            {e.start_time} – {e.end_time}
          </span>
        </li>
      ))}
    </ul>
  );
}
