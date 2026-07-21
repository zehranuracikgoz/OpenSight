namespace OpenSight.Domain.Entities;

public enum AlertType
{
    Performans,
    Davranissal
}

public enum AlertSeverity
{
    Dusuk,
    Orta,
    Yuksek
}

public class Alert
{
    public string AlertId { get; set; } = Guid.NewGuid().ToString();
    public string ClientId { get; set; } = default!;
    public AlertType Type { get; set; }
    public AlertSeverity Severity { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    /// <summary>ollama üretiyor; yetişmezse (3sn timeout) kural tabanlı şablona düşüyor</summary>
    public string? Description { get; set; }

    // alarmı tetikleyen ham sayılar
    public double? ZScore { get; set; }
    public double? AnomalyScore { get; set; }
    public double? RequestRatePct { get; set; }
    public string? RelatedEndpoint { get; set; }

    public bool Acknowledged { get; set; }
    public bool Silenced { get; set; }

    public Client? Client { get; set; }
}