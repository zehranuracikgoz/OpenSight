Language: [🇬🇧 English](#english) · [🇹🇷 Türkçe](#türkçe)

Live demo: [open-sight-theta.vercel.app](https://open-sight-theta.vercel.app/)

<a name="english"></a>

# OpenSight — Unified Performance & Behavioral Anomaly Detection for Open Banking APIs

OpenSight is a full-stack observability platform for Open Banking API traffic. It detects performance anomalies (latency spikes) with a rolling z-score and behavioral anomalies (clients acting unusually) with Isolation Forest, all from the same traffic stream. Its key contribution is a correlation layer: when both signals fire for the same client in the same time window, they are merged into a single correlated event, because a performance drop can be a side effect of an attack. Built with an ASP.NET Core backend, a Python analysis service and a React dashboard, developed as an internship project.

```

## Technologies

* C#, ASP.NET Core, Entity Framework Core, PostgreSQL
* Python, FastAPI, scikit-learn — rolling z-score and Isolation Forest
* RabbitMQ — asynchronous, fire-and-forget traffic pipeline
* Redis — hot-path store for live metrics and per-client feature windows
* React, TypeScript, Vite, Recharts — dashboard
* Ollama (optional) — local LLM for human-readable alert explanations
* xUnit, pytest, Vitest
* GitHub Actions — CI
* Docker, Vercel, Render, Supabase, Upstash, CloudAMQP

## Features

* Traffic simulator with three behavior profiles: normal, heavy and suspicious
* Mock Open Banking API that publishes every request to RabbitMQ without blocking its own response
* Real-time performance anomaly detection with a rolling z-score over Redis windows
* Behavioral anomaly detection with Isolation Forest on per-client feature vectors
* Correlation layer that merges performance and behavioral alerts for the same client within a 30-minute window
* Cold-start strategy: 90 seconds of normal-only traffic to train the model before anomalous profiles start
* Optional Ollama explanations with a 3-second timeout and a rule-based fallback template
* Dashboard with alert feed, correlated event detail panel and threshold configuration
* Keep-alive pings so the free-tier cloud services stay awake

## The Process

The project started with a mock Open Banking API whose endpoints publish each request to RabbitMQ in a fire-and-forget way, so the analysis side can never slow down the bank API. A Python simulator generates normal, heavy and suspicious traffic. The analysis service consumes the queue, keeps recent requests in Redis, computes rolling z-scores for latency, and extracts per-client features for Isolation Forest. Since Isolation Forest must be trained before it can score, the simulator sends only normal traffic at startup; once the baseline is collected the model is fitted and live detection begins. The correlation layer then checks both alert streams per client and stores alerts and correlated events in PostgreSQL. When Ollama is available it turns raw scores into readable explanations; otherwise the system falls back to a template, so detection never depends on the LLM. The dashboard uses a warm cream-and-amber theme with monospace numbers for a calm, data-focused look. CI builds and tests the backend, analysis service and frontend on every push.

## Installation

```bash
# Full stack with Docker (API, analysis service, PostgreSQL, Redis, RabbitMQ, frontend)
docker compose up -d

# Apply the database schema once (the API does not migrate on startup; repeat after `docker compose down -v`)
cd backend/src/OpenSight.Api
dotnet user-secrets set "ConnectionStrings:OpenSightDb" "Host=localhost;Port=5432;Database=OpenSightDb;Username=postgres;Password=<POSTGRES_PASSWORD from docker-compose.yml>"
cd ../..
dotnet ef database update --project src/OpenSight.Infrastructure --startup-project src/OpenSight.Api
cd ..

# Optional: include Ollama, then pull the model
docker compose --profile ollama up -d
docker compose exec ollama ollama pull llama3.2:1b
```

Dashboard: `http://localhost:8090`

```bash
# Backend (needs PostgreSQL and RabbitMQ, e.g. `docker compose up -d postgres rabbitmq`, and the connection string above)
cd backend/src/OpenSight.Api
dotnet run
```

```bash
# Analysis service (needs Redis, RabbitMQ and the backend)
cd analysis-service
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8001
```

```bash
# Traffic simulator (targets http://localhost:8080; the compose stack does not include it)
cd simulator
pip install -r requirements.txt
python traffic_simulator.py
```

```bash
# Frontend
cd frontend
npm install
# optional: cp .env.example .env.local  (VITE_API_URL, VITE_ANALYSIS_SERVICE_URL; defaults are localhost:8080 / localhost:8001)

npm run dev
```

## Tests

```bash
dotnet test
```

```bash
cd analysis-service
python -m pytest tests/ -v
# without Docker: python -m pytest tests/ -v --ignore=tests/test_integration_pipeline.py
```

```bash
cd frontend
npm test
```

<a name="türkçe"></a>

# OpenSight — Açık Bankacılık API'leri için Bütünleşik Performans ve Davranışsal Anomali Tespiti

OpenSight, Açık Bankacılık API trafiği için geliştirilmiş full-stack bir gözlemlenebilirlik platformudur. Aynı trafik akışı üzerinden performans anomalilerini (gecikme artışları) rolling z-score ile, davranışsal anomalileri (olağandışı davranan istemciler) Isolation Forest ile tespit eder. Temel katkısı korelasyon katmanıdır: iki sinyal aynı istemci için aynı zaman penceresinde tetiklendiğinde tek bir korelasyonlu olayda birleştirilir, çünkü bir performans düşüşü bir saldırının yan etkisi olabilir. ASP.NET Core backend, Python analiz servisi ve React dashboard'dan oluşur; staj projesi olarak geliştirilmiştir.

```

## Teknolojiler

* C#, ASP.NET Core, Entity Framework Core, PostgreSQL
* Python, FastAPI, scikit-learn — rolling z-score ve Isolation Forest
* RabbitMQ — asenkron, fire-and-forget trafik akışı
* Redis — canlı metrikler ve istemci bazlı özellik pencereleri için sıcak veri deposu
* React, TypeScript, Vite, Recharts — dashboard
* Ollama (opsiyonel) — insan-okunur alert açıklamaları için yerel LLM
* xUnit, pytest, Vitest
* GitHub Actions — CI
* Docker, Vercel, Render, Supabase, Upstash, CloudAMQP

## Özellikler

* Normal, yoğun ve şüpheli olmak üzere üç davranış profili üreten trafik simülatörü
* Her isteği kendi yanıtını bloklamadan RabbitMQ'ya yayınlayan mock Open Banking API
* Redis pencereleri üzerinde rolling z-score ile gerçek zamanlı performans anomalisi tespiti
* İstemci bazlı özellik vektörleri üzerinde Isolation Forest ile davranışsal anomali tespiti
* Aynı istemciye ait performans ve davranışsal alertleri 30 dakikalık pencerede birleştiren korelasyon katmanı
* Cold start stratejisi: anomalili profiller başlamadan önce modeli eğitmek için 90 saniyelik yalnızca normal trafik
* 3 saniyelik timeout ve kural tabanlı şablon fallback'i ile opsiyonel Ollama açıklamaları
* Alert akışı, korelasyonlu olay detay paneli ve eşik yapılandırması içeren dashboard
* Ücretsiz katmandaki bulut servislerinin uykuya girmemesi için keep-alive ping'leri

## Süreç

Proje, her isteği fire-and-forget şekilde RabbitMQ'ya yayınlayan mock bir Open Banking API ile başladı; böylece analiz tarafı banka API'sini hiçbir zaman yavaşlatamaz. Python simülatörü normal, yoğun ve şüpheli trafik üretir. Analiz servisi kuyruğu tüketir, son istekleri Redis'te tutar, gecikme için rolling z-score hesaplar ve Isolation Forest için istemci bazlı özellikler çıkarır. Isolation Forest skorlamadan önce eğitilmesi gerektiğinden simülatör başlangıçta yalnızca normal trafik gönderir; baseline toplandıktan sonra model eğitilir ve canlı tespit başlar. Korelasyon katmanı her istemci için iki alert akışını karşılaştırır, alertleri ve korelasyonlu olayları PostgreSQL'e yazar. Ollama erişilebilir olduğunda ham skorları okunabilir açıklamalara çevirir; olmadığında sistem şablon metne düşer, yani tespit hiçbir zaman LLM'e bağlı değildir. Dashboard, sakin ve veri odaklı bir görünüm için sıcak krem-amber bir tema ve monospace sayılar kullanır. CI, her push'ta backend, analiz servisi ve frontend'i derleyip test eder.

## Kurulum

```bash
# Docker ile tüm sistem (API, analiz servisi, PostgreSQL, Redis, RabbitMQ, frontend)
docker compose up -d

# Veritabanı şemasını bir kez uygulayın (API açılışta migration çalıştırmaz; `docker compose down -v` sonrası tekrarlayın)
cd backend/src/OpenSight.Api
dotnet user-secrets set "ConnectionStrings:OpenSightDb" "Host=localhost;Port=5432;Database=OpenSightDb;Username=postgres;Password=<docker-compose.yml'deki POSTGRES_PASSWORD>"
cd ../..
dotnet ef database update --project src/OpenSight.Infrastructure --startup-project src/OpenSight.Api
cd ..

# Opsiyonel: Ollama ile birlikte, ardından modeli indirin
docker compose --profile ollama up -d
docker compose exec ollama ollama pull llama3.2:1b
```

Dashboard: `http://localhost:8090`

```bash
# Backend (PostgreSQL ve RabbitMQ gerekir, örn. `docker compose up -d postgres rabbitmq`, ve yukarıdaki connection string)
cd backend/src/OpenSight.Api
dotnet run
```

```bash
# Analiz servisi (Redis, RabbitMQ ve backend gerekir)
cd analysis-service
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8001
```

```bash
# Trafik simülatörü (http://localhost:8080 adresini hedefler; compose sistemine dahil değildir)
cd simulator
pip install -r requirements.txt
python traffic_simulator.py
```

```bash
# Frontend
cd frontend
npm install
# opsiyonel: cp .env.example .env.local  (VITE_API_URL, VITE_ANALYSIS_SERVICE_URL; varsayılanlar localhost:8080 / localhost:8001)

npm run dev
```

## Testler

```bash
dotnet test
```

```bash
cd analysis-service
python -m pytest tests/ -v
# Docker olmadan: python -m pytest tests/ -v --ignore=tests/test_integration_pipeline.py
```

```bash
cd frontend
npm test
```