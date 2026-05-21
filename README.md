<div align="center">
  <h1>RepoHub</h1>
  <p><strong>Discover top GitHub repositories, organized by category.</strong></p>
  <p>
    <img src="https://img.shields.io/badge/repos-405+-brightgreen" alt="405+ repos"/>
    <img src="https://img.shields.io/badge/categories-9-blue" alt="9 categories"/>
    <img src="https://img.shields.io/badge/style-dark-6c5ce7" alt="Dark theme"/>
  </p>
</div>

---

RepoHub, GitHub'daki en popüler repoları kategorilere ayırarak keşfetmenizi sağlayan bir web sitesidir. Sade ve koyu temalı arayüzüyle ihtiyacınız olan projeyi hızla bulmanız hedeflenmiştir.

## Kategoriler

| Kategori | Odağı |
|----------|-------|
| **LLM & Language** | Büyük dil modelleri, NLP, transformerlar |
| **Computer Vision** | Nesne tespiti, görüntü işleme, üretim |
| **Audio & Speech** | Metin-konuşma, ses tanıma |
| **Dev Tools** | CLI araçları, geliştirici araçları |
| **Frameworks** | Derin öğrenme, makine öğrenmesi çatıları |
| **MLOps & Infra** | DevOps, monitoring, Kubernetes |
| **Web Dev** | React, Vue, frontend |
| **Databases** | SQL, NoSQL, veri depoları |
| **Creative & Design** | Tasarım sistemleri, görselleştirme, yaratıcı kodlama |

Her kategoride GitHub'da en çok yıldız alan repo'lar listelenir. Veri 3 saatte bir yenilenir.

## Kullanım

Siteye Tailscale üzerinden erişilir:

```
http://fun-serv:8080
```

Soldaki kategorilerden birine tıklayarak ilgili repoları görebilir, her repo için GitHub sayfasına doğrudan bağlantıya ulaşabilirsiniz. Chart.js grafikleriyle dillerin dağılımı ve repo istatistikleri görselleştirilir.

## Teknik Altyapı

| Bileşen | Açıklama |
|---------|----------|
| **Backend** | Python — GitHub Search API entegrasyonu |
| **Depolama** | SQLite (WAL modu) |
| **Frontend** | Vanilla HTML/CSS/JS, Chart.js, Geist font |
| **Güncelleme** | 3 saatte bir otomatik (systemd timer) |
| **Barındırma** | Self-hosted, Tailscale üzerinden erişim |

---

<div align="center">
  <sub>
    <a href="https://github.com/samedsemihs/repohub">GitHub</a>
  </sub>
</div>
