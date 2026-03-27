import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string;
  icon?: string;
  color?: string;
  subtitle?: string;
  change?: number | null;
}

export default function StatCard({
  title,
  value,
  icon,
  color = "text-blue-600",
  subtitle,
  change,
}: StatCardProps) {
  return (
    <div className="bg-white p-5 rounded-lg shadow stat-card">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-400">{title}</span>
        {icon && <span className="text-lg">{icon}</span>}
      </div>
      <div className={cn("text-2xl font-bold", color)}>{value}</div>
      {subtitle && (
        <div className="text-xs text-gray-400 mt-1">{subtitle}</div>
      )}
      {change != null && change !== 0 && (
        <div
          className={cn(
            "text-xs mt-1",
            change > 0 ? "text-green-500" : "text-red-500"
          )}
        >
          {change > 0 ? "▲" : "▼"} {Math.abs(change).toFixed(1)}%
        </div>
      )}
    </div>
  );
}

