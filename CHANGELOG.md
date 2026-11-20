# Değişiklik Kaydı

## 0.3.0
- **İşlem Yöneticisi – dijital imza:** "İmza" ve "Yayıncı" sütunları eklendi.
  - Durumlar: Geçerli, İmzasız, Geçersiz, Güvenilmeyen.
  - Denetim Windows'un kendi doğrulamasıyla (`Get-AuthenticodeSignature`) yapılıyor; gömülü imzalar ve Windows'un katalog imzaları birlikte denetleniyor. Ücretsiz, ek program veya çevrimiçi servis gerekmiyor.
  - Arka planda küçük dosyalardan büyüğe doğru denetleniyor. Her dosya bir kez denetlenip önbellekte tutuluyor; dosya değişirse yeniden denetleniyor.
  - İmzasız ve sorunlu olanlar renkle işaretleniyor ve "Yalnızca imzasız ve sorunlu olanlar" filtresiyle listelenebiliyor.
- **Düzeltme:** Bilgisayarda PowerShell 7 kuruluysa Windows PowerShell yanlış modülü yüklemeye çalışıyordu. İmza denetimi, disk sağlığı ve olay günlüğü sorguları bu durumda sessizce boş dönüyordu.
- **Düzeltme (performans):** Tablolar tema etkinken her yenilemede bütün sütun genişliklerini satır satır yeniden ölçüyordu. İşlem Yöneticisi her 2 saniyede yenilendiği için pencere dakikalarca donabiliyordu. Artık sütunlar ilk doldurmada bir kez boyutlanıyor ve kullanıcının ayarladığı genişlik korunuyor. Yenileme süreleri:
  - İşlem Yöneticisi: 83 s → 0,02 s
  - Gereksiz Dosya Temizliği (1500 satır): 500 s'den fazla → 0,05 s
  - Windows Hizmetleri: 7 s → 0,01 s
- **Windows Hizmetleri:** Seçilen hizmet başlatılıp durdurulabiliyor. İşlem, işlem motoru üzerinden onay, yönetici yetkisi, deneme modu ve geçmiş kaydıyla yapılıyor. Güvenlik kuralları:
  - kritik Windows ve güvenlik hizmetleri (RPC, Defender, güvenlik duvarı, olay günlüğü, Windows Update vb.) durdurulamaz;
  - başka çalışan hizmetlerin bağlı olduğu hizmetler durdurulmaz;
  - devre dışı hizmetler başlatılmaz;
  - başlangıç türü hiçbir zaman değiştirilmez.
- Hizmetler tablosunda uzun adlar artık diğer sütunları ekran dışına itmiyor.

## 0.2.0

### Yayın sırasında eklenenler
- **Kurulum dosyası** (Inno Setup, `scripts/build_installer.ps1`):
  - varsayılan olarak yönetici yetkisi istemeden kurulur;
  - **masaüstü kısayolu** (varsayılan olarak işaretli) ve Başlat menüsü girdisi oluşturur;
  - Windows "Uygulamalar" listesine eklenir.
  - Kaldırırken Otomatik Bakım görevini siler ve kullanıcı verilerinin silinmesini sorar (varsayılan: hayır).
- Uygulama ikonu artık 9 boyut içeriyor (16–256 px); masaüstünde ve görev çubuğunda bulanık görünmüyor.
- **Otomatik Bakım** (yeni sayfa): isteğe bağlı ve **varsayılan olarak kapalı**. Açıldığında günlük veya haftalık bir Windows Görev Zamanlayıcı görevi kaydedilir. Görev yönetici yetkisi istemez ve yalnızca analiz yapar: sağlık kontrolleri, fiziksel disk sağlığı, gereksiz dosya boyutu, etkin başlangıç programı sayısı, hata olayları. Rapor İşlem Geçmişi'ne yazılır ve bir sonraki açılışta bildirilir. "Şimdi analiz et" ile elle de çalıştırılabilir.
- **Programı kaldırma:** Ayarlar'a "Kaldırmaya hazırla" eklendi. Otomatik bakım görevini siler ve kalan adımları gösterir. README'ye kaldırma bölümü eklendi.
- Açık kaynak hazırlığı: MIT lisansı, katkı rehberi, güvenlik politikası, mimari belgesi, GitHub Issue/PR şablonları ve Windows üzerinde otomatik test (GitHub Actions).
- Düzeltme: BOM ile kaydedilmiş `settings.json` (Not Defteri / PowerShell) okunamıyor ve ayarlar sessizce varsayılana dönüyordu.
- Düzeltme: Günlük ayarlanmadan önce bir hata oluşursa `wincare.log` hiç oluşmuyor, sonraki bütün kayıtlar kayboluyordu.
- `run_windows.bat` artık paketler eksikse hatayı gösterip bekliyor (önceden `pythonw` sessizce kapanıyordu).
- Ana README `README.md` oldu (Türkçe); İngilizcesi `README_EN.md`.
- Eski Tkinter taslağı (`python/`) kaldırıldı.

### Yeni
- **İşlem motoru ve güvenlik katmanı** (`core/engine.py`): yetki kontrolü → doğrulama → deneme modu → yedek → uygulama → kayıt. Arayüz sisteme doğrudan dokunmaz.
- **Deneme modu** varsayılan olarak açık. Değişiklikler yalnızca planlanır ve kaydedilir.
- **İşlem geçmişi** SQLite'ta tutuluyor. Her işlemin benzersiz bir kimliği var ve yarım kalan işlemler açılışta tespit ediliyor.
- **Gereksiz Dosya Temizliği:** Seçilen dosyalar Geri Dönüşüm Kutusu'na taşınıyor, kalıcı silme yok. Çökme dökümleri ve Windows hata raporları da analiz ediliyor. Her dosya uygulamadan hemen önce yeniden doğrulanıyor.
- **Başlangıç Programları:** Girdiler Görev Yöneticisi'nde olduğu gibi etkinleştirilip devre dışı bırakılabiliyor (`StartupApproved`). Değişiklikten önce yedek alınıyor. HKLM 32 bit girdileri de listeleniyor.
- **Kayıt Defteri:** Salt okunur görüntüleyici ve anahtar yedekleme.
- **Yedekleme ve Geri Yükleme:** `.reg` yedekleri SHA-256 ile doğrulanıyor. Geri yüklemeden önce mevcut durumun da yedeği alınıyor.
- **Windows Hizmetleri:** Salt okunur liste ve arama.
- **Disk Yönetimi:** Bütün sürücüler ve fiziksel disk sağlığı (Windows Storage API).
- **Sistem Tanılama:** Sağlık kontrolleri ve Windows olay günlüğü.
- **Genel Bakış:** Yay göstergeler, sağlık özeti, bilgisayar adı ve çekirdek bilgisi.
- İşlem Yöneticisi'ne arama ve dosya yolu sütunu eklendi.
- Ayarlara yeni seçenekler eklendi: deneme modu, temizlik yaşı, kullanıcı adı gösterimi ve isteğe bağlı UAC ile yönetici olarak yeniden başlatma.
- Uygulama ikonu eklendi.

### Düzeltmeler (0.1.0'daki hatalar)
- EXE açılışta çöküyordu, çünkü `theme.qss` pakete eklenmiyordu. Artık ekleniyor ve yolu `get_resource_path` ile çözülüyor.
- `build_windows.ps1` duruyordu, çünkü `pytest` kurulmuyordu. Artık `requirements-dev.txt` ile kuruluyor.
- Tablolarda sayısal sütunlar metin olarak sıralanıyordu. Artık sayı olarak sıralanıyor.
- Tarama ve işlem listesi arayüzü donduruyordu. Artık arka plan iş parçacığında çalışıyorlar.
- İşlem listesi her yenilendiğinde seçim ve kaydırma sıfırlanıyordu. Artık korunuyor.
- CPU ilk ölçümde %0 görünüyordu. İşlem başına CPU artık çekirdek sayısına göre hesaplanıyor; "System Idle Process" listeden çıkarıldı.

### Testler
- 8 olan test sayısı 25'e çıktı: işlem motoru, deneme modu, yetki engeli, yedek bütünlüğü, güvenlik doğrulaması, yarım kalan işlemler ve her çeviri anahtarının iki dil dosyasında da bulunması.

## 0.1.0
- İlk masaüstü sürümü: Genel Bakış, salt okunur işlem ve başlangıç listeleri, geçici dosya analizi, Türkçe/İngilizce arayüz, ayarlar ve günlük.
