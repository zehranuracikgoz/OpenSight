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

- Traffic simulator with normal, heavy and suspicious client profiles
- Mock Open Banking API with load-dependent latency, publishing every request to RabbitMQ without waiting
- Performance anomaly detection with a per-client rolling z-score on latency
- Behavioral anomaly detection with Isolation Forest on request rate, top-endpoint share and average latency
- Correlation layer that merges both alert types for the same client into a single event
- One-click live demo with a scorecard against the simulator's ground-truth labels
- Dashboard with a real-time latency chart, alert explanations and light/dark themes
- Evaluation with precision, recall and F1, plus validation on the Kaggle Credit Card Fraud dataset

---

## The Process

The mock API publishes every request to RabbitMQ without waiting, so the analysis side can never slow down the bank API. The analysis service keeps recent requests in Redis, runs a rolling z-score on latency and an Isolation Forest trained on legitimate traffic, and merges simultaneous alerts for the same client into a correlated event. Since no real bank data was available, a simulator generates labeled traffic; on a 30-minute run the behavioral detector reached 0.86 recall and 0.72 F1, and Isolation Forest was also validated on the Kaggle Credit Card Fraud dataset with a PR-AUC of about 0.17. On the live site, a one-click demo wakes the free-tier services, runs a five-minute scenario and shows a scorecard.

---

## Installation

```bash
# Full stack (API, analysis service, simulator, PostgreSQL, Redis, RabbitMQ, frontend)
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
# env: SIMULATOR_RATE_SCALE, SIMULATOR_DURATION_SECONDS, PORT (the compose simulator uses 10000)

python traffic_simulator.py
```

```bash
# Frontend (development)
cd frontend
npm install
# .env.local: VITE_API_URL, VITE_ANALYSIS_SERVICE_URL, VITE_SIMULATOR_URL

npm run dev
```

```bash
# Evaluation
cd evaluation
pip install -r requirements.txt

python evaluate.py --ground-truth-path ../simulator/ground_truth.log
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

- Normal, yoğun ve şüpheli istemci profilleri üreten trafik simülatörü
- Gecikmesi yükle artan ve her isteği beklemeden RabbitMQ'ya yayınlayan mock Open Banking API
- İstemci bazlı, gecikme üzerinde rolling z-score ile performans anomalisi tespiti
- İstek oranı, en sık endpoint payı ve ortalama gecikme üzerinde Isolation Forest ile davranışsal anomali tespiti
- Aynı istemcideki iki alarm türünü tek bir olayda birleştiren korelasyon katmanı
- Simülatörün gerçek etiketlerine göre karne gösteren tek tıklık canlı demo
- Gerçek zamanlı gecikme grafiği, alarm açıklamaları ve açık/koyu tema içeren dashboard
- Precision, recall ve F1 ile değerlendirme; ayrıca Kaggle Credit Card Fraud veri setinde doğrulama

---

## Süreç

Mock API her isteği beklemeden RabbitMQ'ya yayınlar; böylece analiz tarafı banka API'sini hiçbir zaman yavaşlatamaz. Analiz servisi son istekleri Redis'te tutar, gecikme üzerinde rolling z-score ve meşru trafikle eğitilmiş bir Isolation Forest çalıştırır, aynı istemcide eş zamanlı oluşan alarmları korelasyonlu bir olayda birleştirir. Gerçek banka verisi olmadığı için bir simülatör etiketli trafik üretir; 30 dakikalık bir koşuda davranışsal dedektör 0,86 recall ve 0,72 F1'e ulaştı, Isolation Forest ayrıca Kaggle Credit Card Fraud veri setinde yaklaşık 0,17 PR-AUC ile doğrulandı. Canlı sitede tek tıklık bir demo ücretsiz katmandaki servisleri uyandırır, beş dakikalık bir senaryo çalıştırır ve bir karne gösterir.

---

## Kurulum

```bash
# Tüm sistem (API, analiz servisi, simülatör, PostgreSQL, Redis, RabbitMQ, frontend)
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
# env: SIMULATOR_RATE_SCALE, SIMULATOR_DURATION_SECONDS, PORT (compose'daki simülatör 10000'i kullanıyor)

python traffic_simulator.py
```

```bash
# Frontend (geliştirme)
cd frontend
npm install
# .env.local: VITE_API_URL, VITE_ANALYSIS_SERVICE_URL, VITE_SIMULATOR_URL

npm run dev
```

```bash
# Değerlendirme
cd evaluation
pip install -r requirements.txt

python evaluate.py --ground-truth-path ../simulator/ground_truth.log
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
