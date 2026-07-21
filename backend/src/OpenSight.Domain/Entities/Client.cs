namespace OpenSight.Domain.Entities;

/// API'yi çağıran taraf - uygulama/şirket kimliği
public class Client
{
    public string ClientId { get; set; } = default!;
    public DateTime FirstSeen { get; set; } = DateTime.UtcNow;
    public DateTime LastSeen { get; set; } = DateTime.UtcNow;

    public ICollection<Alert> Alerts { get; set; } = new List<Alert>();
}