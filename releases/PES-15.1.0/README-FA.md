# Project Evolution Standard 15 — PES-15

**نسخه:** `15.1.0` — پیاده‌سازی مرجع مستقل، آزموده‌شده در سطح هسته.  
**سازگاری:** PES-14 بدون تغییر باقی می‌ماند؛ مهاجرت تنها با دستور صریح و روی **کپی جدید** انجام می‌شود.  
**پلتفرم مرجع:** Python 3.10+، Windows / Linux / macOS، SQLite محلی، بدون سرویس خارجی.  
**وضعیت:** هسته CLI و آزمون‌های خودکار تکمیل؛ اتصال به اپ Portfolio Builder و تأیید عملیاتی مالک هنوز انجام نشده است.


## اصلاح جدید: مراحل کاملاً مستقل Task در PES-15.1

**تنظیم اولویت (P0/P1/...) یا رنگ‌بندی، به‌معنای انجام تسک نیست.** Task اکنون پنج
مرحله مستقل دارد: **تحلیل، اولویت‌بندی، اجرا/اصلاح، راستی‌آزمایی و پذیرش نهایی**.
برای هر Task، فیلد `workflow.deliverable_phase` مشخص می‌کند خروجی مورد انتظار
خود آن تسک چیست. مثلاً Task اصلاحی فقط وقتی «اصلاح انجام شده» محسوب می‌شود که
مرحله `implementation` با ارجاع به خروجی واقعی تکمیل شده باشد؛ تکمیل
`prioritization` به‌تنهایی هیچ مرحله دیگری را تمام نمی‌کند.

این وضعیت‌ها مستقل می‌مانند؛ **پیاده‌سازی کامل** الزاماً به معنی **تست موفق**
یا **تأیید مالک** نیست. Test باید رکورد Verification معتبر داشته باشد و پذیرش
باید رکورد Acceptance مستقل داشته باشد. گزارش نهایی همواره چهار وضعیت جدا
نمایش می‌دهد: انجام خروجی، انجام اصلاح، گذراندن آزمون و تأیید مالک.

برای یک Task که *هدفش صرفاً اولویت‌بندی* است، تمام شدن همان فاز می‌تواند به
معنای تحویل خروجی آن Task باشد، ولی این موضوع هیچ Task اصلاحی دیگری را
تکمیل نمی‌کند. `status` قدیمی صرفاً توصیفی است و منبع معتبر مراحل جدید نیست.

**دستورات جدید، همگی بدون تغییر فایل اصلی:**

```powershell
# وضعیت مستقل مراحل یک تسک تاریخی را بخوان (نامعلوم، نه انجام‌شده)
py -m pes15 task-status examples/portfolio_builder_migrated_v15_demo.json --task TASK-DEMO-LEGACY-001

# برای یک Task قدیمی، در یک کپی جدید فقط ساختار مراحل را آغاز کن (بدون حدس زدن پیشرفت و با وضعیت «نامعلوم» برای همه مراحل)
py -m pes15 task-workflow-init examples/portfolio_builder_migrated_v15_demo.json --task TASK-DEMO-LEGACY-001 --deliverable-phase implementation --output my-task-workflow.json

# یک تغییر فاز را فقط روی کپی جدید آماده کن؛ برای اجرای واقعی شناسه شواهد معتبر لازم است
py -m pes15 task-phase my-task-workflow.json --task TASK-DEMO-LEGACY-001 --phase prioritization --state in_progress --output my-task-priority-started.json

# ارتقای نسخه ۱۵.۰ به نسخه ۱۵.۱ فقط به انتخاب شما و با خروجی جدید
py -m pes15 upgrade-v15 pes15-old.json --output pes15-1-new.json
```

پیش‌نمایش آفلاین پنج سکشن در فایل `examples/task-workflow-sections.html` قرار دارد؛ با بازکردن آن در مرورگر و انتخاب فایل PES-15 می‌توان مراحل را **فقط مشاهده** کرد.

برای ثبت نتیجه واقعی، Snapshot جدید را با `store.commit` و همان کنترل
Revision/SHA ثبت کنید. **هیچ تغییر خودکاری در PES-14 یا HTML برنامه Portfolio
Builder ایجاد نشده است.** برای رابط‌های HTML نیز هر مرحله باید سکشن/برچسب
مستقل داشته باشد؛ رنگ و رتبه نباید علامت انجام اصلاح باشد.

## PES-15 چه چیزی است؟

PES-15 یک استاندارد و موتور قابل اجرا برای ثبت دانش پایدار پروژه، منشأ داده‌ها، تصمیم‌ها، الزامات، یافته‌ها، وظایف و روابط بین آن‌هاست. کارکرد آن مستقل از تاریخچه چت و مستقل از ارائه‌دهنده AI طراحی شده است.

این نسخه یک **نرم‌افزار جداگانه برای مدیریت پروژه** یا جایگزین مستقیم پایگاه داده Portfolio Builder نیست؛ یک موتور مرجع برای دانش و وضعیت پروژه است که اپلیکیشن می‌تواند با API/CLI آن ارتباط برقرار کند.

## شروع سریع در ویندوز

پس از Extract کردن بسته در یک مسیر مستقل، PowerShell را در ریشه باز کنید:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
py -m pes15 verify-package
py -m pes15 validate examples/portfolio_builder_migrated_v15_demo.json
py tools/evaluate_portfolio_builder.py --output-dir .\my-first-pes15-test
```

خروجی `my-first-pes15-test` یک پایگاه SQLite آزمایشی، فایل مهاجرت‌شده، Context، بکاپ و گزارش جامع تولید می‌کند. **این اجرا هیچ فایل PES-14 یا سورس Portfolio Builder را تغییر نمی‌دهد.**

## تجربه روی فایل واقعی Portfolio Builder

اگر مخزن را محلی دارید، مسیر فایل `project evolution/Project-Evolution-V1-PES-14.json` را وارد کنید:

```powershell
py tools/evaluate_portfolio_builder.py `
  --source "B:\ChatGPT Project\NSP-Portfolio-Builder\project evolution\Project-Evolution-V1-PES-14.json" `
  --output-dir "B:\PES15-Independent-Evaluation"
```

این مسیر **فقط نمونه نحوه فراخوانی** است؛ باید با مسیر واقعی مخزن روی سیستم خودتان جایگزین شود. فایل Canonical پروژه در GitHub تغییر نمی‌کند. خروجی جدید ممکن است برای بعضی داده‌های قدیمی نیازمند بررسی و رفع تعارض باشد؛ برنامه در صورت ناسازگاری، مهاجرت را با خطای صریح متوقف می‌کند.

## دستورات اصلی

```sh
python -m pes15 init-bootstrap --output new-pes15-bootstrap.json
python -m pes15 validate snapshot-v15.json --json
python -m pes15 migrate project-pes14.json --output project-pes15.json
python -m pes15 retrieve project-pes15.json --contract RETRIEVAL-PES15-FULL --scope SC-STORAGE --output context.json
python -m pes15 store-init project-pes15.json --db canonical-v15.sqlite --actor developer
python -m pes15 head --db canonical-v15.sqlite
python -m pes15 commit revised-v15.json --db canonical-v15.sqlite --expected-rev 1 --expected-sha SHA_FROM_HEAD --actor agent-A --reason "task updated"
python -m pes15 history --db canonical-v15.sqlite
python -m pes15 verify-store --db canonical-v15.sqlite
python -m pes15 store-backup --db canonical-v15.sqlite --output canonical-backup.sqlite
python -m pes15 export --db canonical-v15.sqlite --revision 1 --output history-1.json
```

- هنگام نوشتن دو فیلد `--expected-rev` و `--expected-sha` هر دو اجباری هستند. در صورت تعارض، **Commit انجام نمی‌شود**؛ نویسنده باید دوباره بخواند و اختلاف را حل کند.
- `init-bootstrap` یک قالب خام می‌سازد. قالب خام مجاز نیست مستقیماً به‌عنوان Canonical Store تثبیت شود؛ ابتدا باید هویت پروژه و Artifact مشخص شود.
- Migration هرگز با `--output` برابر مسیر مبدا، یا در مسیر یک فایل موجود، انجام نمی‌شود.
- امتیاز/اولویت تاریخی ناموجود **حدس زده نمی‌شود**؛ استثناهای تاریخی در `_pes.legacy_exceptions` ثبت می‌شوند. رکورد **جدید** بدون اولویت/زمان مشاهده در Validator رد می‌شود.
- فایل‌های قدیمی PES-14، Manifest و Schema مربوط به آن در این بسته تغییر یا جایگزین نشده‌اند.

## ساختار فایل‌ها

| مسیر | نقش |
|---|---|
| `pes15/resources/PES-15.schema.json` | قرارداد ساختار JSON مبتنی بر Draft 2020-12 |
| `pes15/resources/PES-15.semantic-rules.json` | قواعد و تفکیک خودکار/غیرخودکار |
| `pes15/resources/PES-15.compatibility-profile.json` | سیاست همزیستی نسخه‌های ۱۴ و ۱۵ |
| `pes15/validation.py` | اعتبارسنجی ساختار، پیوندها، پنج مرحله مستقل، خطاها و اسرار آشکار |
| `pes15/task_workflow.py` | ساخت و به‌روزرسانی تک‌مرحله‌ای، گزارش جداگانه مراحل |
| `pes15/migration.py` | مهاجرت کپی‌شونده و غیرمخرب |
| `pes15/store.py` | SQLite تاریخچه‌دار، CAS، بکاپ قابل بازیابی |
| `pes15/retrieval.py` | بازیابی زمینه با ردگیری منشأ و هشدار عدم قطعیت |
| `pes15/cli.py` | رابط فرمان قابل استفاده در ویندوز/CI |
| `tools/evaluate_portfolio_builder.py` | تست انتهابه‌انتها روی کپی پروژه |
| `examples/` | داده نمونه و گزارش اجرای آزمایشی |
| `tests/` | تست واحد، منفی، مهاجرت، همزمانی و بکاپ |

## محدوده ضمانت

پیاده‌سازی مرجع، اعتبار ساختاری و پیوندهای داخلی را کنترل می‌کند؛ **درست‌بودن یک ادعای فنی درباره سورس GitHub، موفقیت Build، سالم بودن Runtime یا تأیید نهایی کاربر را مستقلاً اثبات نمی‌کند.** داده‌های Derived View همراه با وضعیت Freshness نمایش داده می‌شوند و Context هرگز خود را نسخه زنده اثبات‌شده معرفی نمی‌کند.

ثبت وضعیت یک Task با `completed`، به‌معنای `Verification` یا `Acceptance` نیست. رابطه خارجی نیز فقط یک ارجاع تایپ‌شده محسوب می‌شود و بدون اتصال به منبع خارجی تأیید نمی‌گردد.

## امنیت و قابلیت اطمینان

- CAS اتمیک روی دو مقدار Revision و Snapshot SHA در تراکنش SQLite `BEGIN IMMEDIATE`.
- تاریخچه Append-only با SHA-256 داده و زنجیره هش رویدادها؛ تصحیح یا Restore نیز باید با نوشتن Revision جدید و رعایت ثبات شناسه‌ها انجام شود.
- بکاپ با SQLite Online Backup API، صحت‌سنجی زنجیره هش و انتشار بدون بازنویسی.
- تشخیص ابتدایی کلیدهای حساس و قالب‌های شناخته‌شده Private Key؛ **جایگزین ابزار حرفه‌ای Secret Scanning نیست**.
- `validate --json` برای گزارش ماشین‌خوان و مانع شدن از Commit داده نامعتبر.
- زنجیره هش داخلی بدون امضا/لنگر بیرونی، در برابر مهاجمی که کل دیتابیس را بازنویسی و همه هش‌ها را از نو محاسبه کند، اثبات رمزنگاری مستقل ارائه نمی‌دهد.
- SQLite روی دیسک محلی پیشنهاد می‌شود؛ برای چند ماشین مجزا لازم است یک سرویس واحد و کنترل تراکنش سمت سرور استفاده شود. SQLite مستقیم روی Network File Share برای چند نویسنده توصیه نمی‌شود.

## ادامه کار و پذیرش

قبل از ادغام عملی در Portfolio Builder: مهاجرت کامل از **فایل واقعی جدیدترین main**، تست بار واقعی چند Process، آزمون قطع برق سخت‌افزاری، سنجش حجم/Performance، بررسی امنیت و تست رابط محصول باید جداگانه انجام و توسط مالک پذیرفته شود.

جزئیات در `PES-15-STANDARD.md` و `PORTFOLIO-BUILDER-INTEGRATION-FA.md` آمده است.
