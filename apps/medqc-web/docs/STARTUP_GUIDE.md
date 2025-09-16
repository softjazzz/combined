# MedQC Frontend & Backend Startup Guide

> 🏥 Complete startup guide for Medical Quality Control System (MedQC) frontend and backend services

## 📋 Table of Contents
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Detailed Steps](#detailed-steps)
- [Port Configuration](#port-configuration)
- [Troubleshooting](#troubleshooting)
- [Health Checks](#health-checks)

## 🔧 Requirements

### Frontend Environment
- **Node.js**: >= 18.0.0
- **pnpm**: >= 8.0.0
- **OS**: Linux/macOS/Windows

### Backend Environment
- **Python**: >= 3.10
- **Virtual Environment**: venv or conda
- **Database**: Supabase (PostgreSQL)

## 🚀 Quick Start

### One-Command Startup
```bash
# Execute in project root
cd /home/ubuntu/coding/health-qc-monorepo

# Start frontend (port 3000)
pnpm dev:medqc

# Start backend (port 8001) - in new terminal
cd apps/medqc-web/backend
source venv/bin/activate
export JWT_SECRET=dev-secret
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## 📝 Detailed Steps

### 1. Frontend Startup

#### Method 1: Using pnpm scripts (Recommended)
```bash
# In project root
cd /home/ubuntu/coding/health-qc-monorepo

# Start medqc-web frontend
pnpm dev:medqc
```

#### Method 2: Direct startup
```bash
# Enter frontend directory
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web

# Install dependencies (first run)
pnpm install

# Start development server
pnpm dev --host 0.0.0.0 --port 3000
```

#### Frontend Success Indicators
```
  VITE v6.0.5  ready in 1234 ms

  ➜  Local:   http://localhost:3000/
  ➜  Network: http://0.0.0.0:3000/
  ➜  press h + enter to show help
```

### 2. Backend Startup

#### Step-by-Step Process
```bash
# 1. Enter backend directory
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend

# 2. Activate virtual environment
source venv/bin/activate

# 3. Set environment variables (required)
export JWT_SECRET=dev-secret

# 4. Start FastAPI service
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

#### Backend Success Indicators
```
INFO:     Will watch for changes in these directories: ['/home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend']
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process [481778] using WatchFiles
INFO:     Started server process [481781]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

#### Dependencies Check Success
```
2025-09-16 11:04:44,134 - app.core.supabase_client - INFO - Supabase REST compatible client ready: https://dgsdkdbjpucyawnyfbdu.supabase.co/
```

## 🌐 Port Configuration

| Service | Port | Purpose | Access URL |
|---------|------|---------|------------|
| **Frontend** | 3000 | Vue 3 Dev Server | http://localhost:3000 |
| **Backend** | 8001 | FastAPI Server | http://localhost:8001 |
| **API Docs** | 8001 | Swagger UI | http://localhost:8001/docs |
| **Health Check** | 8001 | Service Status | http://localhost:8001/api/health |

### Important Notes
- ⚠️ **Backend must use port 8001**, not 8000
- Frontend API configuration points to port 8001
- Using wrong port will break frontend-backend communication

## 🔍 Health Checks

### Frontend Health Check
```bash
# Check if frontend responds normally
curl -s http://localhost:3000 | head -5

# Expected output: HTML page content
# <!DOCTYPE html>
# <html lang="zh-CN">
#   <head>
#     <script type="module" src="/@vite/client"></script>
```

### Backend Health Check
```bash
# Check backend health status
curl -s http://localhost:8001/api/health

# Expected output:
# {
#   "status": "healthy",
#   "timestamp": "2025-09-16T03:04:45.045093Z",
#   "version": "1.0.0",
#   "dependencies": {
#     "supabase": true,
#     "llm": true
#   },
#   "env": "development"
# }
```

### Process Check
```bash
# Check frontend process
ps aux | grep vite | grep -v grep

# Check backend process  
ps aux | grep uvicorn | grep -v grep

# Check port usage
netstat -tlnp | grep -E "(3000|8001)"
```

## ❗ Troubleshooting

### 1. Backend Startup Failures

#### Issue: `python: command not found`
```bash
# Solution: Activate virtual environment
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend
source venv/bin/activate
```

#### Issue: `ModuleNotFoundError: No module named 'fastapi'`
```bash
# Solution: Ensure dependencies are installed in virtual environment
source venv/bin/activate
pip install -r requirements.txt
```

#### Issue: JWT_SECRET not set
```bash
# Solution: Set environment variable
export JWT_SECRET=dev-secret
```

### 2. Frontend Startup Failures

#### Issue: Port already in use
```bash
# Find process using port
lsof -i :3000

# Kill the process
kill -9 <PID>
```

#### Issue: Dependency installation failed
```bash
# Clear cache and reinstall
rm -rf node_modules
pnpm install
```

### 3. Frontend-Backend Communication Issues

#### Issue: API calls failing
- Confirm backend is running on **port 8001**
- Check frontend API configuration points to correct port
- Verify backend health check passes

#### Issue: CORS errors
- Backend has CORS configured, this shouldn't occur
- If it does, check backend CORS configuration

### 4. Supabase Connection Issues

#### Warning: `Supabase client initialization failed`
```
2025-09-16 11:04:44,133 - app.core.supabase_client - WARNING - Supabase client initialization failed: 'dict' object has no attribute 'headers'
```
- This is a normal warning, system automatically falls back to REST compatible client
- Does not affect functionality

## 🔄 Restarting Services

### Frontend Restart
```bash
# Ctrl+C to stop current service, then restart
pnpm dev:medqc
```

### Backend Restart
```bash
# Ctrl+C to stop current service, then restart
cd /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend
source venv/bin/activate
export JWT_SECRET=dev-secret
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Force Stop Services
```bash
# Find and stop all related processes
pkill -f "vite.*3000"
pkill -f "uvicorn.*8001"
```

## 📊 Service Monitoring

### Real-time Log Viewing
```bash
# Frontend logs: View in startup terminal
# Backend logs: View in startup terminal or log file
tail -f /home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/backend/backend.log
```

### Performance Monitoring
```bash
# Check resource usage
top -p $(pgrep -f "vite|uvicorn")
```

## 🎯 Development Tips

1. **Use multiple terminals**: Run frontend and backend in separate terminals
2. **Keep services running**: Maintain continuous service operation during development
3. **Regular health checks**: Monitor service status using health check endpoints
4. **Check logs**: Review console logs when issues occur
5. **Environment variables**: Always set JWT_SECRET when starting backend

## 📞 Technical Support

If you encounter startup issues:
1. Check the troubleshooting section in this document
2. Review console error logs
3. Verify environment requirements are met
4. Contact development team for support

---

**Last Updated**: 2025-09-16  
**Document Version**: v1.0.0  
**Maintainer**: MedQC Development Team
