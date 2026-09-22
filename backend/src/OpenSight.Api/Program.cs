using Microsoft.EntityFrameworkCore;
using OpenSight.Application.Interfaces;
using OpenSight.Infrastructure.Messaging;
using OpenSight.Infrastructure.Persistence;
using OpenSight.Infrastructure.Services;

var builder = WebApplication.CreateBuilder(args);

// veritabanı bağlantısı (PostgreSQL - Supabase/Render gibi ücretsiz servislerde de çalışsın diye)
builder.Services.AddDbContext<OpenSightDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("OpenSightDb")));

// RabbitMQ bağlantısı
builder.Services.AddSingleton<ITrafficEventPublisher>(_ =>
    new RabbitMqTrafficEventPublisher(builder.Configuration["RabbitMQ:Uri"] ?? "amqp://localhost"));

// iş mantığı servisleri
builder.Services.AddScoped<IAlertService, AlertService>();

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddCors(options =>
{
    options.AddPolicy("Dashboard", policy =>
        policy.WithOrigins(builder.Configuration["Cors:DashboardOrigin"] ?? "http://localhost:5173")
              .AllowAnyHeader()
              .AllowAnyMethod());
});

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseCors("Dashboard");
app.MapControllers();

// basit health check - dashboard üst barındaki "servisler aktif" göstergesi için
app.MapGet("/health", () => Results.Ok(new { status = "healthy", service = "OpenSight.Api" }));

app.Run();