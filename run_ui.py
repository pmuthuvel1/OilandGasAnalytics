"""UI Server for Oil & Gas Analytics - Runs on port 8001"""

import os
import json
import httpx
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import get_config

config = get_config()

# Create FastAPI app for UI
app = FastAPI(title="Oil & Gas Analytics UI")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_BASE_URL = f"http://localhost:{config.API_PORT}"


# HTML Templates
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Oil & Gas Analytics Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
        }
        
        header {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            border-bottom: 2px solid #00d4ff;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        }
        
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        h1 {
            color: #00d4ff;
            font-size: 28px;
            font-weight: 600;
        }
        
        .status {
            display: flex;
            gap: 15px;
            align-items: center;
        }
        
        .status-badge {
            background: #00d4ff;
            color: #1a1a2e;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        
        .container {
            max-width: 1400px;
            margin: 30px auto;
            padding: 0 20px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(0, 212, 255, 0.2);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }
        
        .card h2 {
            color: #00d4ff;
            font-size: 20px;
            margin-bottom: 15px;
            border-bottom: 1px solid rgba(0, 212, 255, 0.3);
            padding-bottom: 10px;
        }
        
        .input-group {
            margin-bottom: 15px;
        }
        
        label {
            display: block;
            margin-bottom: 5px;
            color: #00d4ff;
            font-weight: 500;
        }
        
        input, textarea, select {
            width: 100%;
            padding: 10px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(0, 212, 255, 0.3);
            border-radius: 4px;
            color: #eee;
            font-family: inherit;
        }
        
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #00d4ff;
            background: rgba(0, 212, 255, 0.1);
        }
        
        button {
            background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%);
            color: #1a1a2e;
            border: none;
            padding: 12px 30px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            transition: all 0.3s ease;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.3);
        }
        
        button:active {
            transform: translateY(0);
        }
        
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }
        
        .results {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .result-item {
            background: rgba(0, 212, 255, 0.1);
            border: 1px solid rgba(0, 212, 255, 0.5);
            border-radius: 6px;
            padding: 15px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .result-item:hover {
            background: rgba(0, 212, 255, 0.15);
            border-color: #00d4ff;
        }
        
        .result-item h3 {
            color: #00d4ff;
            margin-bottom: 8px;
            font-size: 16px;
        }
        
        .result-item p {
            color: #aaa;
            font-size: 12px;
            margin: 4px 0;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .spinner {
            border: 3px solid rgba(0, 212, 255, 0.2);
            border-top: 3px solid #00d4ff;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .error {
            background: rgba(255, 100, 100, 0.1);
            border: 1px solid rgba(255, 100, 100, 0.5);
            color: #ff6464;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 15px;
        }
        
        .success {
            background: rgba(100, 255, 100, 0.1);
            border: 1px solid rgba(100, 255, 100, 0.5);
            color: #64ff64;
            padding: 15px;
            border-radius: 4px;
            margin-bottom: 15px;
        }
        
        .tab-buttons {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 1px solid rgba(0, 212, 255, 0.2);
        }
        
        .tab-btn {
            background: transparent;
            color: #aaa;
            border: none;
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            transition: all 0.3s ease;
        }
        
        .tab-btn.active {
            color: #00d4ff;
            border-bottom-color: #00d4ff;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        code {
            background: rgba(0, 0, 0, 0.3);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        
        pre {
            background: rgba(0, 0, 0, 0.5);
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            border: 1px solid rgba(0, 212, 255, 0.2);
            margin-top: 10px;
        }
        
        footer {
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 12px;
            margin-top: 50px;
        }
    </style>
</head>
<body>
    <header>
        <div class="header-content">
            <h1>🛢️ Oil & Gas Analytics Dashboard</h1>
            <div class="status">
                <span class="status-badge">Multi-Agent AI System</span>
                <span id="api-status" class="status-badge">Checking...</span>
            </div>
        </div>
    </header>
    
    <div class="container">
        <div class="tab-buttons">
            <button class="tab-btn active" onclick="switchTab('analysis')">Analysis</button>
            <button class="tab-btn" onclick="switchTab('history')">History</button>
            <button class="tab-btn" onclick="switchTab('tools')">Tools</button>
            <button class="tab-btn" onclick="switchTab('info')">Info</button>
        </div>
        
        <!-- Analysis Tab -->
        <div id="analysis" class="tab-content active">
            <div class="card">
                <h2>Submit Analysis Request</h2>
                <div id="message"></div>
                
                <div class="input-group">
                    <label>Well Name *</label>
                    <input type="text" id="wellName" placeholder="e.g., Well-001">
                </div>
                
                <div class="input-group">
                    <label>Analysis Type</label>
                    <select id="analysisType">
                        <option value="full">Full Analysis (All Agents)</option>
                        <option value="quick">Quick Analysis (Risk Only)</option>
                    </select>
                </div>
                
                <div class="input-group">
                    <label>Seismic Data (JSON)</label>
                    <textarea id="seismicData" placeholder='{"amplitude_values": [1.2, 3.4, ...], "depth_values": [...]}'></textarea>
                </div>
                
                <div class="input-group">
                    <label>Well Log Data (JSON)</label>
                    <textarea id="wellLogData" placeholder='{"gamma_ray": [...], "resistivity": [...], "porosity": [...]}'></textarea>
                </div>
                
                <div class="input-group">
                    <label>Additional Notes</label>
                    <textarea id="userNotes" placeholder="Add any relevant notes..."></textarea>
                </div>
                
                <div class="button-group">
                    <button onclick="submitAnalysis()">Submit Analysis</button>
                    <button onclick="loadExampleData()" style="background: rgba(0, 212, 255, 0.3);">Load Example Data</button>
                </div>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p style="margin-top: 15px; color: #00d4ff;">Processing your analysis...</p>
                </div>
            </div>
            
            <div id="resultsContainer"></div>
        </div>
        
        <!-- History Tab -->
        <div id="history" class="tab-content">
            <div class="card">
                <h2>Analysis History</h2>
                <button onclick="fetchHistory()">Refresh History</button>
                <div id="historyContainer" style="margin-top: 20px;"></div>
            </div>
        </div>
        
        <!-- Tools Tab -->
        <div id="tools" class="tab-content">
            <div class="card">
                <h2>Available Analysis Tools</h2>
                <div id="toolsContainer"></div>
            </div>
        </div>
        
        <!-- Info Tab -->
        <div id="info" class="tab-content">
            <div class="card">
                <h2>System Information</h2>
                <div id="infoContainer"></div>
            </div>
        </div>
    </div>
    
    <footer>
        <p>Oil & Gas Analytics Multi-Agent System | Powered by LangGraph | API: localhost:8000 | UI: localhost:8001</p>
    </footer>
    
    <script>
        const API_URL = 'http://localhost:8000';
        
        async function checkAPIHealth() {
            try {
                const response = await fetch(`${API_URL}/health`);
                const data = await response.json();
                document.getElementById('api-status').textContent = '✓ API Online';
                document.getElementById('api-status').style.background = '#00ff00';
            } catch (e) {
                document.getElementById('api-status').textContent = '✗ API Offline';
                document.getElementById('api-status').style.background = '#ff6464';
            }
        }
        
        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            
            // Load content
            if (tabName === 'history') fetchHistory();
            if (tabName === 'tools') fetchTools();
            if (tabName === 'info') fetchInfo();
        }
        
        async function submitAnalysis() {
            const wellName = document.getElementById('wellName').value;
            if (!wellName) {
                showMessage('Please enter a well name', 'error');
                return;
            }
            
            showLoading(true);
            
            try {
                const analysisData = {
                    well_name: wellName,
                    analysis_type: document.getElementById('analysisType').value,
                    seismic_data: document.getElementById('seismicData').value ? JSON.parse(document.getElementById('seismicData').value) : null,
                    well_log_data: document.getElementById('wellLogData').value ? JSON.parse(document.getElementById('wellLogData').value) : null,
                    user_notes: document.getElementById('userNotes').value
                };
                
                const response = await fetch(`${API_URL}/analyze`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(analysisData)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showMessage(`Analysis submitted successfully! Workflow ID: ${result.workflow_id}`, 'success');
                    displayResults(result);
                    // Clear form
                    document.getElementById('wellName').value = '';
                    document.getElementById('seismicData').value = '';
                    document.getElementById('wellLogData').value = '';
                    document.getElementById('userNotes').value = '';
                } else {
                    showMessage(`Error: ${result.detail || 'Unknown error'}`, 'error');
                }
            } catch (e) {
                showMessage(`Error: ${e.message}`, 'error');
            } finally {
                showLoading(false);
            }
        }
        
        function loadExampleData() {
            document.getElementById('wellName').value = 'Example-Well-001';
            document.getElementById('seismicData').value = JSON.stringify({
                "amplitude_values": [0.5, 1.2, 2.3, 1.8, 0.9, 3.2, 1.5, 0.7, 2.1],
                "depth_values": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800],
                "frequency_content": {"low": 0.3, "mid": 0.5, "high": 0.2}
            }, null, 2);
            document.getElementById('wellLogData').value = JSON.stringify({
                "gamma_ray": [80, 75, 120, 100, 90, 70, 85],
                "resistivity": [50, 120, 30, 150, 45, 110, 55],
                "porosity": [18, 22, 8, 25, 15, 20, 19],
                "depth_values": [2000, 2100, 2200, 2300, 2400, 2500, 2600]
            }, null, 2);
        }
        
        function displayResults(result) {
            const container = document.getElementById('resultsContainer');
            container.innerHTML = `
                <div class="card">
                    <h2>Analysis Results</h2>
                    <div class="results">
                        <div class="result-item">
                            <h3>Workflow ID</h3>
                            <p><code>${result.workflow_id}</code></p>
                        </div>
                        <div class="result-item">
                            <h3>Status</h3>
                            <p>${result.status}</p>
                        </div>
                        <div class="result-item">
                            <h3>Timestamp</h3>
                            <p>${new Date(result.timestamp).toLocaleString()}</p>
                        </div>
                    </div>
                    <div style="margin-top: 20px;">
                        <h3 style="color: #00d4ff; margin-bottom: 10px;">Full Response</h3>
                        <pre>${JSON.stringify(result, null, 2)}</pre>
                    </div>
                </div>
            `;
        }
        
        async function fetchHistory() {
            try {
                const response = await fetch(`${API_URL}/workflows/history`);
                const data = await response.json();
                
                const container = document.getElementById('historyContainer');
                if (data.recent_workflows.length === 0) {
                    container.innerHTML = '<p>No workflows executed yet.</p>';
                    return;
                }
                
                container.innerHTML = data.recent_workflows.map((w, i) => `
                    <div class="result-item">
                        <h3>Workflow ${i + 1}</h3>
                        <p>ID: <code>${w.workflow_id}</code></p>
                        <p>Status: ${w.status}</p>
                    </div>
                `).join('');
            } catch (e) {
                document.getElementById('historyContainer').innerHTML = `<div class="error">Failed to fetch history: ${e.message}</div>`;
            }
        }
        
        async function fetchTools() {
            try {
                const response = await fetch(`${API_URL}/tools`);
                const data = await response.json();
                
                const container = document.getElementById('toolsContainer');
                let html = `<p><strong>Total Tools:</strong> ${data.total_tools}</p>`;
                
                for (const [category, tools] of Object.entries(data.categories)) {
                    html += `<h3 style="color: #00d4ff; margin-top: 15px; margin-bottom: 8px;">${category}</h3>`;
                    html += `<ul style="margin-left: 20px;">`;
                    tools.forEach(tool => {
                        html += `<li>${tool}</li>`;
                    });
                    html += `</ul>`;
                }
                
                container.innerHTML = html;
            } catch (e) {
                document.getElementById('toolsContainer').innerHTML = `<div class="error">Failed to fetch tools: ${e.message}</div>`;
            }
        }
        
        async function fetchInfo() {
            try {
                const response = await fetch(`${API_URL}/info`);
                const data = await response.json();
                
                const container = document.getElementById('infoContainer');
                container.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
            } catch (e) {
                document.getElementById('infoContainer').innerHTML = `<div class="error">Failed to fetch info: ${e.message}</div>`;
            }
        }
        
        function showMessage(msg, type) {
            const messageDiv = document.getElementById('message');
            messageDiv.innerHTML = `<div class="${type}">${msg}</div>`;
            setTimeout(() => {
                messageDiv.innerHTML = '';
            }, 5000);
        }
        
        function showLoading(show) {
            document.getElementById('loading').style.display = show ? 'block' : 'none';
        }
        
        // Initialize
        checkAPIHealth();
        setInterval(checkAPIHealth, 30000);
    </script>
</body>
</html>
"""


# Endpoints
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the main dashboard"""
    return DASHBOARD_HTML


@app.get("/health")
async def health_check():
    """Check API health"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/health", timeout=5.0)
            return {"status": "healthy", "api": response.json()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.get("/api/proxy/{path:path}")
async def proxy_api(path: str):
    """Proxy API calls (for CORS handling)"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/{path}")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=config.HOST,
        port=config.UI_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
