using OpenSight.Application.DTOs;

namespace OpenSight.Application.Interfaces;

/// trafik olayını yayınlama işi - asıl kod (RabbitMQ) Infrastructure'da
public interface ITrafficEventPublisher
{
    Task PublishAsync(TrafficEventDto trafficEvent, CancellationToken ct = default);
}

/// alarm ve korelasyon kayıtlarını yazma/okuma işi - asıl kod (EF Core) Infrastructure'da
public interface IAlertService
{
    Task<string> CreateAlertAsync(CreateAlertRequest request, CancellationToken ct = default);
    Task<string> CreateCorrelationEventAsync(CreateCorrelationEventRequest request, CancellationToken ct = default);
    Task<PagedAlertsDto> GetRecentAlertsAsync(int take = 50, int skip = 0, int? hours = null, CancellationToken ct = default);
    Task<AlertDetailDto?> GetAlertByIdAsync(string alertId, CancellationToken ct = default);
    Task<DashboardSummaryDto> GetDashboardSummaryAsync(int hours = 24, CancellationToken ct = default);
    Task AcknowledgeAsync(string alertId, CancellationToken ct = default);
    Task SilenceAsync(string alertId, CancellationToken ct = default);
    Task UpdateDescriptionAsync(string alertId, string description, CancellationToken ct = default);
}