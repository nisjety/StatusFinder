#!/usr/bin/env python3
"""
Webhook handler for Discovery project.

This script sets up a FastAPI web server to handle webhook events and trigger spider jobs.
Supports environment validation, rate limiting, and secure configuration.
"""
import os
import json
import time
import hmac
import hashlib
import logging
import requests
import uvicorn
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger('webhook_handler')

# Environment validation
VALID_ENVIRONMENTS = ['development', 'staging', 'production']
ENVIRONMENT = os.getenv('DISCOVERY_ENV', 'development').lower()

if ENVIRONMENT not in VALID_ENVIRONMENTS:
    raise ValueError(
        f"Invalid environment: {ENVIRONMENT}. "
        f"Must be one of: {', '.join(VALID_ENVIRONMENTS)}"
    )

# Configuration
SCRAPYD_URL = os.getenv('SCRAPYD_URL', 'http://discovery-scrapyd:6800')
PROJECT_NAME = os.getenv('PROJECT_NAME', 'discovery')
DEFAULT_SPIDER = os.getenv('DEFAULT_SPIDER', 'quick')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
MAX_REQUESTS_PER_MINUTE = int(os.getenv('MAX_REQUESTS_PER_MINUTE', '60'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

# Initialize FastAPI app
app = FastAPI(
    title="Discovery Webhook Handler",
    description="Webhook handler for Discovery project",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RateLimiter:
    """Rate limiter implementation using token bucket algorithm"""
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_update = time.time()
        
    def update_tokens(self):
        now = time.time()
        time_passed = now - self.last_update
        self.tokens = min(
            self.max_requests,
            self.tokens + (time_passed * self.max_requests / self.time_window)
        )
        self.last_update = now
        
    def acquire(self) -> bool:
        self.update_tokens()
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
        
rate_limiter = RateLimiter(MAX_REQUESTS_PER_MINUTE)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Webhook endpoint
@app.post("/webhook")
async def handle_webhook(request: Request):
    """Handle incoming webhook requests"""
    # Rate limiting
    if not rate_limiter.acquire():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
    # Validate signature if webhook secret is set
    if WEBHOOK_SECRET:
        signature = request.headers.get('X-Hub-Signature')
        if not signature:
            raise HTTPException(status_code=400, detail="Missing signature")
            
        raw_body = await request.body()
        expected_signature = f"sha1={hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha1).hexdigest()}"
        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(status_code=403, detail="Invalid signature")
    
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
    # Extract spider name and settings from payload
    spider = payload.get('spider', DEFAULT_SPIDER)
    settings = payload.get('settings', {})
    
    try:
        # Schedule job with Scrapyd
        response = requests.post(
            f"{SCRAPYD_URL}/schedule.json",
            data={
                'project': PROJECT_NAME,
                'spider': spider,
                'settings': json.dumps(settings)
            },
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        job_data = response.json()
        
        if job_data.get('status') != 'ok':
            raise HTTPException(status_code=500, detail=f"Scrapyd error: {job_data.get('message', 'Unknown error')}")
            
        return {
            'status': 'ok',
            'job_id': job_data.get('jobid'),
            'spider': spider
        }
        
    except requests.RequestException as e:
        logger.error(f"Error scheduling job: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Error communicating with Scrapyd: {str(e)}")

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', '8000'))
    uvicorn.run(app, host='0.0.0.0', port=port)