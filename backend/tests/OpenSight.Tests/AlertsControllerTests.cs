using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using OpenSight.Api.Controllers;
using OpenSight.Application.DTOs;
using OpenSight.Infrastructure.Persistence;
using OpenSight.Infrastructure.Services;

namespace OpenSight.Tests;

public class AlertsControllerTests
{
    private static OpenSightDbContext CreateInMemoryDb()
    {
        var options = new DbContextOptionsBuilder<OpenSightDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;
        return new OpenSightDbContext(options);
    }

    [Fact]
    public async Task CreateAlert_ValidRequest_Returns201AndPersists()
    {
        var db = CreateInMemoryDb();
        var controller = new AlertsController(new AlertService(db));
        var request = new CreateAlertRequest("client_1", "Performans", "Yüksek", "test açıklaması", 4.2, null, null, "/v1/accounts");

        var result = await controller.CreateAlert(request, CancellationToken.None);

        var created = Assert.IsType<CreatedAtActionResult>(result);
        Assert.Equal(201, created.StatusCode);
        Assert.Single(db.Alerts);
        Assert.Equal("client_1", db.Alerts.First().ClientId);
    }

    [Fact]
    public async Task CreateAlert_InvalidType_ReturnsBadRequestAndDoesNotPersist()
    {
        var db = CreateInMemoryDb();
        var controller = new AlertsController(new AlertService(db));
        var request = new CreateAlertRequest("client_1", "GecersizTur", "Yüksek", null, null, null, null, null);

        var result = await controller.CreateAlert(request, CancellationToken.None);

        var badRequest = Assert.IsType<BadRequestObjectResult>(result);
        Assert.Equal(400, badRequest.StatusCode);
        Assert.Empty(db.Alerts);
    }

    [Fact]
    public async Task CreateAlert_EmptyClientId_ReturnsBadRequest()
    {
        var db = CreateInMemoryDb();
        var controller = new AlertsController(new AlertService(db));
        var request = new CreateAlertRequest("", "Performans", "Orta", null, null, null, null, null);

        var result = await controller.CreateAlert(request, CancellationToken.None);

        Assert.IsType<BadRequestObjectResult>(result);
        Assert.Empty(db.Alerts);
    }

    [Fact]
    public async Task CreateCorrelation_ValidAlerts_Returns200AndPersists()
    {
        var db = CreateInMemoryDb();
        var service = new AlertService(db);
        var perfId = await service.CreateAlertAsync(new CreateAlertRequest("client_2", "Performans", "Orta", null, 3.5, null, null, null));
        var behId = await service.CreateAlertAsync(new CreateAlertRequest("client_2", "Davranışsal", "Orta", null, null, 0.8, null, null));
        var controller = new AlertsController(service);

        var result = await controller.CreateCorrelation(new CreateCorrelationEventRequest(perfId, behId), CancellationToken.None);

        var ok = Assert.IsType<OkObjectResult>(result);
        Assert.Equal(200, ok.StatusCode);
        Assert.Single(db.CorrelationEvents);
    }

    [Fact]
    public async Task CreateCorrelation_NonExistentAlert_ReturnsBadRequestAndDoesNotPersist()
    {
        var db = CreateInMemoryDb();
        var controller = new AlertsController(new AlertService(db));

        var result = await controller.CreateCorrelation(new CreateCorrelationEventRequest("yok-1", "yok-2"), CancellationToken.None);

        var badRequest = Assert.IsType<BadRequestObjectResult>(result);
        Assert.Equal(400, badRequest.StatusCode);
        Assert.Empty(db.CorrelationEvents);
    }

    [Fact]
    public async Task GetSummary_ReturnsCountsFromDatabase()
    {
        var db = CreateInMemoryDb();
        var service = new AlertService(db);
        await service.CreateAlertAsync(new CreateAlertRequest("client_3", "Performans", "Düşük", null, 1.1, null, null, null));
        var controller = new AlertsController(service);

        var result = await controller.GetSummary(CancellationToken.None);

        var ok = Assert.IsType<OkObjectResult>(result.Result);
        var summary = Assert.IsType<DashboardSummaryDto>(ok.Value);
        Assert.Equal(1, summary.ActiveAlertCount);
        Assert.Equal(1, summary.ActiveClientCount);
    }

    [Fact]
    public async Task GetById_ExistingAlert_ReturnsAllRawMetrics()
    {
        var db = CreateInMemoryDb();
        var service = new AlertService(db);
        var alertId = await service.CreateAlertAsync(
            new CreateAlertRequest("client_4", "Davranışsal", "Yüksek", "test açıklaması", null, 0.92, 18.5, "/v1/payments"));
        var controller = new AlertsController(service);

        var result = await controller.GetById(alertId, CancellationToken.None);

        var ok = Assert.IsType<OkObjectResult>(result.Result);
        var detail =Assert.IsType<AlertDetailDto>(ok.Value);
        Assert.Equal("client_4", detail.ClientId);
        Assert.Equal("Davranışsal", detail.Type); // ASCII enum değil, Türkçe etiket dönmeli
        Assert.Equal("Yüksek", detail.Severity);
        Assert.Equal(0.92, detail.AnomalyScore);
        Assert.Equal(18.5, detail.RequestRatePct);
        Assert.Equal("/v1/payments", detail.RelatedEndpoint) ;
        Assert.False(detail.Acknowledged);
        Assert.Null(detail.CorrelationId);
    }

    [Fact]
    public async Task GetById_NonExistentAlert_ReturnsNotFound()
    {
        var db = CreateInMemoryDb();
        var controller = new AlertsController(new AlertService(db));

        var result = await controller.GetById("yok", CancellationToken.None);

        Assert.IsType<NotFoundResult>(result.Result);
    }

    [Fact]
    public async Task GetById_CorrelatedAlert_IncludesCorrelationId()
    {
        var db = CreateInMemoryDb();
        var service = new AlertService(db);
        var perfId = await service.CreateAlertAsync(new CreateAlertRequest("client_5", "Performans", "Orta", null, 3.5, null, null, null));
        var behId = await service.CreateAlertAsync(new CreateAlertRequest("client_5", "Davranışsal", "Orta", null, null, 0.8, null, null));
        await service.CreateCorrelationEventAsync(new CreateCorrelationEventRequest(perfId, behId));
        var controller = new AlertsController(service);

        var result = await controller.GetById(perfId, CancellationToken.None);

        var ok = Assert.IsType<OkObjectResult>(result.Result);
        var detail = Assert.IsType<AlertDetailDto>(ok.Value);
        Assert.NotNull(detail.CorrelationId);
    }
}
