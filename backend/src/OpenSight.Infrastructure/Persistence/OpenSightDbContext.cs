using Microsoft.EntityFrameworkCore;
using OpenSight.Domain.Entities;

namespace OpenSight.Infrastructure.Persistence;

public class OpenSightDbContext : DbContext
{
    public OpenSightDbContext(DbContextOptions<OpenSightDbContext> options) : base(options) { }

    public DbSet<Client> Clients => Set<Client>();
    public DbSet<Alert> Alerts => Set<Alert>();
    public DbSet<CorrelationEvent> CorrelationEvents => Set<CorrelationEvent>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Client>(e =>
        {
            e.ToTable("Client");
            e.HasKey(c => c.ClientId);
        });

        modelBuilder.Entity<Alert>(e =>
        {
            e.ToTable("Alert");
            e.HasKey(a => a.AlertId);
            e.Property(a => a.Type).HasConversion<string>().HasMaxLength(32);
            e.Property(a => a.Severity).HasConversion<string>().HasMaxLength(16);
            e.HasOne(a => a.Client)
                .WithMany(c => c.Alerts)
                .HasForeignKey(a => a.ClientId);
            e.HasIndex(a => new { a.ClientId, a.CreatedAt });
        });

        modelBuilder.Entity<CorrelationEvent>(e =>
        {
            e.ToTable("CorrelationEvent");
            e.HasKey(c => c.CorrelationId);
            e.HasOne(c => c.PerformanceAlert)
                .WithMany()
                .HasForeignKey(c => c.PerformanceAlertId)
                .OnDelete(DeleteBehavior.Restrict);
            e.HasOne(c => c.BehavioralAlert)
                .WithMany()
                .HasForeignKey(c => c.BehavioralAlertId)
                .OnDelete(DeleteBehavior.Restrict);
        });
    }
}