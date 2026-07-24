using System.Text;
using System.Text.Json;
using OpenSight.Application.DTOs;
using OpenSight.Application.Interfaces;
using RabbitMQ.Client;

namespace OpenSight.Infrastructure.Messaging;

/// API'nin yanıt süresini bloklamaması için fire-and-forget
/// RabbitMQ'ya ulaşılmasa bile istek yine başarılı döner, trafik loglama best-effort
public class RabbitMqTrafficEventPublisher : ITrafficEventPublisher, IDisposable
{
    private const string ExchangeName = "opensight.traffic";
    private const string RoutingKey = "traffic.raw";

    private readonly IConnection _connection;
    private readonly IModel _channel;

    public RabbitMqTrafficEventPublisher(string hostName)
    {
        var factory = new ConnectionFactory { HostName = hostName, DispatchConsumersAsync = true };
        _connection = factory.CreateConnection();
        _channel = _connection.CreateModel();
        _channel.ExchangeDeclare(ExchangeName, ExchangeType.Fanout, durable: true);
    }

    public Task PublishAsync(TrafficEventDto trafficEvent, CancellationToken ct = default)
    {
        try
        {
            var body = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(trafficEvent));
            var props = _channel.CreateBasicProperties();
            props.Persistent = false; // hot-path veri, kalıcı olması gerekmiyor
            _channel.BasicPublish(ExchangeName, RoutingKey, props, body);
        }
        catch
        {
            // yayın patlarsa da Mock API yanıtı etkilenmemesi için
        }
        return Task.CompletedTask;
    }

    public void Dispose()
    {
        _channel?.Dispose();
        _connection?.Dispose();
    }
}