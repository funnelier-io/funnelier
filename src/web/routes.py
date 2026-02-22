"""
Web Dashboard Routes

Routes for the web dashboard pages with real-time API data.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

dashboard_router = APIRouter()

# ── Shared HTML shell with Tailwind, Chart.js, Shabnam font ──
_HEAD = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>فانلیر - {title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <link href="https://cdn.jsdelivr.net/gh/AminFazloon/shabnam-font@main/dist/css/shabnam.min.css" rel="stylesheet">
    <style>
        body {{ font-family: 'Shabnam', sans-serif; }}
        .sidebar-link {{ display:block; padding:0.5rem 0.75rem; border-radius:0.375rem; }}
        .sidebar-link:hover {{ background:#eff6ff; }}
        .sidebar-link.active {{ background:#dbeafe; color:#2563eb; font-weight:600; }}
        .stat-card {{ transition: transform 0.15s; }}
        .stat-card:hover {{ transform: translateY(-2px); }}
        .funnel-bar {{ transition: width 0.6s ease; }}
    </style>
</head>
<body class="bg-gray-50 text-gray-800">
"""

_SIDEBAR = """
<aside class="fixed right-0 top-0 w-60 h-full bg-white shadow-lg z-10 flex flex-col">
    <div class="p-4 border-b">
        <h1 class="text-xl font-bold text-blue-600">🎯 فانلیر</h1>
        <p class="text-xs text-gray-400">تحلیل فانل بازاریابی</p>
    </div>
    <nav class="p-3 flex-1 overflow-y-auto">
        <ul class="space-y-1 text-sm">
            <li><a href="/" class="sidebar-link {a_dash}">📊 داشبورد</a></li>
            <li><a href="/leads" class="sidebar-link {a_leads}">📋 سرنخ‌ها</a></li>
            <li><a href="/funnel" class="sidebar-link {a_funnel}">🔻 فانل فروش</a></li>
            <li><a href="/segments" class="sidebar-link {a_segments}">🎯 بخش‌بندی RFM</a></li>
            <li><a href="/communications" class="sidebar-link {a_comms}">💬 ارتباطات</a></li>
            <li><a href="/team" class="sidebar-link {a_team}">👥 تیم فروش</a></li>
            <li><a href="/settings" class="sidebar-link {a_settings}">⚙️ تنظیمات</a></li>
        </ul>
    </nav>
    <div class="p-3 border-t text-xs text-gray-400" id="user-info">
        <div id="user-name">ورود نشده</div>
    </div>
</aside>
"""

_MAIN_OPEN = '<main class="mr-60 p-6 min-h-screen">'
_MAIN_CLOSE = '</main>'

_AUTH_SCRIPT = """
<script>
const API = '/api/v1';
let TOKEN = localStorage.getItem('token') || '';

async function api(method, path, body) {
    const opts = { method, headers: {'Content-Type':'application/json'} };
    if (TOKEN) opts.headers['Authorization'] = 'Bearer ' + TOKEN;
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(API + path, opts);
    const data = await r.json().catch(()=>({}));
    return { status: r.status, data };
}

async function checkAuth() {
    if (!TOKEN) return null;
    const { status, data } = await api('GET', '/auth/me');
    if (status === 200) {
        document.getElementById('user-name').textContent = data.full_name || data.username;
        return data;
    }
    localStorage.removeItem('token');
    TOKEN = '';
    return null;
}

async function doLogin(username, password) {
    const { status, data } = await api('POST', '/auth/login', { username, password });
    if (status === 200) {
        TOKEN = data.access_token;
        localStorage.setItem('token', TOKEN);
        return data.user;
    }
    return null;
}

function toPersianNum(n) {
    if (n == null) return '۰';
    return String(n).replace(/[0-9]/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
}

function fmtNum(n) {
    if (n == null) return '۰';
    return toPersianNum(Number(n).toLocaleString('en'));
}
</script>
"""

_FOOT = '</body></html>'


def _page(title, active, content, extra_js=""):
    acts = {k: "" for k in ["a_dash","a_leads","a_funnel","a_segments","a_comms","a_team","a_settings"]}
    acts[active] = "active"
    return (
        _HEAD.format(title=title)
        + _SIDEBAR.format(**acts)
        + _MAIN_OPEN + content + _MAIN_CLOSE
        + _AUTH_SCRIPT + extra_js + _FOOT
    )


# ============================================================================
# Dashboard Home
# ============================================================================
@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard_home():
    content = """
    <header class="mb-6 flex items-center justify-between">
        <div>
            <h2 class="text-2xl font-bold">داشبورد</h2>
            <p class="text-sm text-gray-400" id="date-line"></p>
        </div>
        <div id="login-area"></div>
    </header>

    <!-- KPI Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" id="kpi-cards">
        <div class="bg-white p-5 rounded-lg shadow stat-card">
            <div class="text-xs text-gray-400">سرنخ‌ها</div>
            <div class="text-2xl font-bold text-blue-600" id="kpi-leads">-</div>
        </div>
        <div class="bg-white p-5 rounded-lg shadow stat-card">
            <div class="text-xs text-gray-400">پیامک ارسالی</div>
            <div class="text-2xl font-bold text-purple-600" id="kpi-sms">-</div>
        </div>
        <div class="bg-white p-5 rounded-lg shadow stat-card">
            <div class="text-xs text-gray-400">تماس‌ها</div>
            <div class="text-2xl font-bold text-green-600" id="kpi-calls">-</div>
        </div>
        <div class="bg-white p-5 rounded-lg shadow stat-card">
            <div class="text-xs text-gray-400">محصولات</div>
            <div class="text-2xl font-bold text-amber-600" id="kpi-products">-</div>
        </div>
    </div>

    <!-- Funnel + RFM row -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="bg-white p-5 rounded-lg shadow">
            <h3 class="font-bold mb-3">فانل فروش</h3>
            <canvas id="funnelChart" height="220"></canvas>
        </div>
        <div class="bg-white p-5 rounded-lg shadow">
            <h3 class="font-bold mb-3">توزیع بخش‌بندی RFM</h3>
            <canvas id="rfmChart" height="220"></canvas>
        </div>
    </div>

    <!-- Team table -->
    <div class="bg-white p-5 rounded-lg shadow">
        <h3 class="font-bold mb-3">تیم فروش</h3>
        <table class="w-full text-sm">
            <thead><tr class="text-right text-gray-400 border-b">
                <th class="pb-2">نام</th><th class="pb-2">منطقه</th>
                <th class="pb-2">سرنخ‌ها</th><th class="pb-2">تبدیل</th>
            </tr></thead>
            <tbody id="team-tbody"></tbody>
        </table>
    </div>
    """

    js = """
<script>
(async function() {
    document.getElementById('date-line').textContent = new Date().toLocaleDateString('fa-IR');

    const user = await checkAuth();
    const la = document.getElementById('login-area');
    if (!user) {
        la.innerHTML = '<a href="/login" class="text-sm bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">ورود</a>';
    } else {
        la.innerHTML = '<span class="text-sm text-gray-500">سلام، ' + (user.full_name||user.username) + '</span>';
    }

    // Fetch real data
    const [leads, sms, calls, products, funnel, rfm, team] = await Promise.all([
        api('GET', '/leads/stats/summary'),
        api('GET', '/communications/sms/stats'),
        api('GET', '/communications/calls/stats'),
        api('GET', '/sales/products'),
        api('GET', '/analytics/analytics/funnel'),
        api('GET', '/segments/segmentation/distribution'),
        api('GET', '/team/salespeople'),
    ]);

    document.getElementById('kpi-leads').textContent = fmtNum(leads.data.total_contacts);
    document.getElementById('kpi-sms').textContent = fmtNum(sms.data.total_sent || sms.data.total_queued || 0);
    document.getElementById('kpi-calls').textContent = fmtNum(calls.data.total_calls);
    document.getElementById('kpi-products').textContent = fmtNum(products.data.total_count);

    // Funnel chart
    if (funnel.data.stage_counts) {
        const labels = Object.keys(funnel.data.stage_counts);
        const values = Object.values(funnel.data.stage_counts);
        const fLabels = {
            lead_acquired:'سرنخ', sms_sent:'پیامک', call_attempted:'تماس',
            call_answered:'پاسخ', invoice_sent:'پیش‌فاکتور',
            invoice_accepted:'تأیید', payment_received:'پرداخت'
        };
        new Chart(document.getElementById('funnelChart'), {
            type: 'bar',
            data: {
                labels: labels.map(l => fLabels[l]||l),
                datasets: [{
                    data: values,
                    backgroundColor: ['#3b82f6','#8b5cf6','#f59e0b','#22c55e','#06b6d4','#10b981','#059669'],
                    borderRadius: 6,
                }]
            },
            options: {
                indexAxis: 'y', plugins: { legend: { display: false } },
                scales: { x: { beginAtZero: true } }
            }
        });
    }

    // RFM chart
    if (rfm.data.segments) {
        const segLabels = { champions:'قهرمانان', loyal:'وفادار', potential_loyalist:'بالقوه',
            new_customers:'جدید', promising:'امیدوار', need_attention:'نیاز توجه',
            about_to_sleep:'رو به خواب', at_risk:'در خطر', cant_lose:'از دست ندهید',
            hibernating:'خواب', lost:'از دست رفته' };
        const colors = ['#059669','#22c55e','#3b82f6','#06b6d4','#8b5cf6',
            '#f59e0b','#f97316','#ef4444','#dc2626','#9ca3af','#6b7280'];
        new Chart(document.getElementById('rfmChart'), {
            type: 'doughnut',
            data: {
                labels: rfm.data.segments.map(s => segLabels[s.segment]||s.segment),
                datasets: [{
                    data: rfm.data.segments.map(s => s.count),
                    backgroundColor: colors.slice(0, rfm.data.segments.length),
                }]
            },
            options: { plugins: { legend: { position: 'right', rtl: true,
                labels: { font: { family: 'Shabnam', size: 11 } } } } }
        });
    }

    // Team table
    if (team.data.salespeople) {
        const tb = document.getElementById('team-tbody');
        team.data.salespeople.forEach(s => {
            tb.innerHTML += '<tr class="border-b"><td class="py-2">' + s.name +
                '</td><td>' + (s.region||'-') +
                '</td><td>' + fmtNum(s.assigned_leads) +
                '</td><td>' + fmtNum(s.conversions) + '</td></tr>';
        });
    }
})();
</script>
    """
    return _page("داشبورد", "a_dash", content, js)


# ============================================================================
# Login Page
# ============================================================================
@dashboard_router.get("/login", response_class=HTMLResponse)
async def login_page():
    return """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>فانلیر - ورود</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/gh/AminFazloon/shabnam-font@main/dist/css/shabnam.min.css" rel="stylesheet">
    <style>body { font-family: 'Shabnam', sans-serif; }</style>
</head>
<body class="bg-gray-50 flex items-center justify-center min-h-screen">
    <div class="bg-white p-8 rounded-xl shadow-lg w-96">
        <h1 class="text-2xl font-bold text-blue-600 text-center mb-2">🎯 فانلیر</h1>
        <p class="text-center text-gray-400 text-sm mb-6">ورود به پنل مدیریت</p>
        <div id="error" class="hidden bg-red-50 text-red-600 p-3 rounded mb-4 text-sm"></div>
        <form id="login-form" class="space-y-4">
            <div>
                <label class="block text-sm text-gray-600 mb-1">نام کاربری</label>
                <input id="username" type="text" class="w-full border rounded-lg p-2.5 text-sm" placeholder="admin" autofocus>
            </div>
            <div>
                <label class="block text-sm text-gray-600 mb-1">رمز عبور</label>
                <input id="password" type="password" class="w-full border rounded-lg p-2.5 text-sm" placeholder="••••••••">
            </div>
            <button type="submit" class="w-full bg-blue-600 text-white py-2.5 rounded-lg hover:bg-blue-700 transition text-sm font-medium">
                ورود
            </button>
        </form>
        <p class="text-xs text-gray-400 text-center mt-4">پیش‌فرض: admin / admin1234</p>
    </div>
<script>
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const u = document.getElementById('username').value;
    const p = document.getElementById('password').value;
    const err = document.getElementById('error');
    err.classList.add('hidden');

    const r = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({username:u, password:p})
    });
    const data = await r.json();
    if (r.ok) {
        localStorage.setItem('token', data.access_token);
        window.location.href = '/';
    } else {
        err.textContent = data.detail || 'خطا در ورود';
        err.classList.remove('hidden');
    }
});
</script>
</body></html>"""


# ============================================================================
# Leads Page
# ============================================================================
@dashboard_router.get("/leads", response_class=HTMLResponse)
async def leads_page():
    content = """
    <h2 class="text-2xl font-bold mb-4">سرنخ‌ها</h2>
    <div class="bg-white rounded-lg shadow p-5">
        <div class="flex gap-3 mb-4">
            <input id="search" type="text" placeholder="جستجو شماره یا نام..." class="border rounded-lg px-3 py-2 text-sm flex-1">
            <button onclick="loadContacts()" class="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm">جستجو</button>
        </div>
        <table class="w-full text-sm">
            <thead><tr class="text-right text-gray-400 border-b">
                <th class="pb-2">نام</th><th class="pb-2">شماره</th>
                <th class="pb-2">مرحله</th><th class="pb-2">دسته‌بندی</th>
                <th class="pb-2">تاریخ ایجاد</th>
            </tr></thead>
            <tbody id="contacts-tbody"></tbody>
        </table>
        <div class="mt-4 text-sm text-gray-400" id="contacts-info"></div>
    </div>
    """
    js = """
<script>
async function loadContacts() {
    const search = document.getElementById('search').value;
    let path = '/leads/contacts?page_size=50';
    if (search) path += '&search=' + encodeURIComponent(search);
    const { data } = await api('GET', path);
    const tb = document.getElementById('contacts-tbody');
    tb.innerHTML = '';
    const stages = {lead_acquired:'سرنخ',sms_sent:'پیامک',call_attempted:'تماس',
        call_answered:'پاسخ',invoice_sent:'فاکتور',payment_received:'پرداخت'};
    (data.contacts||[]).forEach(c => {
        const d = new Date(c.created_at).toLocaleDateString('fa-IR');
        tb.innerHTML += '<tr class="border-b"><td class="py-2">'+(c.name||'-')+
            '</td><td>'+c.phone_number+'</td><td>'+(stages[c.current_stage]||c.current_stage||'-')+
            '</td><td>'+(c.category||'-')+'</td><td>'+d+'</td></tr>';
    });
    document.getElementById('contacts-info').textContent = 'مجموع: ' + fmtNum(data.total_count);
}
checkAuth(); loadContacts();
</script>"""
    return _page("سرنخ‌ها", "a_leads", content, js)


# ============================================================================
# Funnel Page
# ============================================================================
@dashboard_router.get("/funnel", response_class=HTMLResponse)
async def funnel_page():
    content = """
    <h2 class="text-2xl font-bold mb-4">فانل فروش</h2>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div class="bg-white p-5 rounded-lg shadow">
            <h3 class="font-bold mb-3">نمودار فانل</h3>
            <canvas id="funnelChart" height="300"></canvas>
        </div>
        <div class="bg-white p-5 rounded-lg shadow">
            <h3 class="font-bold mb-3">نرخ تبدیل بین مراحل</h3>
            <div id="conversion-rates" class="space-y-3"></div>
        </div>
    </div>
    <div class="bg-white p-5 rounded-lg shadow mt-6">
        <h3 class="font-bold mb-3">روند فانل (۷ روز اخیر)</h3>
        <canvas id="trendChart" height="200"></canvas>
    </div>
    """
    js = """
<script>
(async function() {
    checkAuth();
    const { data: funnel } = await api('GET', '/analytics/analytics/funnel');
    const { data: trend } = await api('GET', '/analytics/analytics/funnel/trend');

    if (funnel.stage_counts) {
        const labels = Object.keys(funnel.stage_counts);
        const values = Object.values(funnel.stage_counts);
        const fa = {lead_acquired:'سرنخ جدید',sms_sent:'پیامک ارسالی',call_attempted:'تماس',
            call_answered:'پاسخ داده',invoice_sent:'پیش‌فاکتور',invoice_accepted:'تأیید فاکتور',payment_received:'پرداخت'};
        new Chart(document.getElementById('funnelChart'), {
            type: 'bar',
            data: { labels: labels.map(l=>fa[l]||l), datasets: [{
                data: values,
                backgroundColor: ['#3b82f6','#8b5cf6','#f59e0b','#22c55e','#06b6d4','#10b981','#059669'],
                borderRadius: 8 }] },
            options: { indexAxis:'y', plugins:{legend:{display:false}}, scales:{x:{beginAtZero:true}} }
        });

        // Conversion rates
        const cr = document.getElementById('conversion-rates');
        for (let i = 1; i < labels.length; i++) {
            const rate = values[i-1] > 0 ? ((values[i]/values[i-1])*100).toFixed(1) : 0;
            const color = rate > 50 ? 'green' : rate > 20 ? 'amber' : 'red';
            cr.innerHTML += '<div class="flex items-center gap-2"><span class="text-sm w-40">'+
                fa[labels[i-1]]+'→'+fa[labels[i]]+'</span><div class="flex-1 bg-gray-200 rounded-full h-4">'+
                '<div class="bg-'+color+'-500 h-4 rounded-full" style="width:'+rate+'%"></div></div>'+
                '<span class="text-sm font-bold w-12">'+rate+'%</span></div>';
        }
    }

    // Trend chart
    if (trend.snapshots) {
        new Chart(document.getElementById('trendChart'), {
            type: 'line',
            data: {
                labels: trend.snapshots.map(s=>new Date(s.date).toLocaleDateString('fa-IR')),
                datasets: [
                    {label:'سرنخ',data:trend.snapshots.map(s=>s.lead_acquired||0),borderColor:'#3b82f6',tension:0.3},
                    {label:'پیامک',data:trend.snapshots.map(s=>s.sms_sent||0),borderColor:'#8b5cf6',tension:0.3},
                    {label:'پرداخت',data:trend.snapshots.map(s=>s.payment_received||0),borderColor:'#059669',tension:0.3},
                ]
            },
            options: { plugins:{legend:{rtl:true,labels:{font:{family:'Shabnam'}}}}, scales:{y:{beginAtZero:true}} }
        });
    }
})();
</script>"""
    return _page("فانل فروش", "a_funnel", content, js)


# ============================================================================
# Segments Page
# ============================================================================
@dashboard_router.get("/segments", response_class=HTMLResponse)
async def segments_page():
    content = """
    <h2 class="text-2xl font-bold mb-4">بخش‌بندی RFM</h2>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div class="bg-white p-5 rounded-lg shadow">
            <h3 class="font-bold mb-3">توزیع بخش‌ها</h3>
            <canvas id="rfmPie" height="280"></canvas>
        </div>
        <div class="bg-white p-5 rounded-lg shadow">
            <h3 class="font-bold mb-3">پیشنهادات بازاریابی</h3>
            <div id="recs" class="space-y-2 text-sm max-h-80 overflow-y-auto"></div>
        </div>
    </div>
    """
    js = """
<script>
(async function() {
    checkAuth();
    const { data } = await api('GET', '/segments/segmentation/distribution');
    const fa = {champions:'قهرمانان',loyal:'وفادار',potential_loyalist:'بالقوه',
        new_customers:'جدید',promising:'امیدوار',need_attention:'نیاز توجه',
        about_to_sleep:'رو به خواب',at_risk:'در خطر',cant_lose:'از دست ندهید',
        hibernating:'خواب',lost:'از دست رفته'};
    const colors = ['#059669','#22c55e','#3b82f6','#06b6d4','#8b5cf6',
        '#f59e0b','#f97316','#ef4444','#dc2626','#9ca3af','#6b7280'];
    if (data.segments) {
        new Chart(document.getElementById('rfmPie'), {
            type: 'doughnut',
            data: {
                labels: data.segments.map(s=>fa[s.segment]||s.segment),
                datasets: [{ data: data.segments.map(s=>s.count), backgroundColor: colors }]
            },
            options: {plugins:{legend:{position:'right',rtl:true,labels:{font:{family:'Shabnam',size:11}}}}}
        });

        const recs = document.getElementById('recs');
        for (const seg of data.segments) {
            const { data: rec } = await api('GET', '/segments/segmentation/recommendations/' + seg.segment);
            if (rec.recommended_message_types) {
                recs.innerHTML += '<div class="p-3 border rounded-lg"><span class="font-bold">'+(fa[seg.segment]||seg.segment)+
                    '</span> <span class="text-gray-400">('+seg.count+')</span><br>'+
                    '<span class="text-gray-500">پیام: '+rec.recommended_message_types.join(', ')+'</span></div>';
            }
        }
    }
})();
</script>"""
    return _page("بخش‌بندی RFM", "a_segments", content, js)


# ============================================================================
# Communications Page
# ============================================================================
@dashboard_router.get("/communications", response_class=HTMLResponse)
async def communications_page():
    content = """
    <h2 class="text-2xl font-bold mb-4">ارتباطات</h2>
    <div class="grid grid-cols-3 gap-4 mb-6">
        <div class="bg-white p-5 rounded-lg shadow stat-card">
            <div class="text-xs text-gray-400">پیامک ارسالی</div>
            <div class="text-2xl font-bold text-purple-600" id="sms-sent">-</div>
        </div>
        <div class="bg-white p-5 rounded-lg shadow stat-card">
            <div class="text-xs text-gray-400">تماس‌ها</div>
            <div class="text-2xl font-bold text-green-600" id="call-total">-</div>
        </div>
        <div class="bg-white p-5 rounded-lg shadow stat-card">
            <div class="text-xs text-gray-400">قالب‌های پیامک</div>
            <div class="text-2xl font-bold text-blue-600" id="tmpl-count">-</div>
        </div>
    </div>
    <div class="bg-white rounded-lg shadow p-5">
        <h3 class="font-bold mb-3">آخرین پیامک‌ها</h3>
        <table class="w-full text-sm">
            <thead><tr class="text-right text-gray-400 border-b">
                <th class="pb-2">شماره</th><th class="pb-2">محتوا</th>
                <th class="pb-2">وضعیت</th><th class="pb-2">تاریخ</th>
            </tr></thead>
            <tbody id="sms-tbody"></tbody>
        </table>
    </div>
    """
    js = """
<script>
(async function() {
    checkAuth();
    const [sms, calls, tmpls, logs] = await Promise.all([
        api('GET', '/communications/sms/stats'),
        api('GET', '/communications/calls/stats'),
        api('GET', '/communications/templates'),
        api('GET', '/communications/sms/logs'),
    ]);
    document.getElementById('sms-sent').textContent = fmtNum(sms.data.total_sent||sms.data.total_queued||0);
    document.getElementById('call-total').textContent = fmtNum(calls.data.total_calls);
    document.getElementById('tmpl-count').textContent = fmtNum(tmpls.data.total_count);

    const tb = document.getElementById('sms-tbody');
    (logs.data.logs||[]).slice(0,20).forEach(l => {
        const d = new Date(l.sent_at||l.created_at).toLocaleDateString('fa-IR');
        tb.innerHTML += '<tr class="border-b"><td class="py-2">'+l.phone_number+
            '</td><td class="truncate max-w-xs">'+(l.content||'').substring(0,50)+
            '</td><td>'+l.status+'</td><td>'+d+'</td></tr>';
    });
})();
</script>"""
    return _page("ارتباطات", "a_comms", content, js)


# ============================================================================
# Team Page
# ============================================================================
@dashboard_router.get("/team", response_class=HTMLResponse)
async def team_page():
    content = """
    <h2 class="text-2xl font-bold mb-4">تیم فروش</h2>
    <div class="bg-white rounded-lg shadow p-5">
        <table class="w-full text-sm">
            <thead><tr class="text-right text-gray-400 border-b">
                <th class="pb-2">نام</th><th class="pb-2">منطقه</th>
                <th class="pb-2">سرنخ اختصاصی</th><th class="pb-2">تماس‌ها</th>
                <th class="pb-2">تبدیل</th><th class="pb-2">درآمد</th>
            </tr></thead>
            <tbody id="team-tbody"></tbody>
        </table>
    </div>
    """
    js = """
<script>
(async function() {
    checkAuth();
    const { data } = await api('GET', '/team/salespeople');
    const tb = document.getElementById('team-tbody');
    (data.salespeople||[]).forEach(s => {
        tb.innerHTML += '<tr class="border-b"><td class="py-2 font-medium">'+s.name+
            '</td><td>'+(s.region||'-')+'</td><td>'+fmtNum(s.assigned_leads)+
            '</td><td>'+fmtNum(s.total_calls)+'</td><td>'+fmtNum(s.conversions)+
            '</td><td>'+fmtNum(s.revenue)+'</td></tr>';
    });
})();
</script>"""
    return _page("تیم فروش", "a_team", content, js)


# ============================================================================
# Settings Page
# ============================================================================
@dashboard_router.get("/settings", response_class=HTMLResponse)
async def settings_page():
    content = """
    <h2 class="text-2xl font-bold mb-4">تنظیمات</h2>
    <div class="space-y-6">
        <div class="bg-white p-5 rounded-lg shadow">
            <h3 class="font-bold mb-3">اتصالات</h3>
            <p class="text-sm text-gray-500 mb-3">مدیریت اتصال به منابع داده</p>
            <div class="grid grid-cols-3 gap-4">
                <div class="border rounded-lg p-4 text-center">
                    <div class="text-2xl mb-1">🐘</div>
                    <div class="text-sm font-medium">PostgreSQL</div>
                    <div class="text-xs text-green-500">متصل ✓</div>
                </div>
                <div class="border rounded-lg p-4 text-center">
                    <div class="text-2xl mb-1">📱</div>
                    <div class="text-sm font-medium">کاوه‌نگار SMS</div>
                    <div class="text-xs text-gray-400">نیاز به پیکربندی</div>
                </div>
                <div class="border rounded-lg p-4 text-center">
                    <div class="text-2xl mb-1">☎️</div>
                    <div class="text-sm font-medium">Asterisk VoIP</div>
                    <div class="text-xs text-gray-400">نیاز به پیکربندی</div>
                </div>
            </div>
        </div>
        <div class="bg-white p-5 rounded-lg shadow">
            <h3 class="font-bold mb-3">API اطلاعات</h3>
            <p class="text-sm text-gray-500 mb-2">مستندات API:</p>
            <a href="/docs" class="text-blue-600 hover:underline text-sm">/docs - Swagger UI</a><br>
            <a href="/redoc" class="text-blue-600 hover:underline text-sm">/redoc - ReDoc</a>
        </div>
    </div>
    """
    return _page("تنظیمات", "a_settings", content, "<script>checkAuth();</script>")
