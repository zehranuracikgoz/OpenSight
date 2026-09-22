using Microsoft.AspNetCore.Mvc;
using OpenSight.Application.DTOs;
using OpenSight.Application.Exceptions;
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
        try
        {
            var alertId = await _alertService.CreateAlertAsync(request, ct);
            return CreatedAtAction(nameof(GetRecent), new { }, new { alertId });
        }
        catch (ValidationException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// aynı client için aynı anda tetiklenen iki alarmı birleştiren uç nokta
    [HttpPost("correlations")]
    public async Task<IActionResult> CreateCorrelation([FromBody] CreateCorrelationEventRequest request, CancellationToken ct)
    {
        try
        {
            var correlationId = await _alertService.CreateCorrelationEventAsync(request, ct);
            return Ok(new { correlationId });
        }
        catch (ValidationException ex)
        {
            return BadRequest(new { error = ex.Message });
        }
    }

    /// hours verilmezse zaman filtresi uygulanmaz (eski davranışla uyumlu) - dashboard'daki
    /// zaman aralığı dropdown'u seçtiği pencereye göre hours'u dolduruyor
    [HttpGet]
    public async Task<ActionResult<PagedAlertsDto>> GetRecent(
        [FromQuery] int take = 50, [FromQuery] int skip = 0, [FromQuery] int? hours = null, CancellationToken ct = default)
        => Ok(await _alertService.GetRecentAlertsAsync(take, skip, hours, ct));

    [HttpGet("summary")]
    public async Task<ActionResult<DashboardSummaryDto>> GetSummary([FromQuery] int hours = 24, CancellationToken ct = default)
        => Ok(await _alertService.GetDashboardSummaryAsync(hours, ct));

    /// tek bir alert'in tüm detayını dönüyor (detay paneli için) - "summary" literal'i bu route'tan önce eşleşir
    [HttpGet("{alertId}")]
    public async Task<ActionResult<AlertDetailDto>> GetById(string alertId, CancellationToken ct)
    {
        var alert = await _alertService.GetAlertByIdAsync(alertId, ct);
        return alert is null ? NotFound() : Ok(alert);
    }

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

    /// analiz servisinin Ollama'dan gelen daha zengin açıklamayla alert'i arka planda güncellemesi için -
    /// alert zaten şablon açıklamayla oluşturulmuş olur, bu sadece sonradan iyileştirme yapar
    [HttpPatch("{alertId}/description")]
    public async Task<IActionResult> UpdateDescription(string alertId, [FromBody] UpdateAlertDescriptionRequest request, CancellationToken ct)
    {
        await _alertService.UpdateDescriptionAsync(alertId, request.Description, ct);
        return NoContent();
    }
}