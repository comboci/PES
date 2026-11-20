# PES-15 — تست‌های نسخه مرجع

تاریخ: ۲۰ نوامبر ۲۰۲۶  
وضعیت هسته مرجع: **PASS**  
وضعیت Integration واقعی محصول Portfolio Builder: **در انتظار**

## ۱. آزمون‌های خودکار

```sh
python -m unittest discover -s tests -v
```

**نتیجه: ۷۳ تست — ۷۳ موفق — ۰ خطا.**

پوشش‌ها: اعتبار JSON Schema، ۱۵ گروه رکورد، شناسه تکراری، روابط محلی/خارجی، ارجاعات شکسته، چرخه Scope، اولویت Task جدید، زمان Observation جدید، استثنای Legacy، اعتبار Source Digest، محرمانگی اولیه، Decision مربوط به Solution، تفکیک Verification و Acceptance، عدم حذف تاریخچه، Retrieval، مهاجرت قطعی و غیرمخرب، CAS SQLite، تاریخچه زنجیره‌ای، بکاپ آنلاین، بررسی تحریف، دو فرایند مستقل، ۸ نویسنده همزمان و Rollback تراکنش پس از قطع ناگهانی فرایند.

## ۲. تست انتهابه‌انتها

```sh
python tools/evaluate_portfolio_builder.py --output-dir examples/portfolio_builder_demo_run
```

**نتیجه: PASS.**

- فایل PES-14 نمونه قبل و بعد از اجرا **بیت‌به‌بیت ثابت** ماند (SHA-256 برابر).
- رکوردها، Scopeها و Relationshipهای قدیمی بدون تبدیل ساختگی و حذف به PES-15 منتقل شدند.
- استثنای یک Task قدیمی فاقد Priority و یک Observation فاقد Timestamp به‌شکل صریح ثبت شد.
- Context اختصاصی Storage با Contract کامل PES-15 ساخته شد؛ هشدارهای فقدان تأیید Source و Acceptance حفظ شد.
- Revision 2 با نوشتن مجاز ساخته شد؛ نوشتن عامل با Revision قدیمی رد شد.
- SQLite تاریخچه‌دار بررسی و Backup مستقل با ۲ Revision ساخته و بررسی شد.

مسیر خروجی نمونه: `examples/portfolio_builder_demo_run/`، شامل گزارش `integration_report.json` و DB و Backup قابل بازشدن.

## ۳. بررسی GitHub واقعی (خواندنی)

در بررسی فایل PES-14 اصلی از GitHub در ۲۰ نوامبر ۲۰۲۶: **۱۲۵ رکورد، ۱۰ Scope، ۳۱ Task، ۳۵ Observation**؛ بررسی اولیه Duplicate ID و ارجاعات داخلی صفر مشکل نشان داد. همه ۳۱ Task فاقد Priority و هر ۳۵ Observation فاقد observed_at بودند. Blob SHA و جزئیات در `examples/GITHUB-READONLY-AUDIT-2026-11-20.json`.

**محدودیت مهم:** تست Python کامل PES-15 روی کل فایل جاری GitHub هنوز اجرا نشده؛ GitHub با کانکتور فقط از لحاظ ساختاری بررسی شد و محیط اجرای Python نسخه کپی قابل استفاده از آن فایل را نداشت. نتایج ۷۳ تست و E2E مربوط به Fixture نماینده و موتور محلی است، نه آزمون Runtime اپ Portfolio Builder.

## ۴. قدم‌های ضروری پیش از Production

1. اجرای همان E2E روی فایل **جدیدترین نسخه واقعی** `Project-Evolution-V1-PES-14.json`، بدون تغییر آن و با گزارش امضا/Hash نگهداری‌شده خارج از DB.
2. تست Integration خود نرم‌افزار، UI/Tauri و SQLite محصول، تفاوت Build/Runtime و Owner Acceptance.
3. آزمون عملی قطع برق، Disk Full، بازیابی از Backup و بار همزمان چند Agent روی سخت‌افزار مقصد.
4. بازبینی Threat Model، دسترسی فایل DB، بررسی حرفه‌ای اسرار، سیاست حفظ حریم خصوصی و فایل‌های Log.
5. تصمیم و تأیید جداگانه مالک برای فعال‌کردن PE-15 در برنامه. **PE-14 به‌صورت مستقل باقی می‌ماند.**
