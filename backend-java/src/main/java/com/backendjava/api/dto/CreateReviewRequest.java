package com.backendjava.api.dto;

import jakarta.validation.constraints.NotBlank;
import java.util.Map;

public class CreateReviewRequest {
    @NotBlank
    private String codeText;

    @NotBlank
    private String language;

    @NotBlank
    private String sourceType;
    private Map<String, Object> options = Map.of();
    private Map<String, Object> metadata = Map.of();

    public String getCodeText() {
        return codeText;
    }

    public void setCodeText(String codeText) {
        this.codeText = codeText;
    }

    public String getLanguage() {
        return language;
    }

    public void setLanguage(String language) {
        this.language = language;
    }

    public String getSourceType() {
        return sourceType;
    }

    public void setSourceType(String sourceType) {
        this.sourceType = sourceType;
    }

    public Map<String, Object> getOptions() {
        return options;
    }

    public void setOptions(Map<String, Object> options) {
        this.options = options == null ? Map.of() : options;
    }

    public Map<String, Object> getMetadata() {
        return metadata;
    }

    public void setMetadata(Map<String, Object> metadata) {
        this.metadata = metadata == null ? Map.of() : metadata;
    }
}
