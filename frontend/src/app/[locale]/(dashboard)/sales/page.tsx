"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useApi } from "@/lib/hooks";
import StatCard from "@/components/ui/StatCard";
import DataTable from "@/components/ui/DataTable";
import { fmtNum, fmtDate, fmtCurrency } from "@/lib/utils";
import { INVOICE_STATUS_LABELS, INVOICE_STATUS_COLORS } from "@/lib/constants";
import type {
  Invoice,
  InvoiceListResponse,
  Product,
  ProductListResponse,
  PaymentListResponse,
  Payment,
  SalesStats,
} from "@/types/sales";

export default function SalesPage() {
  const t = useTranslations("sales");
  const tc = useTranslations("common");
  const tis = useTranslations("invoiceStatuses");
  const [tab, setTab] = useState<"invoices" | "products" | "payments">(
    "invoices"
  );
  const [invoicePage, setInvoicePage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const pageSize = 20;

  const stats = useApi<SalesStats>("/sales/stats");

  const invoiceQuery =
    statusFilter === "all"
      ? `/sales/invoices?page=${invoicePage}&page_size=${pageSize}`
      : `/sales/invoices?page=${invoicePage}&page_size=${pageSize}&status=${statusFilter}`;

  const invoices = useApi<InvoiceListResponse>(
    tab === "invoices" ? invoiceQuery : null
  );
  const products = useApi<ProductListResponse>(
    tab === "products" ? "/sales/products" : null
  );
  const payments = useApi<PaymentListResponse>(
    tab === "payments" ? "/sales/payments" : null
  );

  const invoiceTotalPages = invoices.data
    ? Math.ceil(invoices.data.total_count / pageSize)
    : 0;

  /* ---- Invoice columns ---- */
  const invoiceColumns = [
    {
      key: "invoice_number",
      header: t("columns.invoiceNumber"),
      render: (inv: Invoice) => (
        <span className="font-mono text-xs" dir="ltr">
          {inv.invoice_number}
        </span>
      ),
    },
    {
      key: "customer_name",
      header: t("columns.customer"),
      render: (inv: Invoice) => (
        <div>
          <div className="text-sm font-medium">
            {inv.customer_name || "—"}
          </div>
          <div className="font-mono text-xs text-gray-400" dir="ltr">
            {inv.phone_number}
          </div>
        </div>
      ),
    },
    {
      key: "total_amount",
      header: t("columns.totalAmount"),
      render: (inv: Invoice) => (
        <span className="text-sm font-semibold text-gray-800">
          {fmtCurrency(inv.total_amount)}
        </span>
      ),
    },
    {
      key: "amount_paid",
      header: t("columns.amountPaid"),
      render: (inv: Invoice) =>
        inv.amount_paid > 0 ? (
          <span className="text-sm text-green-600 font-medium">
            {fmtCurrency(inv.amount_paid)}
          </span>
        ) : (
          <span className="text-gray-300 text-xs">—</span>
        ),
    },
    {
      key: "status",
      header: t("columns.status"),
      render: (inv: Invoice) => (
        <span
          className={`inline-block px-2 py-0.5 rounded-full text-xs ${
            INVOICE_STATUS_COLORS[inv.status] || "bg-gray-100 text-gray-600"
          }`}
        >
          {INVOICE_STATUS_LABELS[inv.status] || inv.status}
        </span>
      ),
    },
    {
      key: "line_items",
      header: t("columns.items"),
      render: (inv: Invoice) => (
        <span className="text-xs text-gray-500">
          {tc("items", { count: inv.line_items?.length ?? 0 })}
        </span>
      ),
    },
    {
      key: "issued_at",
      header: t("columns.issuedDate"),
      render: (inv: Invoice) => (
        <span className="text-xs text-gray-500">
          {fmtDate(inv.issued_at || inv.created_at)}
        </span>
      ),
    },
  ];

  /* ---- Product columns ---- */
  const productColumns = [
    {
      key: "name",
      header: t("columns.productName"),
      render: (p: Product) => (
        <div>
          <div className="text-sm font-medium">{p.name}</div>
          {p.code && (
            <span className="text-xs text-gray-400 font-mono" dir="ltr">
              {p.code}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "category",
      header: t("columns.category"),
      render: (p: Product) => (
        <span className="px-2 py-0.5 rounded-full text-xs bg-purple-50 text-purple-700">
          {p.category}
        </span>
      ),
    },
    {
      key: "current_price",
      header: t("columns.currentPrice"),
      render: (p: Product) => (
        <span className="text-sm font-semibold text-gray-800">
          {fmtCurrency(p.current_price)}
        </span>
      ),
    },
    {
      key: "base_price",
      header: t("columns.basePrice"),
      render: (p: Product) => (
        <span className="text-xs text-gray-400">
          {fmtCurrency(p.base_price)}
        </span>
      ),
    },
    {
      key: "unit",
      header: t("columns.unit"),
      render: (p: Product) => (
        <span className="text-xs text-gray-500">{p.unit}</span>
      ),
    },
    {
      key: "is_available",
      header: t("columns.availability"),
      render: (p: Product) =>
        p.is_available ? (
          <span className="text-xs text-green-600 font-medium">{t("available")}</span>
        ) : (
          <span className="text-xs text-red-500">{t("unavailable")}</span>
        ),
    },
    {
      key: "recommended_segments",
      header: t("columns.targetSegments"),
      render: (p: Product) =>
        p.recommended_segments && p.recommended_segments.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {p.recommended_segments.slice(0, 2).map((s) => (
              <span
                key={s}
                className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded"
              >
                {s}
              </span>
            ))}
            {p.recommended_segments.length > 2 && (
              <span className="text-[10px] text-gray-400">
                +{p.recommended_segments.length - 2}
              </span>
            )}
          </div>
        ) : (
          <span className="text-gray-300 text-xs">—</span>
        ),
    },
  ];

  /* ---- Payment columns ---- */
  const paymentColumns = [
    {
      key: "invoice_number",
      header: t("columns.invoice"),
      render: (p: Payment) => (
        <span className="font-mono text-xs" dir="ltr">
          {p.invoice_number || p.invoice_id.slice(0, 8)}
        </span>
      ),
    },
    {
      key: "amount",
      header: t("columns.amount"),
      render: (p: Payment) => (
        <span className="text-sm font-semibold text-green-600">
          {fmtCurrency(p.amount)}
        </span>
      ),
    },
    {
      key: "payment_method",
      header: t("columns.paymentMethod"),
      render: (p: Payment) => (
        <span className="text-xs text-gray-600">
          {p.payment_method || "—"}
        </span>
      ),
    },
    {
      key: "reference_number",
      header: t("columns.referenceNumber"),
      render: (p: Payment) => (
        <span className="font-mono text-xs text-gray-500" dir="ltr">
          {p.reference_number || "—"}
        </span>
      ),
    },
    {
      key: "payment_date",
      header: t("columns.paymentDate"),
      render: (p: Payment) => (
        <span className="text-xs text-gray-500">
          {fmtDate(p.payment_date)}
        </span>
      ),
    },
    {
      key: "notes",
      header: t("columns.notes"),
      render: (p: Payment) => (
        <span className="text-xs text-gray-400 truncate max-w-[150px] block">
          {p.notes || "—"}
        </span>
      ),
    },
  ];

  /* ---- Invoice status tabs ---- */
  const statusTabs = [
    { key: "all", label: tc("all") },
    { key: "draft", label: tis("draft") },
    { key: "issued", label: tis("issued") },
    { key: "paid", label: tis("paid") },
    { key: "overdue", label: tis("overdue") },
    { key: "cancelled", label: tis("cancelled") },
  ];

  function Pagination({
    page,
    totalPages,
    setPage,
  }: {
    page: number;
    totalPages: number;
    setPage: (fn: (p: number) => number) => void;
  }) {
    if (totalPages <= 1) return null;
    return (
      <div className="flex items-center justify-center gap-2 mt-4">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1}
          className="px-3 py-1 text-sm border rounded-md disabled:opacity-30 hover:bg-gray-50"
        >
          {tc("previous")}
        </button>
        <span className="text-sm text-gray-500">
          {tc("page", { current: fmtNum(page), total: fmtNum(totalPages) })}
        </span>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page >= totalPages}
          className="px-3 py-1 text-sm border rounded-md disabled:opacity-30 hover:bg-gray-50"
        >
          {tc("next")}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">{t("title")}</h1>

      {/* KPI Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title={t("totalInvoices")}
          value={fmtNum(stats.data?.total_invoices)}
          icon="🧾"
          color="text-blue-600"
        />
        <StatCard
          title={t("totalRevenue")}
          value={fmtCurrency(stats.data?.total_revenue)}
          icon="💰"
          color="text-green-600"
        />
        <StatCard
          title={t("paidCount")}
          value={fmtNum(stats.data?.total_paid)}
          icon="✅"
          color="text-emerald-600"
        />
        <StatCard
          title={t("avgOrderValue")}
          value={fmtCurrency(stats.data?.average_order_value)}
          icon="📊"
          color="text-purple-600"
          subtitle={
            stats.data?.conversion_rate
              ? t("conversionRate", { rate: `${(stats.data.conversion_rate * 100).toFixed(1)}%` })
              : undefined
          }
        />
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
        <button
          onClick={() => setTab("invoices")}
          className={`px-4 py-2 text-sm rounded-md transition-colors ${
            tab === "invoices"
              ? "bg-white shadow text-blue-700 font-medium"
              : "text-gray-600 hover:text-gray-800"
          }`}
        >
          {t("invoicesTab")}
          {invoices.data && (
            <span className="text-xs text-gray-400 mr-1">
              ({fmtNum(invoices.data.total_count)})
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("products")}
          className={`px-4 py-2 text-sm rounded-md transition-colors ${
            tab === "products"
              ? "bg-white shadow text-blue-700 font-medium"
              : "text-gray-600 hover:text-gray-800"
          }`}
        >
          {t("productsTab")}
          {products.data && (
            <span className="text-xs text-gray-400 mr-1">
              ({fmtNum(products.data.total_count)})
            </span>
          )}
        </button>
        <button
          onClick={() => setTab("payments")}
          className={`px-4 py-2 text-sm rounded-md transition-colors ${
            tab === "payments"
              ? "bg-white shadow text-blue-700 font-medium"
              : "text-gray-600 hover:text-gray-800"
          }`}
        >
          {t("paymentsTab")}
          {payments.data && (
            <span className="text-xs text-gray-400 mr-1">
              ({fmtNum(payments.data.total_count)})
            </span>
          )}
        </button>
      </div>

      {/* Invoices Tab */}
      {tab === "invoices" && (
        <>
          {/* Status filter tabs */}
          <div className="flex gap-2 flex-wrap">
            {statusTabs.map((st) => (
              <button
                key={st.key}
                onClick={() => {
                  setStatusFilter(st.key);
                  setInvoicePage(1);
                }}
                className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                  statusFilter === st.key
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {st.label}
              </button>
            ))}
          </div>

          {/* Invoices summary banner */}
          {invoices.data && (
            <div className="flex items-center gap-4 text-xs text-gray-500 bg-gray-50 rounded-lg px-4 py-2">
              <span>
                {t("totalAmounts")}{" "}
                <span className="font-semibold text-gray-700">
                  {fmtCurrency(invoices.data.total_amount)}
                </span>
              </span>
              <span>
                {t("totalPaid")}{" "}
                <span className="font-semibold text-green-600">
                  {fmtCurrency(invoices.data.total_paid)}
                </span>
              </span>
            </div>
          )}

          <div className="bg-white rounded-lg shadow p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              {t("invoiceList")}
            </h2>
            <DataTable
              columns={invoiceColumns}
              data={invoices.data?.invoices || []}
              isLoading={invoices.isLoading}
              emptyMessage={t("noInvoices")}
            />
            <Pagination
              page={invoicePage}
              totalPages={invoiceTotalPages}
              setPage={setInvoicePage}
            />
          </div>
        </>
      )}

      {/* Products Tab */}
      {tab === "products" && (
        <div className="space-y-4">
          {/* Product categories summary */}
          {products.data && products.data.products.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              {Object.entries(
                products.data.products.reduce(
                  (acc, p) => {
                    acc[p.category] = (acc[p.category] || 0) + 1;
                    return acc;
                  },
                  {} as Record<string, number>
                )
              )
                .sort((a, b) => b[1] - a[1])
                .slice(0, 6)
                .map(([cat, count]) => (
                  <div
                    key={cat}
                    className="bg-white rounded-lg shadow p-3 text-center"
                  >
                    <div className="text-lg font-bold text-purple-600">
                      {fmtNum(count)}
                    </div>
                    <div className="text-xs text-gray-500 truncate">{cat}</div>
                  </div>
                ))}
            </div>
          )}

          <div className="bg-white rounded-lg shadow p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              {t("productCatalog")}
            </h2>
            <DataTable
              columns={productColumns}
              data={products.data?.products || []}
              isLoading={products.isLoading}
              emptyMessage={t("noProducts")}
            />
          </div>
        </div>
      )}

      {/* Payments Tab */}
      {tab === "payments" && (
        <div className="space-y-4">
          {payments.data && (
            <div className="bg-green-50 rounded-lg px-4 py-3 flex items-center gap-4">
              <span className="text-2xl">💳</span>
              <div>
                <div className="text-sm text-green-800 font-semibold">
                  {t("totalPayments", { amount: fmtCurrency(payments.data.total_amount) })}
                </div>
                <div className="text-xs text-green-600">
                  {t("transactionsRegistered", { count: fmtNum(payments.data.total_count) })}
                </div>
              </div>
            </div>
          )}

          <div className="bg-white rounded-lg shadow p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">
              {t("paymentTransactions")}
            </h2>
            <DataTable
              columns={paymentColumns}
              data={payments.data?.payments || []}
              isLoading={payments.isLoading}
              emptyMessage={t("noPayments")}
            />
          </div>
        </div>
      )}
    </div>
  );
}

