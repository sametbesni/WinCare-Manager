# Katkıda Bulunma Rehberi

WinCare Manager'a katkı vermek istediğiniz için teşekkürler. Bu rehber, değişikliğinizin hızlı ve sorunsuz kabul edilmesi için gerekenleri anlatır.

*English summary at the bottom.*

## Başlamadan önce

- Büyük bir değişiklik (yeni modül, sistemi değiştiren yeni bir işlem) planlıyorsanız önce bir **Issue** açıp fikrinizi anlatın. Böylece boşa emek harcanmaz.
- Küçük düzeltmeler (yazım hatası, çeviri, açık bir hata) için doğrudan Pull Request açabilirsiniz.

## Geliştirme ortamı

Windows 10/11 ve Python 3.12 veya üzeri gerekir.

```powershell
git clone <depo-adresi>
cd Windows-System-Manager
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
.\.venv\Scripts\python.exe main.py
```

Testler:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Projenin nasıl çalıştığını, yeni bir sayfanın veya işlemin nasıl ekleneceğini [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) anlatır.

## Değişmez kurallar

Bu kurallara uymayan Pull Request'ler kabul edilmez. Uygulamanın kullanıcı güvenini bu kurallar sağlar.

1. **Arayüz sisteme doğrudan dokunmaz.** Dosya, kayıt defteri, hizmet gibi her değişiklik `core/engine.py` içindeki `OperationEngine` üzerinden bir `OperationPlan` olarak çalıştırılır.
2. **Deneme modu her yeni işlemde desteklenir.** Deneme modunda kullanıcı verisi ve sistem ayarları değişmemelidir. İstisnalar [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) içinde listelenmiştir.
   - **Otomatik çalışan özellikler varsayılan olarak kapalıdır** ve yalnızca analiz yapar; zamanlanmış bir görev kendiliğinden hiçbir şeyi silmez veya değiştirmez.
3. **Geri alınabilir değişikliklerden önce yedek alınır.** Yedek alınamazsa işlem uygulanmaz.
4. **Kalıcı silme yoktur.** Dosyalar Geri Dönüşüm Kutusu'na taşınır.
5. **Windows sistem klasörleri asla otomatik temizlenmez.** Sembolik bağlantılar ve junction'lar izlenmez.
6. **"Kayıt defteri temizleyici" eklenmez.** Kayıt defterinde rastgele değer silen özellikler kabul edilmez.
7. **Ağ erişimi, telemetri ve dış servis bağlantısı yoktur.** Uygulama tamamen çevrimdışı çalışır; kullanıcı verisi hiçbir yere gönderilmez.
8. **Yönetici yetkisi yalnızca gerektiğinde istenir.** İşlem `requires_admin=True` ile işaretlenir.
9. **Lisans atlatma, crack, keygen ve benzeri içerik** kesinlikle kabul edilmez.

## Kod ve metin kuralları

- Arayüzde görünen her metin `locales/tr_TR.json` ve `locales/en_US.json` dosyalarına **aynı anahtarla** eklenir. Kodda metin sabit yazılmaz; `ctx.t("anahtar")` veya sabitler için `K("anahtar")` kullanılır.
  - `tests/test_locales.py` eksik veya kullanılmayan anahtarları otomatik yakalar.
- Uzun süren işler (tarama, PowerShell çağrısı) arayüzü dondurmamak için `ui/worker.py` içindeki `run_async` ile arka planda çalıştırılır.
- Windows'a özgü komutlar `core/winproc.py` üzerinden çalıştırılır (konsol penceresi açılmaz, UTF-8 çıktı).
- `core/` içindeki kod PySide6'ya bağımlı olmamalıdır; böylece test edilebilir kalır.
- Yeni bir işlem veya güvenlik kontrolü eklediğinizde `tests/` altına test ekleyin. Testler gerçek sistemi değiştirmemelidir; geçici klasör (`tmp_path`) ve sahte nesneler kullanın.

## Pull Request süreci

1. Depoyu fork'layın ve `main` dalından yeni bir dal açın: `feature/otomatik-bakim`, `fix/disk-siralama` gibi.
2. Değişikliğinizi yapın, testleri çalıştırın.
3. `CHANGELOG.md` dosyasında "Yayınlanmamış" başlığı altına kısa bir satır ekleyin.
4. Pull Request açın ve şablondaki kontrol listesini doldurun.

GitHub Actions her Pull Request'te testleri Windows üzerinde otomatik çalıştırır.

## Hata bildirme

Issue açarken şunları yazın: Windows sürümü, WinCare Manager sürümü, ne yaptığınız, ne beklediğiniz ve ne olduğu. Günlük dosyası `%LOCALAPPDATA%\WinCareManager\logs\wincare.log` konumundadır. Paylaşmadan önce içinde kişisel bilgi olup olmadığını kontrol edin.

Güvenlik açıkları için [SECURITY.md](SECURITY.md) dosyasına bakın.

---

## English summary

Contributions are welcome. Please open an issue before large changes. Set up with `scripts\setup_windows.ps1` and run `python -m pytest`. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) first.

Non-negotiable rules:
- Every system change goes through `OperationEngine` and supports dry run.
- Back up before reversible changes.
- No permanent deletion, no registry "cleaner", no network access, telemetry or external services.
- All UI text goes into both locale files.

Add tests for new operations and update `CHANGELOG.md`.
