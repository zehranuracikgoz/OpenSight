using Microsoft.EntityFrameworkCore;
using OpenSight.Application.DTOs;
using OpenSight.Application.Exceptions;
using OpenSight.Application.Interfaces;
using OpenSight.Domain.Entities;
using OpenSight.Infrastructure.Persistence;

namespace OpenSight.Infrastructure.Services;

public class AlertService : IAlertService
{
    private readonly OpenSightDbContext _db;

    public AlertService(OpenSightDbContext db) => _db = db;

    public async Task<string> CreateAlertAsync(CreateAlertRequest request, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(request.ClientId))
            throw new ValidationException("clientId boş olamaz");

        AlertType type;
        AlertSeverity severity;
        try
        {
            type = Enum.Parse<AlertType>(request.Type == "Davranışsal" ? "Davranissal" : request.Type);
            severity = Enum.Parse<AlertSeverity>(MapSeverity(request.Severity));
        }
        catch (ArgumentException)
        {
            throw new ValidationException($"geçersiz type/severity: type={request.Type}, severity={request.Severity}");
        }

        var client = await _db.Clients.FindAsync(new object?[] { request.ClientId }, ct);
        if (client is null)
        {
            client = new Client { ClientId = request.ClientId };
            _db.Clients.Add(client);
        }
        else
        {
            client.LastSeen = DateTime.UtcNow;
        }

        var alert = new Alert
        {
            ClientId = request.ClientId,
            Type = type,
            Severity = severity,
            Description = request.Description,
            ZScore = request.ZScore,
            AnomalyScore = request.AnomalyScore,
            RequestRatePct = request.RequestRatePct,
            RelatedEndpoint = request.RelatedEndpoint
        };

        _db.Alerts.Add(alert);
        await _db.SaveChangesAsync(ct);
        return alert.AlertId;
    }

    public async Task<string> CreateCorrelationEventAsync(CreateCorrelationEventRequest request, CancellationToken ct = default)
    {
        var performanceAlert = await _db.Alerts.FindAsync(new object?[] { request.PerformanceAlertId }, ct);
        if (performanceAlert is null)
            throw new ValidationException($"performanceAlertId bulunamadı: {request.PerformanceAlertId}");

        var behavioralAlert = await _db.Alerts.FindAsync(new object?[] { request.BehavioralAlertId }, ct);
        if (behavioralAlert is null)
            throw new ValidationException($"behavioralAlertId bulunamadı: {request.BehavioralAlertId}");

        var correlation = new CorrelationEvent
        {
            PerformanceAlertId = request.PerformanceAlertId,
            BehavioralAlertId = request.BehavioralAlertId
        };
        _db.CorrelationEvents.Add(correlation);
        await _db.SaveChangesAsync(ct);
        return correlation.CorrelationId;
    }

    public async Task<PagedAlertsDto> GetRecentAlertsAsync(int take = 50, int skip = 0, int? hours = null, CancellationToken ct = default)
    {
        var query = _db.Alerts.AsQueryable();
        if (hours is not null)
        {
            var since = DateTime.UtcNow.AddHours(-hours.Value);
            query = query.Where(a => a.CreatedAt >= since);
        }

        var totalCount = await query.CountAsync(ct);
        var alerts = await query
            .OrderByDescending(a => a.CreatedAt)
            .Skip(skip)
            .Take(take)
            .ToListAsync(ct);

        var items = alerts
            .Select(a => new AlertListItemDto(a.AlertId, a.ClientId, TypeLabel(a.Type), SeverityLabel(a.Severity), a.CreatedAt))
            .ToList();
        return new PagedAlertsDto(items, totalCount);
    }

    public async Task<AlertDetailDto?> GetAlertByIdAsync(string alertId, CancellationToken ct = default)
    {
        var alert = await _db.Alerts.FindAsync(new object?[] { alertId }, ct);
        if (alert is null) return null;

        // bu alert bir korelasyon olayına dahil mi diye kontrol ediyor
        var correlation = await _db.CorrelationEvents
            .FirstOrDefaultAsync(c => c.PerformanceAlertId == alertId || c.BehavioralAlertId == alertId, ct);

        return new AlertDetailDto(
            alert.AlertId,
            alert.ClientId,
            TypeLabel(alert.Type),
            SeverityLabel(alert.Severity),
            alert.CreatedAt,
            alert.Description,
            alert.ZScore,
            alert.AnomalyScore,
            alert.RequestRatePct,
            alert.RelatedEndpoint,
            alert.Acknowledged,
            alert.Silenced,
            correlation?.CorrelationId
        );
    }

    public async Task<DashboardSummaryDto> GetDashboardSummaryAsync(int hours = 24, CancellationToken ct = default)
    {
        var now = DateTime.UtcNow;
        var since = now.AddHours(-hours);
        var activeAlerts = await _db.Alerts.CountAsync(a => !a.Silenced && a.CreatedAt >= since, ct);
        var correlationCount = await _db.CorrelationEvents.CountAsync(c => c.DetectedAt >= since, ct);
        var activeClients = await _db.Clients.CountAsync(c => c.LastSeen >= since, ct);

        // trend oku için hemen önceki, aynı büyüklükteki pencere - [now-2h, now-h)
        var previousSince =now.AddHours(-2 * hours);
        var previousActiveAlerts = await _db.Alerts.CountAsync(a => !a.Silenced && a.CreatedAt >= previousSince && a.CreatedAt < since, ct);
        var previousCorrelationCount = await _db.CorrelationEvents.CountAsync(c=> c.DetectedAt >= previousSince && c.DetectedAt < since, ct);
        var previousActiveClients = await _db.Clients.CountAsync(c => c.LastSeen >= previousSince && c.LastSeen < since, ct);

        // ortalama gecikme Redis'ten okunacak, şimdilik placeholder
        var avgLatency = 0d;

        return new DashboardSummaryDto(
            activeAlerts, correlationCount, avgLatency, activeClients,
            previousActiveAlerts,previousCorrelationCount, previousActiveClients
        );
    }

    public async Task AcknowledgeAsync(string alertId, CancellationToken ct = default)
    {
        var alert = await _db.Alerts.FindAsync(new object?[] { alertId }, ct);
        if (alert is null) return;
        alert.Acknowledged = true;
        await _db.SaveChangesAsync(ct);
    }

    public async Task SilenceAsync(string alertId, CancellationToken ct = default)
    {
        var alert = await _db.Alerts.FindAsync(new object?[] { alertId }, ct);
        if (alert is null) return;
        alert.Silenced = true;
        await _db.SaveChangesAsync(ct);
    }

    public async Task UpdateDescriptionAsync(string alertId, string description, CancellationToken ct = default)
    {
        var alert = await _db.Alerts.FindAsync(new object?[] { alertId }, ct);
        if (alert is null) return;
        alert.Description =description;
        await _db.SaveChangesAsync(ct);
    }

    private static string MapSeverity(string severity) => severity switch
    {
        "Düşük" => "Dusuk",
        "Orta" => "Orta",
        "Yüksek" => "Yuksek",
        _ => severity
    };

    // enum adları ASCII (Davranissal/Dusuk/Yuksek), dashboard'a Türkçe etiketlerle dönüyor
    private static string TypeLabel(AlertType type) => type switch
    {
        AlertType.Davranissal => "Davranışsal",
        _ => "Performans"
    };

    private static string SeverityLabel(AlertSeverity severity) => severity switch
    {
        AlertSeverity.Dusuk => "Düşük",
        AlertSeverity.Yuksek => "Yüksek",
        _ => "Orta"
    };
}