using System.Collections.Concurrent;

namespace OpenSight.Api;

public interface IClock
{
    DateTime UtcNow { get; }
}

public class SystemClock : IClock
{
    public DateTime UtcNow => DateTime.UtcNow;
}

/// mock API'de gecikmeyi istemcinin son birkaç saniyedeki istek oranına bağlıyor
/// gecikme sabit rastgeleydi, yoğun profil hiç performans alarmı üretemiyordu
public class LoadAwareLatencySimulator
{
    private static readonly TimeSpan RecentWindow = TimeSpan.FromSeconds(5);
    private const double ExtraMsPerRequestPerSecond = 100.0; // her ek req/s için +100ms
    private const double MaxExtraMs = 800.0; // gecikme çok büyümesin diye tavan

    private readonly IClock _clock;
    private readonly ConcurrentDictionary<string, ConcurrentQueue<DateTime>> _recentRequests = new();

    public LoadAwareLatencySimulator(IClock clock) => _clock = clock;

    /// son 5 saniyedeki istek sayısına göre ek gecikme (ms) döndürüyor
    /// formül basit: req/s * 100, en fazla 800
    public int ComputeExtraDelayMs(string clientId)
    {
        var now = _clock.UtcNow;
        var queue = _recentRequests.GetOrAdd(clientId, _ => new ConcurrentQueue<DateTime>());
        queue.Enqueue(now);
        while (queue.TryPeek(out var oldest) && now - oldest > RecentWindow)
        {
            queue.TryDequeue(out _);
        }

        double recentRequestsPerSecond = queue.Count / RecentWindow.TotalSeconds;
        double extraMs = Math.Min(recentRequestsPerSecond * ExtraMsPerRequestPerSecond, MaxExtraMs);
        return (int)extraMs;
 
    }
}