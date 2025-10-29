#!/bin/bash
# AURA Compression - Docker Deployment Script

set -e

echo "===================================="
echo "AURA Compression - Docker Deployment"
echo "===================================="
echo ""

# Check Docker
echo "[1/4] Checking Docker..."
docker --version || {
    echo "❌ Docker is not installed"
    echo "Install from: https://docs.docker.com/get-docker/"
    exit 1
}
echo "✅ Docker detected"
echo ""

# Build Docker image
echo "[2/4] Building Docker image..."
docker build -t aura/compression:latest -t aura/compression:1.0.0 . || {
    echo "❌ Docker build failed"
    exit 1
}
echo "✅ Docker image built successfully"
echo ""

# Run container
echo "[3/4] Starting container..."
docker run -d \
    --name aura-compression-server \
    -p 8765:8765 \
    --restart unless-stopped \
    aura/compression:latest || {
    echo "❌ Failed to start container"
    echo "Note: If container already exists, run: docker rm aura-compression-server"
    exit 1
}
echo "✅ Container started"
echo ""

# Wait for health check
echo "[4/4] Waiting for health check..."
sleep 3

# Check container status
if docker ps | grep -q aura-compression-server; then
    echo "✅ Container is running"
else
    echo "❌ Container failed to start"
    echo ""
    echo "Logs:"
    docker logs aura-compression-server
    exit 1
fi

echo ""
echo "===================================="
echo "Deployment Complete!"
echo "===================================="
echo ""
echo "Server is running at: ws://localhost:8765"
echo ""
echo "Useful commands:"
echo "  docker logs aura-compression-server       # View logs"
echo "  docker stop aura-compression-server       # Stop server"
echo "  docker start aura-compression-server      # Start server"
echo "  docker rm aura-compression-server         # Remove container"
echo ""
echo "Or use docker-compose:"
echo "  docker-compose up -d                      # Start with compose"
echo "  docker-compose down                       # Stop with compose"
echo "  docker-compose logs -f                    # Follow logs"
echo ""
