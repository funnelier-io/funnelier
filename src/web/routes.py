"""
Web Dashboard Routes

Routes for the web dashboard pages.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse

dashboard_router = APIRouter()


async def get_current_tenant() -> UUID:
    """Get current tenant from session/auth."""
    return UUID("00000000-0000-0000-0000-000000000001")


@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main dashboard page."""
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>فانلیر - داشبورد</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdn.jsdelivr.net/gh/AminFazloon/shabnam-font@main/dist/css/shabnam.min.css" rel="stylesheet">
        <style>
            body { font-family: 'Shabnam', sans-serif; }
        </style>
    </head>
    <body class="bg-gray-100">
        <div class="min-h-screen">
            <!-- Sidebar -->
            <aside class="fixed right-0 top-0 w-64 h-full bg-white shadow-lg">
                <div class="p-4 border-b">
                    <h1 class="text-2xl font-bold text-blue-600">فانلیر</h1>
                    <p class="text-sm text-gray-500">پلتفرم تحلیل فانل بازاریابی</p>
                </div>
                <nav class="p-4">
                    <ul class="space-y-2">
                        <li><a href="/" class="block p-2 rounded bg-blue-50 text-blue-600">داشبورد</a></li>
                        <li><a href="/leads" class="block p-2 rounded hover:bg-gray-50">سرنخ‌ها</a></li>
                        <li><a href="/funnel" class="block p-2 rounded hover:bg-gray-50">فانل فروش</a></li>
                        <li><a href="/segments" class="block p-2 rounded hover:bg-gray-50">بخش‌بندی RFM</a></li>
                        <li><a href="/communications" class="block p-2 rounded hover:bg-gray-50">ارتباطات</a></li>
                        <li><a href="/campaigns" class="block p-2 rounded hover:bg-gray-50">کمپین‌ها</a></li>
                        <li><a href="/team" class="block p-2 rounded hover:bg-gray-50">تیم فروش</a></li>
                        <li><a href="/reports" class="block p-2 rounded hover:bg-gray-50">گزارش‌ها</a></li>
                        <li><a href="/settings" class="block p-2 rounded hover:bg-gray-50">تنظیمات</a></li>
                    </ul>
                </nav>
            </aside>

            <!-- Main Content -->
            <main class="mr-64 p-8">
                <header class="mb-8">
                    <h2 class="text-3xl font-bold text-gray-800">داشبورد</h2>
                    <p class="text-gray-500">خلاصه عملکرد امروز</p>
                </header>

                <!-- KPI Cards -->
                <div class="grid grid-cols-4 gap-6 mb-8">
                    <div class="bg-white p-6 rounded-lg shadow">
                        <div class="text-sm text-gray-500">سرنخ‌های جدید</div>
                        <div class="text-3xl font-bold text-blue-600">۳۵</div>
                        <div class="text-sm text-green-500">+۹.۴٪ نسبت به دیروز</div>
                    </div>
                    <div class="bg-white p-6 rounded-lg shadow">
                        <div class="text-sm text-gray-500">پیامک ارسالی</div>
                        <div class="text-3xl font-bold text-purple-600">۱۲۰</div>
                        <div class="text-sm text-gray-500">۹۱.۷٪ تحویل داده شده</div>
                    </div>
                    <div class="bg-white p-6 rounded-lg shadow">
                        <div class="text-sm text-gray-500">تماس‌های موفق</div>
                        <div class="text-3xl font-bold text-green-600">۱۵</div>
                        <div class="text-sm text-gray-500">از ۸۵ تماس</div>
                    </div>
                    <div class="bg-white p-6 rounded-lg shadow">
                        <div class="text-sm text-gray-500">درآمد امروز</div>
                        <div class="text-3xl font-bold text-amber-600">۲۵M</div>
                        <div class="text-sm text-green-500">+۲۵٪ نسبت به دیروز</div>
                    </div>
                </div>

                <!-- Funnel Overview -->
                <div class="grid grid-cols-2 gap-6 mb-8">
                    <div class="bg-white p-6 rounded-lg shadow">
                        <h3 class="text-lg font-bold mb-4">فانل فروش</h3>
                        <div class="space-y-3">
                            <div class="flex items-center">
                                <div class="w-32 text-sm">سرنخ جدید</div>
                                <div class="flex-1 bg-gray-200 rounded-full h-6">
                                    <div class="bg-blue-500 h-6 rounded-full" style="width: 100%"></div>
                                </div>
                                <div class="w-16 text-left text-sm">۱۰۰۰</div>
                            </div>
                            <div class="flex items-center">
                                <div class="w-32 text-sm">پیامک ارسالی</div>
                                <div class="flex-1 bg-gray-200 rounded-full h-6">
                                    <div class="bg-purple-500 h-6 rounded-full" style="width: 80%"></div>
                                </div>
                                <div class="w-16 text-left text-sm">۸۰۰</div>
                            </div>
                            <div class="flex items-center">
                                <div class="w-32 text-sm">تماس گرفته شده</div>
                                <div class="flex-1 bg-gray-200 rounded-full h-6">
                                    <div class="bg-amber-500 h-6 rounded-full" style="width: 50%"></div>
                                </div>
                                <div class="w-16 text-left text-sm">۵۰۰</div>
                            </div>
                            <div class="flex items-center">
                                <div class="w-32 text-sm">تماس پاسخ داده</div>
                                <div class="flex-1 bg-gray-200 rounded-full h-6">
                                    <div class="bg-green-500 h-6 rounded-full" style="width: 20%"></div>
                                </div>
                                <div class="w-16 text-left text-sm">۲۰۰</div>
                            </div>
                            <div class="flex items-center">
                                <div class="w-32 text-sm">پیش‌فاکتور</div>
                                <div class="flex-1 bg-gray-200 rounded-full h-6">
                                    <div class="bg-cyan-500 h-6 rounded-full" style="width: 10%"></div>
                                </div>
                                <div class="w-16 text-left text-sm">۱۰۰</div>
                            </div>
                            <div class="flex items-center">
                                <div class="w-32 text-sm">پرداخت</div>
                                <div class="flex-1 bg-gray-200 rounded-full h-6">
                                    <div class="bg-emerald-500 h-6 rounded-full" style="width: 5%"></div>
                                </div>
                                <div class="w-16 text-left text-sm">۵۰</div>
                            </div>
                        </div>
                        <div class="mt-4 text-sm text-gray-500">
                            نرخ تبدیل کل: ۵٪
                        </div>
                    </div>

                    <div class="bg-white p-6 rounded-lg shadow">
                        <h3 class="text-lg font-bold mb-4">توزیع بخش‌بندی RFM</h3>
                        <div class="space-y-3">
                            <div class="flex items-center justify-between">
                                <span class="text-sm">قهرمانان</span>
                                <span class="px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-sm">۵۰ (۶.۳٪)</span>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-sm">وفادار</span>
                                <span class="px-2 py-1 bg-green-100 text-green-700 rounded text-sm">۱۰۰ (۱۲.۵٪)</span>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-sm">وفادار بالقوه</span>
                                <span class="px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm">۱۵۰ (۱۸.۸٪)</span>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-sm">در خطر</span>
                                <span class="px-2 py-1 bg-amber-100 text-amber-700 rounded text-sm">۱۲۰ (۱۵٪)</span>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-sm">خواب</span>
                                <span class="px-2 py-1 bg-orange-100 text-orange-700 rounded text-sm">۲۰۰ (۲۵٪)</span>
                            </div>
                            <div class="flex items-center justify-between">
                                <span class="text-sm">از دست رفته</span>
                                <span class="px-2 py-1 bg-red-100 text-red-700 rounded text-sm">۱۰۰ (۱۲.۵٪)</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Team Performance -->
                <div class="bg-white p-6 rounded-lg shadow mb-8">
                    <h3 class="text-lg font-bold mb-4">عملکرد تیم فروش</h3>
                    <table class="w-full">
                        <thead>
                            <tr class="text-right text-sm text-gray-500 border-b">
                                <th class="pb-2">نام</th>
                                <th class="pb-2">تماس‌ها</th>
                                <th class="pb-2">پاسخ داده</th>
                                <th class="pb-2">تبدیل</th>
                                <th class="pb-2">درآمد</th>
                            </tr>
                        </thead>
                        <tbody class="text-sm">
                            <tr class="border-b">
                                <td class="py-2">اسدالهی</td>
                                <td>۱۱۰</td>
                                <td>۳۸</td>
                                <td>۱۷</td>
                                <td>۳۰۰M</td>
                            </tr>
                            <tr class="border-b">
                                <td class="py-2">بردبار</td>
                                <td>۱۰۵</td>
                                <td>۳۶</td>
                                <td>۱۵</td>
                                <td>۲۸۰M</td>
                            </tr>
                            <tr class="border-b">
                                <td class="py-2">رضایی</td>
                                <td>۹۸</td>
                                <td>۳۳</td>
                                <td>۱۴</td>
                                <td>۲۵۰M</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- Recent Activity -->
                <div class="bg-white p-6 rounded-lg shadow">
                    <h3 class="text-lg font-bold mb-4">فعالیت‌های اخیر</h3>
                    <div class="space-y-3">
                        <div class="flex items-center text-sm">
                            <span class="w-24 text-gray-500">۱۰:۳۵</span>
                            <span class="px-2 py-1 bg-green-100 text-green-700 rounded ml-2">پرداخت</span>
                            <span>پرداخت ۵۰M از ۰۹۱۲۳۴۵۶۷۸۹</span>
                        </div>
                        <div class="flex items-center text-sm">
                            <span class="w-24 text-gray-500">۱۰:۲۰</span>
                            <span class="px-2 py-1 bg-blue-100 text-blue-700 rounded ml-2">تماس</span>
                            <span>تماس موفق اسدالهی با ۰۹۱۲۸۷۶۵۴۳۲</span>
                        </div>
                        <div class="flex items-center text-sm">
                            <span class="w-24 text-gray-500">۱۰:۱۵</span>
                            <span class="px-2 py-1 bg-purple-100 text-purple-700 rounded ml-2">پیامک</span>
                            <span>۵۰ پیامک به بخش "در خطر" ارسال شد</span>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    </body>
    </html>
    """


@dashboard_router.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request):
    """Leads management page."""
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>فانلیر - سرنخ‌ها</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100">
        <div class="p-8">
            <h1 class="text-2xl font-bold mb-4">مدیریت سرنخ‌ها</h1>
            <p>صفحه مدیریت سرنخ‌ها در حال توسعه است...</p>
            <a href="/" class="text-blue-500 hover:underline">بازگشت به داشبورد</a>
        </div>
    </body>
    </html>
    """


@dashboard_router.get("/funnel", response_class=HTMLResponse)
async def funnel_page(request: Request):
    """Funnel analytics page."""
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>فانلیر - فانل فروش</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100">
        <div class="p-8">
            <h1 class="text-2xl font-bold mb-4">تحلیل فانل فروش</h1>
            <p>صفحه تحلیل فانل در حال توسعه است...</p>
            <a href="/" class="text-blue-500 hover:underline">بازگشت به داشبورد</a>
        </div>
    </body>
    </html>
    """


@dashboard_router.get("/segments", response_class=HTMLResponse)
async def segments_page(request: Request):
    """RFM segmentation page."""
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>فانلیر - بخش‌بندی RFM</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100">
        <div class="p-8">
            <h1 class="text-2xl font-bold mb-4">بخش‌بندی RFM</h1>
            <p>صفحه بخش‌بندی RFM در حال توسعه است...</p>
            <a href="/" class="text-blue-500 hover:underline">بازگشت به داشبورد</a>
        </div>
    </body>
    </html>
    """


@dashboard_router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    return """
    <!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>فانلیر - تنظیمات</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gray-100">
        <div class="p-8">
            <h1 class="text-2xl font-bold mb-4">تنظیمات</h1>
            <p>صفحه تنظیمات در حال توسعه است...</p>
            <a href="/" class="text-blue-500 hover:underline">بازگشت به داشبورد</a>
        </div>
    </body>
    </html>
    """

