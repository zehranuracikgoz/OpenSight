-- bu dosya 'dotnet ef migrations script' ile üretildi (PostgreSQL)
-- şema değişiklikleri Domain entity'leri + yeni migration'lar üzerinden yapılmalı
CREATE TABLE IF NOT EXISTS "__EFMigrationsHistory" (
    "MigrationId" character varying(150) NOT NULL,
    "ProductVersion" character varying(32) NOT NULL,
    CONSTRAINT "PK___EFMigrationsHistory" PRIMARY KEY ("MigrationId")
);

START TRANSACTION;


DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260916150716_InitialCreate') THEN
    CREATE TABLE "Client" (
        "ClientId" text NOT NULL,
        "FirstSeen" timestamp with time zone NOT NULL,
        "LastSeen" timestamp with time zone NOT NULL,
        CONSTRAINT "PK_Client" PRIMARY KEY ("ClientId")
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260916150716_InitialCreate') THEN
    CREATE TABLE "Alert" (
        "AlertId" text NOT NULL,
        "ClientId" text NOT NULL,
        "Type" character varying(32) NOT NULL,
        "Severity" character varying(16) NOT NULL,
        "CreatedAt" timestamp with time zone NOT NULL,
        "Description" text,
        "ZScore" double precision,
        "AnomalyScore" double precision,
        "RequestRatePct" double precision,
        "RelatedEndpoint" text,
        "Acknowledged" boolean NOT NULL,
        "Silenced" boolean NOT NULL,
        CONSTRAINT "PK_Alert" PRIMARY KEY ("AlertId"),
        CONSTRAINT "FK_Alert_Client_ClientId" FOREIGN KEY ("ClientId") REFERENCES "Client" ("ClientId") ON DELETE CASCADE
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260916150716_InitialCreate') THEN
    CREATE TABLE "CorrelationEvent" (
        "CorrelationId" text NOT NULL,
        "PerformanceAlertId" text NOT NULL,
        "BehavioralAlertId" text NOT NULL,
        "DetectedAt" timestamp with time zone NOT NULL,
        CONSTRAINT "PK_CorrelationEvent" PRIMARY KEY ("CorrelationId"),
        CONSTRAINT "FK_CorrelationEvent_Alert_BehavioralAlertId" FOREIGN KEY ("BehavioralAlertId") REFERENCES "Alert" ("AlertId") ON DELETE RESTRICT,
        CONSTRAINT "FK_CorrelationEvent_Alert_PerformanceAlertId" FOREIGN KEY ("PerformanceAlertId") REFERENCES "Alert" ("AlertId") ON DELETE RESTRICT
    );
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260916150716_InitialCreate') THEN
    CREATE INDEX "IX_Alert_ClientId_CreatedAt" ON "Alert" ("ClientId", "CreatedAt");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260916150716_InitialCreate') THEN
    CREATE INDEX "IX_CorrelationEvent_BehavioralAlertId" ON "CorrelationEvent" ("BehavioralAlertId");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260916150716_InitialCreate') THEN
    CREATE INDEX "IX_CorrelationEvent_PerformanceAlertId" ON "CorrelationEvent" ("PerformanceAlertId");
    END IF;
END $EF$;

DO $EF$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM "__EFMigrationsHistory" WHERE "MigrationId" = '20260916150716_InitialCreate') THEN
    INSERT INTO "__EFMigrationsHistory" ("MigrationId", "ProductVersion")
    VALUES ('20260916150716_InitialCreate', '8.0.10');
    END IF;
END $EF$;
COMMIT;