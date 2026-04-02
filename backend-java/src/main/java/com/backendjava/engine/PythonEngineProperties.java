package com.backendjava.engine;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "sentinel.ai")
public class PythonEngineProperties {
    private String mode = "mock";
    private String pythonBaseUrl = "http://localhost:8000";
    private int pythonConnectTimeoutMs = 3000;
    private int pythonReadTimeoutMs = 0;

    public String getMode() {
        return mode;
    }

    public void setMode(String mode) {
        this.mode = mode;
    }

    public String getPythonBaseUrl() {
        return pythonBaseUrl;
    }

    public void setPythonBaseUrl(String pythonBaseUrl) {
        this.pythonBaseUrl = pythonBaseUrl;
    }

    public int getPythonConnectTimeoutMs() {
        return pythonConnectTimeoutMs;
    }

    public void setPythonConnectTimeoutMs(int pythonConnectTimeoutMs) {
        this.pythonConnectTimeoutMs = pythonConnectTimeoutMs;
    }

    public int getPythonReadTimeoutMs() {
        return pythonReadTimeoutMs;
    }

    public void setPythonReadTimeoutMs(int pythonReadTimeoutMs) {
        this.pythonReadTimeoutMs = pythonReadTimeoutMs;
    }
}
