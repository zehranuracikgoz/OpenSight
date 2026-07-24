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
    Task<IReadOnlyList<AlertListItemDto>> GetRecentAlertsAsync(int take = 50, CancellationToken ct = default);
    Task<DashboardSummaryDto> GetDashboardSummaryAsync(CancellationToken ct = default);
    Task AcknowledgeAsync(string alertId, CancellationToken ct = default);
    Task SilenceAsync(string alertId, CancellationToken ct = default);
}