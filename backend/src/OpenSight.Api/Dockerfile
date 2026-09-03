# build context'in ./backend oldugunu varsayiyor (docker-compose.yml'e bakin) - Domain/Application/
# Infrastructure/Api birbirine ProjectReference ile bagli oldugu icin hepsinin ayni context'te olmasi gerekiyor
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# once sadece csproj dosyalarini kopyalayip restore ediyor - sadece kod degisince NuGet
# paketlerinin tekrar indirilmemesi icin (Docker layer cache)
COPY src/OpenSight.Domain/OpenSight.Domain.csproj OpenSight.Domain/
COPY src/OpenSight.Application/OpenSight.Application.csproj OpenSight.Application/
COPY src/OpenSight.Infrastructure/OpenSight.Infrastructure.csproj OpenSight.Infrastructure/
COPY src/OpenSight.Api/OpenSight.Api.csproj OpenSight.Api/
RUN dotnet restore OpenSight.Api/OpenSight.Api.csproj

# geri kalan kaynak kodu kopyalayip yayimliyor
COPY src/OpenSight.Domain/ OpenSight.Domain/
COPY src/OpenSight.Application/ OpenSight.Application/
COPY src/OpenSight.Infrastructure/ OpenSight.Infrastructure/
COPY src/OpenSight.Api/ OpenSight.Api/
RUN dotnet publish OpenSight.Api/OpenSight.Api.csproj -c Release -o /app --no-restore

# calistirma imaji sadece ASP.NET runtime iceriyor, SDK degil - imaj boyutu icin
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app .
EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080
ENTRYPOINT ["dotnet", "OpenSight.Api.dll"]
