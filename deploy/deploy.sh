#!/bin/bash
# AVIP PoC — Deployment Script
# Run on the target server after cloning the repo
set -e

echo "=== AVIP PoC Deployment ==="
echo ""

# 0. Create model placeholder files if they don't exist
echo "0. Checking AI model files..."
mkdir -p backend/ai_models/patchcore backend/ai_models/yolov8
if [ ! -f backend/ai_models/patchcore/model.onnx ]; then
    echo "   Creating placeholder model files (demo mode — models not required)"
    touch backend/ai_models/patchcore/model.onnx
    touch backend/ai_models/yolov8/defect_detector.onnx
fi
echo "   ✓ Model directory ready"

# 1. Build and start containers
echo ""
echo "1. Building Docker images..."
docker compose -f docker-compose.prod.yml build

echo ""
echo "2. Starting services..."
docker compose -f docker-compose.prod.yml up -d

echo ""
echo "3. Waiting for health check..."
sleep 5
if curl -sf http://localhost:8001/api/v1/health > /dev/null; then
    echo "   ✓ API is healthy"
else
    echo "   ✗ API health check failed. Check logs:"
    echo "     docker compose -f docker-compose.prod.yml logs avip-api"
    exit 1
fi

if curl -sf http://localhost:5174 > /dev/null; then
    echo "   ✓ Frontend is serving"
else
    echo "   ✗ Frontend check failed. Check logs:"
    echo "     docker compose -f docker-compose.prod.yml logs avip-frontend"
    exit 1
fi

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "  Frontend:  http://localhost:5174"
echo "  API:       http://localhost:8001"
echo "  Health:    http://localhost:8001/api/v1/health"
echo ""
echo "Provide to DevOps for Nginx routing:"
echo "  Subdomain:  avip.ideyalabs.com"
echo "  Upstream:   http://127.0.0.1:5174"
echo "  (Frontend Nginx handles /api/ and /static/ proxy internally)"
echo ""
