using Microsoft.EntityFrameworkCore;
using OpenSight.Application.DTOs;
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
            Type = Enum.Parse<AlertType>(request.Type == "Davranışsal" ? "Davranissal" : request.Type),
            Severity = Enum.Parse<AlertSeverity>(MapSeverity(request.Severity)),
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
        var correlation = new CorrelationEvent
        {
            PerformanceAlertId = request.PerformanceAlertId,
            BehavioralAlertId = request.BehavioralAlertId
        };
        _db.CorrelationEvents.Add(correlation);
        await _db.SaveChangesAsync(ct);
        return correlation.CorrelationId;
    }

    public async Task<IReadOnlyList<AlertListItemDto>> GetRecentAlertsAsync(int take = 50, CancellationToken ct = default)
    {
        return await _db.Alerts
            .OrderByDescending(a => a.CreatedAt)
            .Take(take)
            .Select(a => new AlertListItemDto(a.AlertId, a.ClientId, a.Type.ToString(), a.Severity.ToString(), a.CreatedAt))
            .ToListAsync(ct);
    }

    public async Task<DashboardSummaryDto> GetDashboardSummaryAsync(CancellationToken ct = default)
    {
        var since = DateTime.UtcNow.AddHours(-24);
        var activeAlerts = await _db.Alerts.CountAsync(a => !a.Silenced && a.CreatedAt >= since, ct);
        var correlationCount = await _db.CorrelationEvents.CountAsync(c => c.DetectedAt >= since, ct);
        var activeClients = await _db.Clients.CountAsync(c => c.LastSeen >= since, ct);

        // ortalama gecikme Redis'ten okunacak, şimdilik placeholder
        var avgLatency = 0d;

        return new DashboardSummaryDto(activeAlerts, correlationCount, avgLatency, activeClients);
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

    private static string MapSeverity(string severity) => severity switch
    {
        "Düşük" => "Dusuk",
        "Orta" => "Orta",
        "Yüksek" => "Yuksek",
        _ => severity
    };
}