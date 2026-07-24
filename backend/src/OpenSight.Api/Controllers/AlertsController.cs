using Microsoft.AspNetCore.Mvc;
using OpenSight.Application.DTOs;
using OpenSight.Application.Interfaces;

namespace OpenSight.Api.Controllers;

/// analiz servisi buraya yazıyor (alarm/korelasyon), dashboard buradan okuyor
[ApiController]
[Route("api/alerts")]
public class AlertsController : ControllerBase
{
    private readonly IAlertService _alertService;

    public AlertsController(IAlertService alertService) => _alertService = alertService;

    /// z-score veya Isolation Forest'ın ürettiği alarmı kaydetmek için
    [HttpPost]
    public async Task<IActionResult> CreateAlert([FromBody] CreateAlertRequest request, CancellationToken ct)
    {
        var alertId = await _alertService.CreateAlertAsync(request, ct);
        return CreatedAtAction(nameof(GetRecent), new { }, new { alertId });
    }

    /// aynı client için aynı anda tetiklenen iki alarmı birleştiren uç nokta
    [HttpPost("correlations")]
    public async Task<IActionResult> CreateCorrelation([FromBody] CreateCorrelationEventRequest request, CancellationToken ct)
    {
        var correlationId = await _alertService.CreateCorrelationEventAsync(request, ct);
        return Ok(new { correlationId });
    }

    [HttpGet]
    public async Task<ActionResult<IReadOnlyList<AlertListItemDto>>> GetRecent([FromQuery] int take = 50, CancellationToken ct = default)
        => Ok(await _alertService.GetRecentAlertsAsync(take, ct));

    [HttpGet("summary")]
    public async Task<ActionResult<DashboardSummaryDto>> GetSummary(CancellationToken ct)
        => Ok(await _alertService.GetDashboardSummaryAsync(ct));

    [HttpPost("{alertId}/acknowledge")]
    public async Task<IActionResult> Acknowledge(string alertId, CancellationToken ct)
    {
        await _alertService.AcknowledgeAsync(alertId, ct);
        return NoContent();
    }

    [HttpPost("{alertId}/silence")]
    public async Task<IActionResult> Silence(string alertId, CancellationToken ct)
    {
        await _alertService.SilenceAsync(alertId, ct);
        return NoContent();
    }
}