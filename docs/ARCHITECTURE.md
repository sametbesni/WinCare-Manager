# Mimari

Bu belge, projeye katkı vermek isteyen geliştiriciler için WinCare Manager'ın nasıl çalıştığını anlatır.

## Katmanlar

```text
main.py            Uygulamayı başlatır: ayarlar, dil, günlük, AppContext, ana pencere
app/               Ortak altyapı (PySide6'dan bağımsız)
  context.py       AppContext: config, translator, history, backups, engine
  config_manager.py  settings.json okuma/yazma, varsayılanlar ve sınır kontrolleri
  i18n.py          Translator ve K() işaretçisi
  admin.py         Yönetici kontrolü ve UAC ile yeniden başlatma
core/              Sistem işlemleri (PySide6'dan bağımsız, test edilebilir)
  engine.py        İşlem motoru ve güvenlik katmanı
  backup.py        .reg yedekleri + SHA-256 manifest
  registry.py      winreg ve reg.exe yardımcıları
  winproc.py       Konsolsuz komut ve PowerShell (JSON) çalıştırma
  cleaner.py, startup.py, processes.py, services.py, disks.py, diagnostics.py, ...
database/history.py  İşlem geçmişi (SQLite)
ui/                PySide6 arayüzü
  main_window.py   Menü ve sayfa yığını
  pages/           Her menü öğesi bir sayfa (BasePage alt sınıfı)
  widgets.py       Ortak bileşenler (Card, MetricCard, make_table, onay pencereleri)
  worker.py        run_async: arka planda iş çalıştırma
locales/           tr_TR.json, en_US.json
tests/             pytest testleri
```

Temel kural: **`core/` arayüzü bilmez, arayüz sistemi doğrudan değiştirmez.**

## İşlem motoru

Sistemi değiştiren her işlem bir `OperationPlan` olarak tanımlanır ve `ctx.engine.run(plan, dry_run=ctx.dry_run)` ile çalıştırılır.

Motor şu adımları sırayla uygular:

1. **Kayıt:** benzersiz bir işlem kimliği oluşturur ve geçmişe "running" yazar.
2. **Yetki:** `requires_admin=True` ise ve yönetici yetkisi yoksa işlemi engeller.
3. **Doğrulama:** `validate()` çağrılır; bir sorun listesi dönerse işlem engellenir.
4. **Deneme modu:** açıksa burada durur; hiçbir şey değişmez.
5. **Yedekleme:** `backup()` çağrılır; hata verirse işlem uygulanmaz.
6. **Uygulama:** `execute()` çalışır ve bir `ExecutionOutcome` döner.
7. **Sonuç:** durum (success, partial, failed …) geçmişe yazılır.

Uygulama beklenmedik biçimde kapanırsa "running" kalan kayıtlar bir sonraki açılışta "interrupted" olarak işaretlenir.

### Örnek

```python
from core.engine import ExecutionOutcome, OperationPlan
from ui.widgets import ask_confirmation, show_operation_result

def _on_apply(self) -> None:
    plan = OperationPlan(
        kind="ornek.islem",              # geçmişte görünen işlem türü
        summary="Kısa açıklama",
        targets=["hedef-1", "hedef-2"],
        validate=lambda: [],             # sorun yoksa boş liste
        backup=lambda: self.ctx.backups.create_registry_backup(...).backup_id,
        execute=lambda: ExecutionOutcome(succeeded=2),
        requires_admin=False,
    )
    if not ask_confirmation(self, self.ctx, self.t("confirm_title"), "...", "..."):
        self.ctx.engine.record_cancelled(plan)
        return
    result = self.ctx.engine.run(plan, dry_run=self.ctx.dry_run)
    show_operation_result(self, self.ctx, result)
```

Gerçek bir örnek için `ui/pages/startup.py` dosyasındaki `_plan` metoduna bakın.

### Deneme modundan etkilenmeyen işlemler

`respects_dry_run=False` yalnızca kullanıcı verisine dokunmayan işlemlerde kullanılır:
- yedek alma;
- Otomatik Bakım görevini kaydetme veya silme. Görev yalnızca analiz yapar ve açıkça kullanıcının tercihidir.

Bu işlemler de onay ister ve geçmişe yazılır.

## Pencere açmadan çalışma (`--maintenance`)

`main.py --maintenance` (veya `WinCare Manager.exe --maintenance`) PySide6'yı hiç yüklemeden `core/maintenance.py` içindeki `analyze_and_record` fonksiyonunu çalıştırır. Bu kip Görev Zamanlayıcı tarafından kullanılır. Ayarlarda Otomatik Bakım kapalıysa hiçbir şey yapmadan çıkar. Analiz salt okunurdur; buraya sistemi değiştiren bir adım eklenmemelidir.

## Yeni bir sayfa ekleme

1. `core/` altına veri toplayan veya işlem yapan modülü yazın (PySide6 kullanmadan).
2. `ui/pages/` altına `BasePage` alt sınıfı oluşturun:
   - `title_key` ve `subtitle_key` sınıf değişkenlerini `K("...")` ile tanımlayın.
   - Veriyi `refresh()` içinde `run_async(fn, on_done, on_error)` ile arka planda yükleyin.
   - Sayfa sürekli güncellenecekse `auto_refresh = True` yapın.
3. `ui/main_window.py` içinde:
   - `NAV_ITEMS` listesine menü öğesini,
   - sayfa sözlüğüne sayfanın örneğini ekleyin.
4. Yeni metin anahtarlarını **iki dil dosyasına da** ekleyin.
5. `tests/` altına `core` modülü için test yazın.
6. `python -m pytest` ile her şeyin geçtiğini doğrulayın.

## Çeviri

- Kodda `ctx.t("anahtar", ad=deger)` kullanılır; metindeki `{ad}` yer tutucusu doldurulur.
- Modül düzeyindeki sabitlerde anahtarlar `K("anahtar")` ile işaretlenir. Böylece test, anahtarın kullanıldığını görür.
- `tests/test_locales.py` iki dosyanın aynı anahtarlara sahip olduğunu, koddaki her anahtarın var olduğunu ve kullanılmayan anahtar kalmadığını denetler.
- Yeni bir dil eklemek için `locales/` altına dosya ekleyip `app/i18n.py` içindeki `SUPPORTED_LANGUAGES` listesini güncelleyin.

## Veriler

Ayarlar, geçmiş, yedekler ve günlük `%LOCALAPPDATA%\WinCareManager\` altında tutulur. Testler `tmp_path` ile geçici bir klasör kullanır ve gerçek verilere dokunmaz.

## Paketleme

`scripts/build_windows.ps1`:
1. testleri çalıştırır,
2. PyInstaller ile onedir paketi oluşturur (`locales`, `theme.qss` ve `assets` dahil),
3. `SHA256SUMS.txt` yazar.

`scripts/build_installer.ps1`, bu klasörden `installer/WinCareManager.iss` ile kurulum dosyası üretir. Sürüm numarası `app/__init__.py` içindeki `__version__` değerinden okunur. `.iss` dosyasındaki `AppId` değeri, yükseltmelerin çalışması için değiştirilmemelidir.

Pakete yeni bir veri dosyası eklerseniz hem `--add-data` satırını güncelleyin hem de dosyaya kodda `app.paths.get_resource_path` ile erişin.
