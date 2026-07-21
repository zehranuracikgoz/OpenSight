namespace OpenSight.Domain.Entities;

/// <summary>
/// aynı client için performans ve davranışsal alarm aynı anda tetiklenirse,
/// ikisini burada tek bir olay olarak birleştirmek için
/// </summary>
public class CorrelationEvent
{
    public string CorrelationId { get; set; } = Guid.NewGuid().ToString();
    public string PerformanceAlertId { get; set; } = default!;
    public string BehavioralAlertId { get; set; } = default!;
    public DateTime DetectedAt { get; set; } = DateTime.UtcNow;

    public Alert? PerformanceAlert { get; set; }
    public Alert? BehavioralAlert { get; set; }
}