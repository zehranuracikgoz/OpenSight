namespace OpenSight.Application.DTOs;

/// simülatörden gelen isteğin bilgisi - mock api bunu RabbitMQ'ya gönderiyor
public record TrafficEventDto(string ClientId, string Endpoint, int LatencyMs, int StatusCode);

/// analiz servisi bir anomali bulunca alarmı backend'e bildirmek için
public record CreateAlertRequest(
    string ClientId,
    string Type,          // "Performans" | "Davranışsal"
    string Severity,      // "Düşük" | "Orta" | "Yüksek"
    string? Description,
    double? ZScore,
    double? AnomalyScore,
    double? RequestRatePct,
    string? RelatedEndpoint
);

/// iki alarmı (performans + davranışsal) birleştirirken
public record CreateCorrelationEventRequest(string PerformanceAlertId, string BehavioralAlertId);

/// analiz servisinin Ollama'dan gelen daha zengin açıklamayla alert'i arka planda güncellemesi için
public record UpdateAlertDescriptionRequest(string Description);

/// dashboard'daki üst 4 metrik kartının verisi - Previous* alanları, aynı büyüklükte hemen
/// önceki zaman penceresindeki sayım, kartlardaki artış/azalış oku bundan hesaplanıyor
public record DashboardSummaryDto(
    int ActiveAlertCount,
    int CorrelationEventCount,
    double AverageLatencyMs,
    int ActiveClientCount,
    int PreviousActiveAlertCount = 0,
    int PreviousCorrelationEventCount = 0,
    int PreviousActiveClientCount = 0
);

/// alarm listesindeki her satırın şekli için
public record AlertListItemDto(
    string AlertId,
    string ClientId,
    string Type,
    string Severity,
    DateTime CreatedAt
);

/// sayfalanmış alarm listesi - TotalCount, sayfalama kontrollerinin "X / Y gösteriliyor" metni için
public record PagedAlertsDto(IReadOnlyList<AlertListItemDto> Items, int TotalCount);

/// detay panelinin ihtiyaç duyduğu tüm alanlar - ham metrikler, açıklama, onay/sessize durumu, varsa korelasyon
public record AlertDetailDto(
    string AlertId,
    string ClientId,
    string Type,
    string Severity,
    DateTime CreatedAt,
    string? Description,
    double? ZScore,
    double? AnomalyScore,
    double? RequestRatePct,
    string? RelatedEndpoint,
    bool Acknowledged,
    bool Silenced,
    string? CorrelationId
);