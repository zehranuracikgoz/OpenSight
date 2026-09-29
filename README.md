**Language:** [🇬🇧 English](#english) · [🇹🇷 Türkçe](#türkçe)

**Live demo:** [open-sight-theta.vercel.app](https://open-sight-theta.vercel.app)
---

<a name="english"></a>

# OpenSight — Performance & Behavioral Anomaly Detection for Open Banking APIs

OpenSight is a full-stack observability platform for Open Banking API traffic. It detects performance anomalies (latency spikes) with a rolling z-score and behavioral anomalies (clients acting unusually) with Isolation Forest, both from the same traffic stream. When both signals fire for the same client within the same time window, a correlation layer merges them into a single event, since a performance drop can be a side effect of an attack. Built with an ASP.NET Core backend, a Python analysis service and a React dashboard, developed as an internship project and deployed on Vercel and Render.

---

## Technologies

- **C#, ASP.NET Core, Entity Framework Core, PostgreSQL**
- **Python, FastAPI, scikit-learn** — rolling z-score and Isolation Forest
- **RabbitMQ** — asynchronous, fire-and-forget traffic pipeline
- **Redis** — live metric windows and model baseline
- **React, TypeScript, Vite, Recharts** — dashboard
- **Ollama** (optional) — local LLM for alert explanations
- **xUnit, pytest, Vitest**
- **GitHub Actions** — CI
- **Docker, Vercel, Render, Supabase, Upstash, CloudAMQP**

---

## Features

- Traffic simulator with normal, heavy and suspicious client profiles; heavy clients alternate between calm and burst periods
- Mock Open Banking API whose latency grows with each client's load
- Real-time performance anomaly detection with a per-client rolling z-score on latency
- Behavioral anomaly detection with Isolation Forest on three per-client features: request rate, top-endpoint share and average latency
- Correlation layer that merges performance and behavioral alerts for the same client within a 30-minute window
- Model baseline built from legitimate traffic and persisted in Redis, so restarts do not require a new cold start
- Readiness signal: suspicious traffic starts only after the model reports it is trained
- 5-minute alert cooldown per client and alert type to prevent alert floods
- Optional Ollama explanations with a 3-second timeout and a rule-based fallback template
- Dashboard with alert feed, correlated event detail panel and threshold configuration
- Evaluation script that measures precision, recall and F1 against the simulator's ground-truth labels

---

## The Process

The project started with a mock Open Banking API whose endpoints publish each request to RabbitMQ in a fire-and-forget way, so the analysis side can never slow down the bank API. A Python simulator generates normal, heavy and suspicious traffic, and the mock API adds latency as a client's request rate rises, so heavy bursts produce real slowdowns. The analysis service consumes the queue, keeps recent requests in Redis and computes a rolling z-score on latency for each client. For behavioral detection, Isolation Forest is trained on a baseline sampled from legitimate (normal and heavy) traffic, so it learns that busy clients are not suspicious by themselves; what stands out is a client that is both fast and concentrated on a single endpoint. The correlation layer checks both alert streams per client and stores alerts and correlated events in PostgreSQL. On a 30-minute evaluation run, the behavioral detector reached 0.86 recall and 0.72 F1, and the performance detector caught 67% of heavy bursts with no false positives on heavy clients. The dashboard uses a warm cream-and-amber theme with monospace numbers for a calm, data-focused look.

---

## Installation

```bash
# Full stack (API, analysis service, PostgreSQL, Redis, RabbitMQ, frontend)
docker compose up -d

# Database migration
cd backend
dotnet ef database update --project src/OpenSight.Infrastructure --startup-project src/OpenSight.Api
```

Dashboard: `http://localhost:8090`

```bash
# Traffic simulator
cd simulator
pip install -r requirements.txt
# .env: SIMULATOR_RATE_SCALE, SIMULATOR_DURATION_SECONDS

python traffic_simulator.py
```

```bash
# Frontend (development)
cd frontend
npm install
# .env.local: VITE_API_URL, VITE_ANALYSIS_SERVICE_URL

npm run dev
```

```bash
# Evaluation
cd evaluation
pip install -r requirements.txt

python evaluate.py
```

### Tests

```bash
cd backend
dotnet test
```

```bash
python -m pytest analysis-service/tests simulator/tests evaluation/tests -v
```

```bash
cd frontend
npm test
```

---

---

<a name="türkçe"></a>

# OpenSight — Açık Bankacılık API'leri için Performans ve Davranışsal Anomali Tespiti

OpenSight, Açık Bankacılık API trafiği için geliştirilmiş full-stack bir gözlemlenebilirlik platformudur. Aynı trafik akışı üzerinden performans anomalilerini (gecikme artışları) rolling z-score ile, davranışsal anomalileri (olağandışı davranan istemciler) Isolation Forest ile tespit eder. İki sinyal aynı istemci için aynı zaman penceresinde tetiklendiğinde korelasyon katmanı bunları tek bir olayda birleştirir, çünkü bir performans düşüşü bir saldırının yan etkisi olabilir. ASP.NET Core backend, Python analiz servisi ve React dashboard'dan oluşur; staj projesi olarak geliştirilmiştir ve Vercel ile Render üzerinde yayındadır.

---

## Teknolojiler

- **C#, ASP.NET Core, Entity Framework Core, PostgreSQL**
- **Python, FastAPI, scikit-learn** — rolling z-score ve Isolation Forest
- **RabbitMQ** — asenkron, fire-and-forget trafik akışı
- **Redis** — canlı metrik pencereleri ve model baseline'ı
- **React, TypeScript, Vite, Recharts** — dashboard
- **Ollama** (opsiyonel) — alert açıklamaları için yerel LLM
- **xUnit, pytest, Vitest**
- **GitHub Actions** — CI
- **Docker, Vercel, Render, Supabase, Upstash, CloudAMQP**

---

## Özellikler

- Normal, yoğun ve şüpheli istemci profilleri üreten trafik simülatörü; yoğun istemciler sakin ve patlama dönemleri arasında dalgalanır
- Gecikmesi her istemcinin yüküyle artan mock Open Banking API
- İstemci bazlı, gecikme üzerinde rolling z-score ile gerçek zamanlı performans anomalisi tespiti
- Üç istemci bazlı feature üzerinde Isolation Forest ile davranışsal anomali tespiti: istek oranı, en sık endpoint payı ve ortalama gecikme
- Aynı istemciye ait performans ve davranışsal alertleri 30 dakikalık pencerede birleştiren korelasyon katmanı
- Meşru trafikten oluşturulan ve Redis'te saklanan model baseline'ı; servis yeniden başladığında yeni bir cold start gerekmez
- Hazır olma sinyali: şüpheli trafik ancak model eğitildiğini bildirdikten sonra başlar
- Alert selini önlemek için istemci ve alert türü başına 5 dakikalık cooldown
- 3 saniyelik timeout ve kural tabanlı şablon fallback'i ile opsiyonel Ollama açıklamaları
- Alert akışı, korelasyonlu olay detay paneli ve eşik yapılandırması içeren dashboard
- Simülatörün ground-truth etiketlerine göre precision, recall ve F1 ölçen değerlendirme betiği

---

## Süreç

Proje, her isteği fire-and-forget şekilde RabbitMQ'ya yayınlayan mock bir Open Banking API ile başladı; böylece analiz tarafı banka API'sini hiçbir zaman yavaşlatamaz. Python simülatörü normal, yoğun ve şüpheli trafik üretir; mock API ise bir istemcinin istek oranı arttıkça gecikme ekler, böylece yoğun patlamalar gerçek yavaşlamalara yol açar. Analiz servisi kuyruğu tüketir, son istekleri Redis'te tutar ve her istemci için gecikme üzerinde rolling z-score hesaplar. Davranışsal tespit için Isolation Forest, meşru (normal ve yoğun) trafikten örneklenen bir baseline üzerinde eğitilir; böylece yoğun bir istemcinin tek başına şüpheli olmadığını öğrenir. Öne çıkan, hem hızlı hem de tek bir endpoint'e yoğunlaşmış istemcidir. Korelasyon katmanı her istemci için iki alert akışını karşılaştırır, alertleri ve korelasyonlu olayları PostgreSQL'e yazar. 30 dakikalık bir değerlendirme koşusunda davranışsal dedektör 0,86 recall ve 0,72 F1'e ulaştı; performans dedektörü yoğun patlamaların %67'sini yakaladı ve yoğun istemcilerde hiç yanlış alarm üretmedi. Dashboard, sakin ve veri odaklı bir görünüm için sıcak krem-amber bir tema ve monospace sayılar kullanır.

---

## Kurulum

```bash
# Tüm sistem (API, analiz servisi, PostgreSQL, Redis, RabbitMQ, frontend)
docker compose up -d

# Veritabanı migration'ı
cd backend
dotnet ef database update --project src/OpenSight.Infrastructure --startup-project src/OpenSight.Api
```

Dashboard: `http://localhost:8090`

```bash
# Trafik simülatörü
cd simulator
pip install -r requirements.txt
# .env: SIMULATOR_RATE_SCALE, SIMULATOR_DURATION_SECONDS

python traffic_simulator.py
```

```bash
# Frontend (geliştirme)
cd frontend
npm install
# .env.local: VITE_API_URL, VITE_ANALYSIS_SERVICE_URL

npm run dev
```

```bash
# Değerlendirme
cd evaluation
pip install -r requirements.txt

python evaluate.py
```

### Testler

```bash
cd backend
dotnet test
```

```bash
python -m pytest analysis-service/tests simulator/tests evaluation/tests -v
```

```bash
cd frontend
npm test
```
