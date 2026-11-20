# WinCare Manager

**Sürüm:** 0.2.0 · [English](README_EN.md)
**Platform:** Windows 10/11 (64 bit)
**Arayüz:** Türkçe ve English
**Çalışma şekli:** Yerel ve çevrimdışı masaüstü uygulaması

WinCare Manager, Windows için bir bakım ve yönetim aracıdır. Sistemi analiz eder, güvenli bakım işlemleri yapar ve yaptığı her değişikliği kayıt altına alarak geri alınabilir tutar.

## Modüller

| Menü | Ne yapar | Sistemi değiştirir mi? |
|---|---|---|
| Genel Bakış | CPU, bellek ve disk göstergeleri, sağlık özeti, sistem bilgisi | Hayır |
| Gereksiz Dosya Temizliği | Geçici dosyaları, çökme dökümlerini ve hata raporlarını listeler; seçilenleri **Geri Dönüşüm Kutusu'na** taşır | Evet, onayla |
| Başlangıç Programları | Başlangıç girdilerini etkinleştirir veya devre dışı bırakır (silmez) | Evet, onay ve yedekle |
| İşlem Yöneticisi | Çalışan işlemleri, CPU ve bellek kullanımını, dosya yollarını gösterir | Hayır |
| Kayıt Defteri | Anahtarları gösterir ve yedekler | Hayır (yalnızca yedek alır) |
| Windows Hizmetleri | Hizmet durumu ve başlangıç türü | Hayır |
| Disk Yönetimi | Sürücü doluluğu, fiziksel disk sağlığı | Hayır |
| Yedekleme ve Geri Yükleme | `.reg` yedeklerini doğrular ve geri yükler | Evet, onay ve yedekle |
| Sistem Tanılama | Sağlık kontrolleri, Windows olay günlüğü | Hayır |
| Otomatik Bakım | **İsteğe bağlı, varsayılan olarak kapalı.** Açılırsa günlük veya haftalık analiz yapar ve sonucu bir sonraki açılışta bildirir | Hayır (yalnızca analiz) |
| İşlem Geçmişi | Bütün işlemler (SQLite) ve uygulama günlüğü | Hayır |

## Güvenlik ilkeleri

1. **Deneme modu varsayılan olarak açıktır.** İşlemler yalnızca planlanır ve İşlem Geçmişi'ne yazılır. Gerçekten uygulamak için Ayarlar'dan kapatın.
2. **Arayüz sisteme doğrudan dokunmaz.** Her değişiklik işlem motorundan geçer: yetki kontrolü, güvenlik doğrulaması, yedek, uygulama ve kayıt.
3. **Kalıcı silme yoktur.** Dosyalar Geri Dönüşüm Kutusu'na taşınır.
4. **Windows klasörleri, Program Files, sembolik bağlantılar ve junction'lar** temizlik kapsamı dışındadır ve uygulama anında yeniden kontrol edilir.
5. **Kayıt defterinde "temizleyici" yoktur.** Değer silinmez; yalnızca başlangıç durumu değiştirilir, değişiklikten önce de yedek alınır.
6. **Yedekler SHA-256 ile doğrulanır.** Bozuk bir yedek geri yüklenmez.
7. **Yönetici yetkisi** sürekli istenmez. Gerektiğinde Ayarlar'dan "Yönetici olarak yeniden başlat" seçilir.
8. **Yarım kalan işlemler** bir sonraki açılışta tespit edilip raporlanır.

## Kurulum (kullanıcılar için)

[Releases sayfasından](https://github.com/sametbesni/WinCare-Manager/releases/latest) `WinCareManager-Setup-<sürüm>.exe` dosyasını indirip çalıştırın. Kurulum istemiyorsanız `portable.zip` dosyasını bir klasöre çıkarıp kullanabilirsiniz.

- Varsayılan olarak yalnızca sizin için ve **yönetici yetkisi istemeden** kurulur. İsterseniz "tüm kullanıcılar için" seçeneğini seçebilirsiniz.
- **Masaüstü kısayolu** varsayılan olarak oluşturulur; istemezseniz kurulumda işareti kaldırın. Başlat menüsüne de eklenir.
- Program "Uygulamalar" listesinde görünür ve oradan kaldırılabilir.

Kurulum dosyası henüz kod imzalama sertifikasıyla imzalanmadığı için Windows SmartScreen "Tanınmayan uygulama" uyarısı gösterebilir. "Ek bilgi → Yine de çalıştır" ile devam edilir.

## Geliştirme ortamı

PowerShell'i proje klasöründe açın:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\setup_windows.ps1
```

Ardından `run_windows.bat` dosyasını çift tıklayın.

### Elle kurulum

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python main.py
```

## Testler

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## EXE oluşturma

```powershell
.\scripts\build_windows.ps1
```

Betik önce testleri çalıştırır. Testlerden biri başarısız olursa paketleme yapılmaz. Çıktı:

```text
dist\WinCare Manager\WinCare Manager.exe
dist\WinCare Manager\SHA256SUMS.txt
```

### Kurulum dosyası

[Inno Setup 6](https://jrsoftware.org/isinfo.php) gerekir (`winget install --id JRSoftware.InnoSetup -e`).

```powershell
.\scripts\build_installer.ps1
```

Çıktı: `dist\installer\WinCareManager-Setup-<sürüm>.exe`. Kurulum betiği `installer\WinCareManager.iss` dosyasındadır.

Kurulumsuz kullanım için `dist\WinCare Manager` klasörünün **tamamı** birlikte dağıtılmalıdır, çünkü EXE `_internal` klasörüne ihtiyaç duyar. Python kurulu olmayan bir Windows'ta da çalışır. EXE henüz kod imzalama sertifikasıyla imzalanmadığı için Windows SmartScreen uyarı gösterebilir.

## Veriler

```text
%LOCALAPPDATA%\WinCareManager\
    settings.json        Ayarlar
    history.db           İşlem geçmişi (SQLite)
    backups\             Kayıt defteri yedekleri (.reg + .json manifest)
    logs\wincare.log     Uygulama günlüğü
```

## Proje yapısı

```text
main.py              Giriş noktası
app/                 Ayarlar, dil, günlük, yetki, ortak bağlam
core/                Sistem modülleri, işlem motoru (engine.py), yedekleme (backup.py)
database/            İşlem geçmişi (SQLite)
locales/             tr_TR.json, en_US.json
ui/                  PySide6 ana pencere, sayfalar, tema
tests/               Otomatik testler
scripts/             Kurulum, EXE paketleme, ikon üretimi
assets/              Uygulama ikonu (16–256 px, çok boyutlu)
installer/           Inno Setup kurulum betiği
docs/                Geliştirici belgeleri (ARCHITECTURE.md)
.github/             Otomatik testler (Actions) ve Issue/PR şablonları
```

## Otomatik Bakım

- Varsayılan olarak **kapalıdır**. Otomatik Bakım sayfasından açılır; sıklık (her gün / her hafta), gün ve saat seçilir.
- Açıldığında Windows Görev Zamanlayıcı'ya `WinCareManager AutoMaintenance` adlı bir görev kaydedilir:
  - görev sizin hesabınızla ve **yönetici yetkisi olmadan** çalışır;
  - yalnızca oturumunuz açıkken ve bilgisayar prize takılıyken çalışır;
  - kaçırılan bir çalışma ilk fırsatta yapılır.
- Görev programı pencere açmadan `--maintenance` parametresiyle başlatır. Program **yalnızca analiz yapar**: dosya silmez, kayıt defterini veya ayarları değiştirmez.
- Rapor İşlem Geçmişi'ne yazılır ve uygulama bir sonraki açılışta bildirir. "Şimdi analiz et" düğmesiyle elle de çalıştırılabilir.
- Kapatmak için onay kutusunu kaldırıp "Uygula"ya basın; görev silinir.

## Programı kaldırma

WinCare Manager Windows'a hizmet veya sürücü eklemez.

**Kurulum dosyasıyla kurduysanız:** Windows Ayarlar → Uygulamalar → WinCare Manager → Kaldır. Bu işlem programı, masaüstü ve Başlat menüsü kısayollarını ve Otomatik Bakım görevini siler. Son adımda ayarlar, geçmiş ve yedeklerin de silinip silinmeyeceği sorulur; varsayılan cevap "Hayır"dır.

**Kurulumsuz (klasör) sürümü kullanıyorsanız:**

1. **Ayarlar → Programı kaldırma → "Kaldırmaya hazırla"** düğmesine basın. Program, sisteme eklediği tek kalıcı öğe olan Otomatik Bakım görevini (varsa) siler.
2. Programı kapatın.
3. Program klasörünü (`WinCare Manager.exe` dosyasının bulunduğu klasör) silin.
4. Ayarları, geçmişi ve yedekleri de silmek isterseniz `%LOCALAPPDATA%\WinCareManager\` klasörünü silin.

Bilmeniz gerekenler:
- Programla yaptığınız değişiklikler (ör. devre dışı bıraktığınız başlangıç programları) kaldırınca **geri alınmaz**; bunlar sizin tercihlerinizdir. Geri almak istediklerinizi kaldırmadan önce Başlangıç Programları ya da Yedekleme ve Geri Yükleme sayfasından geri alın.
- Geri Dönüşüm Kutusu'na taşınan dosyalar orada kalır.

## Gizlilik

Uygulamanın ağ erişimi, telemetrisi, hesap sistemi ve dış servis bağlantısı yoktur. Tüm veriler bu bilgisayarda kalır.

## Sonraki adımlar

- Hizmetleri kontrollü biçimde başlatma ve durdurma
- İşlemlerde dijital imza (imzalı/imzasız) bilgisi
- Kod imzalama (SmartScreen uyarısını kaldırmak için)

## Katkıda bulunma

Katkılara açığız. Başlamadan önce [CONTRIBUTING.md](CONTRIBUTING.md) ve [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) dosyalarını okuyun. Güvenlik açıkları için [SECURITY.md](SECURITY.md).

## Lisans

[MIT](LICENSE)
