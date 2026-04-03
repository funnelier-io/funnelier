export interface Product {
  id: string;
  tenant_id: string;
  name: string;
  code: string | null;
  description: string | null;
  category: string;
  unit: string;
  base_price: number;
  current_price: number;
  is_available: boolean;
  recommended_segments: string[];
  is_active: boolean;
  metadata: Record<string, unknown>;
  price_updated_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface ProductListResponse {
  products: Product[];
  total_count: number;
}

export interface InvoiceLineItem {
  id: string;
  tenant_id: string;
  invoice_id: string;
  product_id: string | null;
  product_name: string;
  product_code: string | null;
  quantity: number;
  unit: string;
  unit_price: number;
  total_price: number;
}

export interface Invoice {
  id: string;
  tenant_id: string;
  invoice_number: string;
  contact_id: string | null;
  phone_number: string;
  customer_name: string | null;
  salesperson_id: string | null;
  salesperson_name: string | null;
  line_items: InvoiceLineItem[];
  subtotal: number;
  discount_amount: number;
  tax_amount: number;
  total_amount: number;
  status: string;
  issued_at: string | null;
  due_date: string | null;
  paid_at: string | null;
  cancelled_at: string | null;
  amount_paid: number;
  payment_method: string | null;
  notes: string | null;
  external_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
}

export interface InvoiceListResponse {
  invoices: Invoice[];
  total_count: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
  total_amount: number;
  total_paid: number;
}

export interface Payment {
  id: string;
  tenant_id: string;
  invoice_id: string;
  invoice_number?: string;
  amount: number;
  payment_method: string | null;
  payment_date: string;
  reference_number: string | null;
  notes: string | null;
  created_at: string;
}

export interface PaymentListResponse {
  payments: Payment[];
  total_count: number;
  total_amount: number;
}

export interface SalesStats {
  period_start: string;
  period_end: string;
  total_invoices: number;
  total_paid: number;
  total_cancelled: number;
  total_revenue: number;
  total_outstanding: number;
  average_order_value: number;
  by_product_category: Record<string, unknown>[];
  by_salesperson: Record<string, unknown>[];
  conversion_rate: number;
}

