package com.backendjava.api;

import com.backendjava.api.dto.CreateReviewRequest;
import com.backendjava.api.dto.CreateReviewResponse;
import com.backendjava.api.dto.ReviewHistoryItemResponse;
import com.backendjava.api.dto.ReviewTaskResponse;
import com.backendjava.event.ReviewEvent;
import com.backendjava.service.ReviewService;
import jakarta.validation.Valid;
import java.util.List;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestParam;
import reactor.core.publisher.Flux;

@RestController
@RequestMapping("/api/reviews")
public class ReviewController {
    private final ReviewService reviewService;

    public ReviewController(ReviewService reviewService) {
        this.reviewService = reviewService;
    }

    @PostMapping
    public CreateReviewResponse createReview(@Valid @RequestBody CreateReviewRequest request) {
        return reviewService.createReviewTask(request);
    }

    @GetMapping("/{taskId}")
    public ReviewTaskResponse getReviewTask(@PathVariable String taskId) {
        return reviewService.getTaskDetail(taskId);
    }

    @GetMapping
    public List<ReviewHistoryItemResponse> listReviewTasks(@RequestParam(defaultValue = "100") int limit) {
        return reviewService.listReviewTasks(limit);
    }

    @GetMapping("/conversations")
    public List<java.util.Map<String, Object>> listConversations(@RequestParam(defaultValue = "100") int limit) {
        return reviewService.listConversations(limit);
    }

    @GetMapping("/conversations/{conversationId}/messages")
    public List<java.util.Map<String, Object>> listConversationMessages(
            @PathVariable String conversationId,
            @RequestParam(defaultValue = "500") int limit) {
        return reviewService.listConversationMessages(conversationId, limit);
    }

    @GetMapping(value = "/{taskId}/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<ServerSentEvent<ReviewEvent>> streamReviewEvents(
            @PathVariable String taskId, ServerHttpResponse response) {
        response.getHeaders().setCacheControl("no-cache");
        return reviewService.streamTaskEvents(taskId)
                .map(event -> ServerSentEvent.<ReviewEvent>builder()
                        .id(String.valueOf(event.sequence()))
                        .event(event.eventType())
                        .data(event)
                        .build());
    }
}
