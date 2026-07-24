using Microsoft.AspNetCore.Mvc;
using OpenSight.Application.DTOs;
using OpenSight.Application.Interfaces;

namespace OpenSight.Api.Controllers;

/// Trafik Simülatörü'nün hedef aldığı mock Open Banking uç noktaları - PSD2 tarzı
/// (hesap bilgisi/ödeme) senaryoları simüle ediyor. Yanıt süresi RabbitMQ'ya yazmaya
/// bağlı değil, publish fire-and-forget
[ApiController]
[Route("v1")]
public class MockOpenBankingController : ControllerBase
{
    private readonly ITrafficEventPublisher _publisher;

    public MockOpenBankingController(ITrafficEventPublisher publisher) => _publisher = publisher;

    [HttpGet("accounts")]
    public async Task<IActionResult> GetAccounts([FromHeader(Name = "X-Client-Id")] string clientId)
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        await Task.Delay(Random.Shared.Next(20, 80)); // gerçekçi bir gecikme simülesi
        sw.Stop();

        await LogTrafficAsync(clientId, "/v1/accounts", (int)sw.ElapsedMilliseconds, 200);
        return Ok(new { accounts = new[] { new { iban = "TR000000000000000000000001", balance = 1000 } } });
    }

    [HttpPost("payments")]
    public async Task<IActionResult> InitiatePayment([FromHeader(Name = "X-Client-Id")] string clientId)
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        await Task.Delay(Random.Shared.Next(30, 150));
        sw.Stop();

        await LogTrafficAsync(clientId, "/v1/payments", (int)sw.ElapsedMilliseconds, 201);
        return StatusCode(201, new { paymentId = Guid.NewGuid() });
    }

    private Task LogTrafficAsync(string clientId, string endpoint, int latencyMs, int statusCode)
    {
        var evt = new TrafficEventDto(clientId, endpoint, latencyMs, statusCode);
        // sonucu beklemeden dönüyor, API yanıt süresi buna bağlı kalmamalı
        _ = _publisher.PublishAsync(evt);
        return Task.CompletedTask;
    }
}