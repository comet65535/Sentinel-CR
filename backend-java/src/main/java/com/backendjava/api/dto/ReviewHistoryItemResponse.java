package com.backendjava.api.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;

public record ReviewHistoryItemResponse(
        @JsonProperty("task_id") String taskId,
        @JsonProperty("status") String status,
        @JsonProperty("created_at") Instant createdAt,
        @JsonProperty("updated_at") Instant updatedAt,
        @JsonProperty("title") String title,
        @JsonProperty("input_kind") String inputKind,
        @JsonProperty("summary") ReviewHistorySummary summary,
        @JsonProperty("has_patch") boolean hasPatch) {

    public record ReviewHistorySummary(
            @JsonProperty("final_status") String finalStatus,
            @JsonProperty("verified_level") String verifiedLevel,
            @JsonProperty("failure_taxonomy") ReviewHistoryFailureTaxonomy failureTaxonomy) {
    }

    public record ReviewHistoryFailureTaxonomy(@JsonProperty("bucket") String bucket) {
    }
}
