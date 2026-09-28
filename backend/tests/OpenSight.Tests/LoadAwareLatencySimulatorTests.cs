using OpenSight.Api;

namespace OpenSight.Tests;

public class LoadAwareLatencySimulatorTests
{
    private class FakeClock : IClock
    {
        public DateTime UtcNow { get; set; } = DateTime.UtcNow;
    }

    [Fact]
    public void ComputeExtraDelayMs_LowRecentRate_ReturnsNearZero()
    {
        var clock = new FakeClock();
        var simulator = new LoadAwareLatencySimulator(clock);

        // tek istek var, ek gecikme çok az olmalı
        var extra = simulator.ComputeExtraDelayMs("client_normal_0000");

        Assert.True(extra <= 20);
    }

    [Fact]
    public void ComputeExtraDelayMs_HighRecentRate_ReturnsLargerDelay()
    {
        var clock = new FakeClock();
        var simulator = new LoadAwareLatencySimulator(clock);
        var clientId = "client_yogun_0000";

        // art arda 10 istek, ek gecikme artmalı
        for (var i = 0; i < 10; i++)
        {
            simulator.ComputeExtraDelayMs(clientId);
        }
        var extra = simulator.ComputeExtraDelayMs(clientId);

        Assert.True(extra > 100);
    }

    [Fact]
    public void ComputeExtraDelayMs_OldRequestsFallOutOfWindow_DelayDropsBackDown()
    {
        var clock = new FakeClock();
        var simulator = new LoadAwareLatencySimulator(clock);
        var clientId = "client_yogun_0001";

        for (var i = 0; i < 10; i++)
        {
            simulator.ComputeExtraDelayMs(clientId);
        }
        var duringBurst = simulator.ComputeExtraDelayMs(clientId);

        clock.UtcNow = clock.UtcNow.AddSeconds(10); // 5s'lik pencere geçti
        var afterWindow = simulator.ComputeExtraDelayMs(clientId);

        Assert.True(duringBurst > afterWindow);
        Assert.True(afterWindow <= 100); // pencerede sadece son istek var
    }

    [Fact]
    public void ComputeExtraDelayMs_DifferentClients_AreTrackedIndependently()
    {
        var clock = new FakeClock();
        var simulator = new LoadAwareLatencySimulator(clock);

        for (var i = 0; i < 10; i++)
        {
            simulator.ComputeExtraDelayMs("client_busy");
        }
        var busyExtra = simulator.ComputeExtraDelayMs("client_busy");
        var quietExtra = simulator.ComputeExtraDelayMs("client_quiet");

        Assert.True(busyExtra > quietExtra);
    }

    [Fact]
    public void ComputeExtraDelayMs_ExtremelyHighRate_IsCappedAtMax()
    {
        var clock = new FakeClock();
        var simulator = new LoadAwareLatencySimulator(clock);
        var clientId = "client_extreme";

        for (var i = 0; i < 500; i++)
        {
            simulator.ComputeExtraDelayMs(clientId);
        }
        var extra = simulator.ComputeExtraDelayMs(clientId);

        Assert.True(extra <= 800);
    }
}
