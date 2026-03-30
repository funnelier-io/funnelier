// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface Column<T = any> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
interface DataTableProps<T = any> {
  columns: Column<T>[];
  data: T[];
  emptyMessage?: string;
  isLoading?: boolean;
  onRowClick?: (item: T) => void;
}

export default function DataTable<T>({
  columns,
  data,
  emptyMessage = "داده‌ای یافت نشد",
  isLoading = false,
  onRowClick,
}: DataTableProps<T>) {
  if (isLoading) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">
        در حال بارگذاری...
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-right text-gray-400 border-b border-gray-200">
            {columns.map((col) => (
              <th key={col.key} className="pb-2 px-2 font-medium">
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="text-center py-8 text-gray-400"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item, idx) => (
              <tr
                key={idx}
                className={`border-b border-gray-100 hover:bg-gray-50 transition-colors${
                  onRowClick ? " cursor-pointer" : ""
                }`}
                onClick={onRowClick ? () => onRowClick(item) : undefined}
              >
                {columns.map((col) => (
                  <td key={col.key} className="py-2.5 px-2">
                    {col.render
                      ? col.render(item)
                      : ((item as Record<string, unknown>)[col.key] as React.ReactNode) ?? "-"}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
