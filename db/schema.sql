-- bu dosya 'dotnet ef migrations script' ile üretildi
-- şema değişiklikleri Domain entity'leri + yeni migration'lar üzerinden yapılmalı
IF OBJECT_ID(N'[__EFMigrationsHistory]') IS NULL
BEGIN
    CREATE TABLE [__EFMigrationsHistory] (
        [MigrationId] nvarchar(150) NOT NULL,
        [ProductVersion] nvarchar(32) NOT NULL,
        CONSTRAINT [PK___EFMigrationsHistory] PRIMARY KEY ([MigrationId])
    );
END;
GO

BEGIN TRANSACTION;
GO

CREATE TABLE [Client] (
    [ClientId] nvarchar(450) NOT NULL,
    [FirstSeen] datetime2 NOT NULL,
    [LastSeen] datetime2 NOT NULL,
    CONSTRAINT [PK_Client] PRIMARY KEY ([ClientId])
);
GO

CREATE TABLE [Alert] (
    [AlertId] nvarchar(450) NOT NULL,
    [ClientId] nvarchar(450) NOT NULL,
    [Type] nvarchar(32) NOT NULL,
    [Severity] nvarchar(16) NOT NULL,
    [CreatedAt] datetime2 NOT NULL,
    [Description] nvarchar(max) NULL,
    [ZScore] float NULL,
    [AnomalyScore] float NULL,
    [RequestRatePct] float NULL,
    [RelatedEndpoint] nvarchar(max) NULL,
    [Acknowledged] bit NOT NULL,
    [Silenced] bit NOT NULL,
    CONSTRAINT [PK_Alert] PRIMARY KEY ([AlertId]),
    CONSTRAINT [FK_Alert_Client_ClientId] FOREIGN KEY ([ClientId]) REFERENCES [Client] ([ClientId]) ON DELETE CASCADE
);
GO

CREATE TABLE [CorrelationEvent] (
    [CorrelationId] nvarchar(450) NOT NULL,
    [PerformanceAlertId] nvarchar(450) NOT NULL,
    [BehavioralAlertId] nvarchar(450) NOT NULL,
    [DetectedAt] datetime2 NOT NULL,
    CONSTRAINT [PK_CorrelationEvent] PRIMARY KEY ([CorrelationId]),
    CONSTRAINT [FK_CorrelationEvent_Alert_BehavioralAlertId] FOREIGN KEY ([BehavioralAlertId]) REFERENCES [Alert] ([AlertId]) ON DELETE NO ACTION,
    CONSTRAINT [FK_CorrelationEvent_Alert_PerformanceAlertId] FOREIGN KEY ([PerformanceAlertId]) REFERENCES [Alert] ([AlertId]) ON DELETE NO ACTION
);
GO

CREATE INDEX [IX_Alert_ClientId_CreatedAt] ON [Alert] ([ClientId], [CreatedAt]);
GO

CREATE INDEX [IX_CorrelationEvent_BehavioralAlertId] ON [CorrelationEvent] ([BehavioralAlertId]);
GO

CREATE INDEX [IX_CorrelationEvent_PerformanceAlertId] ON [CorrelationEvent] ([PerformanceAlertId]);
GO

INSERT INTO [__EFMigrationsHistory] ([MigrationId], [ProductVersion])
VALUES (N'20260720190812_InitialCreate', N'8.0.8');
GO

COMMIT;
GO