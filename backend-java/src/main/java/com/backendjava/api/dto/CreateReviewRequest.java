package com.backendjava.api.dto;

import jakarta.validation.constraints.NotBlank;

public class CreateReviewRequest {
    @NotBlank
    private String codeText;

    @NotBlank
    private String language;

    @NotBlank
    private String sourceType;

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
}
