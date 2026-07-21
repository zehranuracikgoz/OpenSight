namespace OpenSight.Domain.Entities;

/// <summary>
/// mock API'ye gelen tek bir isteğin anlık görüntüsü. Veritabanına hiç yazılmıyor
/// RabbitMQ'ya fire-and-forget atıp Redis'te sadece son N isteklik pencerede tutuluyor
/// yoksa API'nin yanıt süresi buna bağlı kalır.
/// </summary>
public class TrafficEvent
{
    public string ClientId { get; set; } = default!;
    public DateTime Timestamp { get; set; } = DateTime.UtcNow;
    public string Endpoint { get; set; } = default!;
    public int LatencyMs { get; set; }
    public int StatusCode { get; set; }
}