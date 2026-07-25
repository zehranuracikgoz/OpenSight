using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace OpenSight.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Client",
                columns: table => new
                {
                    ClientId = table.Column<string>(type: "nvarchar(450)", nullable: false),
                    FirstSeen = table.Column<DateTime>(type: "datetime2", nullable: false),
                    LastSeen = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Client", x => x.ClientId);
                });

            migrationBuilder.CreateTable(
                name: "Alert",
                columns: table => new
                {
                    AlertId = table.Column<string>(type: "nvarchar(450)", nullable: false),
                    ClientId = table.Column<string>(type: "nvarchar(450)", nullable: false),
                    Type = table.Column<string>(type: "nvarchar(32)", maxLength: 32, nullable: false),
                    Severity = table.Column<string>(type: "nvarchar(16)", maxLength: 16, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "datetime2", nullable: false),
                    Description = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    ZScore = table.Column<double>(type: "float", nullable: true),
                    AnomalyScore = table.Column<double>(type: "float", nullable: true),
                    RequestRatePct = table.Column<double>(type: "float", nullable: true),
                    RelatedEndpoint = table.Column<string>(type: "nvarchar(max)", nullable: true),
                    Acknowledged = table.Column<bool>(type: "bit", nullable: false),
                    Silenced = table.Column<bool>(type: "bit", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Alert", x => x.AlertId);
                    table.ForeignKey(
                        name: "FK_Alert_Client_ClientId",
                        column: x => x.ClientId,
                        principalTable: "Client",
                        principalColumn: "ClientId",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "CorrelationEvent",
                columns: table => new
                {
                    CorrelationId = table.Column<string>(type: "nvarchar(450)", nullable: false),
                    PerformanceAlertId = table.Column<string>(type: "nvarchar(450)", nullable: false),
                    BehavioralAlertId = table.Column<string>(type: "nvarchar(450)", nullable: false),
                    DetectedAt = table.Column<DateTime>(type: "datetime2", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_CorrelationEvent", x => x.CorrelationId);
                    table.ForeignKey(
                        name: "FK_CorrelationEvent_Alert_BehavioralAlertId",
                        column: x => x.BehavioralAlertId,
                        principalTable: "Alert",
                        principalColumn: "AlertId",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_CorrelationEvent_Alert_PerformanceAlertId",
                        column: x => x.PerformanceAlertId,
                        principalTable: "Alert",
                        principalColumn: "AlertId",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Alert_ClientId_CreatedAt",
                table: "Alert",
                columns: new[] { "ClientId", "CreatedAt" });

            migrationBuilder.CreateIndex(
                name: "IX_CorrelationEvent_BehavioralAlertId",
                table: "CorrelationEvent",
                column: "BehavioralAlertId");

            migrationBuilder.CreateIndex(
                name: "IX_CorrelationEvent_PerformanceAlertId",
                table: "CorrelationEvent",
                column: "PerformanceAlertId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "CorrelationEvent");

            migrationBuilder.DropTable(
                name: "Alert");

            migrationBuilder.DropTable(
                name: "Client");
        }
    }
}