# Docker Setup for Discovery Project

This document explains how to use the Docker setup for the Discovery project.

## Prerequisites

- Docker installed on your system
- Docker Compose installed on your system

## Getting Started

### Build and Start the Container

```bash
docker-compose up --build -d
```

This command will:
1. Build the Docker image based on the Dockerfile
2. Start the container in detached mode

### Verify the Container is Running

```bash
docker ps
```

You should see a container named `discovery-scrapyd` running.

### Access Scrapyd Web Interface

Open your browser and navigate to:

```
http://localhost:6800
```

### Deploy Your Spiders

To deploy your spiders to Scrapyd, use the following command from your project directory:

```bash
scrapyd-client deploy
```

This will package and deploy your spiders to the running Scrapyd instance.

### Schedule a Spider Run

You can schedule a spider run using the Scrapyd API:

```bash
curl http://localhost:6800/schedule.json -d project=discovery -d spider=quick -d start_urls=https://example.com
```

Or using scrapyd-client:

```bash
scrapyd-client schedule -p discovery quick start_urls=https://example.com
```

### Stop the Container

```bash
docker-compose down
```

## Docker Configuration Details

### Volumes

The Docker Compose configuration creates several volumes to persist data:

- `./data:/app/data`: Maps the local data directory to the container's data directory
- `scrapyd_eggs:/app/eggs`: Stores eggs (packaged spiders)
- `scrapyd_items:/app/items`: Stores scraped items
- `scrapyd_logs:/app/logs`: Stores logs
- `scrapyd_dbs:/app/dbs`: Stores Scrapyd databases

### Environment Variables

You can configure the following environment variables:

- `DISCOVERY_ENV`: Set to `production` by default
- `SCRAPYD_USERNAME`: (Optional) Username for Scrapyd authentication
- `SCRAPYD_PASSWORD`: (Optional) Password for Scrapyd authentication

To enable authentication, uncomment the corresponding lines in the `docker-compose.yml` file.

### Exposed Port

The container exposes port 6800, which is the default port for Scrapyd.

## Custom Configuration

If you need to customize the Scrapyd configuration, edit the `scrapyd.conf` file before building the Docker image.
