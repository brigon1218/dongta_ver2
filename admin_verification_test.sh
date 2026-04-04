#!/bin/bash

# Admin Page Verification Test
# Tests that all admin pages are accessible and responsive

BASE_URL="https://dongta.theuit.info"
INSECURE="-k"  # Ignore SSL cert issues (self-signed)

echo "====================================="
echo "Admin Page Verification Test"
echo "====================================="
echo ""

# Test 1: Health Check
echo "✓ Test 1: Health Check"
HEALTH=$(curl -s $INSECURE "$BASE_URL/api/v1/health/")
if echo "$HEALTH" | grep -q "healthy"; then
    echo "  ✅ Status: Healthy"
    echo "  Database: $(echo "$HEALTH" | grep -o '"database":"[^"]*"')"
    echo "  Cache: $(echo "$HEALTH" | grep -o '"cache":"[^"]*"')"
else
    echo "  ❌ Status: Failed"
fi
echo ""

# Test 2: Admin Login Page
echo "✓ Test 2: Admin Login Page"
STATUS=$(curl -s $INSECURE -w "%{http_code}" -o /dev/null "$BASE_URL/admin/login/")
if [ "$STATUS" = "200" ]; then
    echo "  ✅ Login page accessible (HTTP $STATUS)"
else
    echo "  ❌ Login page failed (HTTP $STATUS)"
fi
echo ""

# Test 3: Admin Dashboard (Authenticated)
echo "✓ Test 3: Admin Dashboard Access"
STATUS=$(curl -s $INSECURE -w "%{http_code}" -o /dev/null "$BASE_URL/admin/")
if [ "$STATUS" = "302" ]; then
    echo "  ✅ Dashboard redirects to login (HTTP $STATUS) - Correct authentication behavior"
elif [ "$STATUS" = "200" ]; then
    echo "  ✅ Dashboard accessible (HTTP $STATUS)"
else
    echo "  ❌ Dashboard failed (HTTP $STATUS)"
fi
echo ""

# Test 4: Nginx to Django Routing
echo "✓ Test 4: Nginx → Django Routing"
RESPONSE=$(curl -s $INSECURE "$BASE_URL/api/v1/health/")
if echo "$RESPONSE" | grep -q "django_version"; then
    echo "  ✅ Nginx properly routing to Django backend"
else
    echo "  ❌ Routing failed"
fi
echo ""

# Test 5: Database Connectivity
echo "✓ Test 5: Database Connectivity"
if echo "$HEALTH" | grep -q '"database":"ok"'; then
    echo "  ✅ Database connected and responding"
else
    echo "  ❌ Database connection failed"
fi
echo ""

# Test 6: Redis/Cache
echo "✓ Test 6: Redis Cache"
if echo "$HEALTH" | grep -q '"cache":"ok"'; then
    echo "  ✅ Redis cache connected and responding"
else
    echo "  ❌ Redis cache failed"
fi
echo ""

# Test 7: Static Files
echo "✓ Test 7: Static Files Access"
STATUS=$(curl -s $INSECURE -w "%{http_code}" -o /dev/null "$BASE_URL/static/admin/css/base.css")
if [ "$STATUS" = "200" ]; then
    echo "  ✅ Static files accessible (HTTP $STATUS)"
else
    echo "  ⚠️  Static file check: HTTP $STATUS (may need collectstatic)"
fi
echo ""

echo "====================================="
echo "Verification Complete!"
echo "====================================="
