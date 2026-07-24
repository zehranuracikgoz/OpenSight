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

/// dashboard'daki üst 4 metrik kartının verisi
public record DashboardSummaryDto(
    int ActiveAlertCount,
    int CorrelationEventCount,
    double AverageLatencyMs,
    int ActiveClientCount
);

/// alarm listesindeki her satırın şekli için
public record AlertListItemDto(
    string AlertId,
    string ClientId,
    string Type,
    string Severity,
    DateTime CreatedAt
);