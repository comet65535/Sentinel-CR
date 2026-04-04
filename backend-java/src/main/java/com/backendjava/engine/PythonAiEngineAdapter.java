package com.backendjava.engine;

import com.backendjava.task.ReviewTask;
import io.netty.channel.ChannelOption;
import java.time.Duration;
import java.util.Map;
import org.springframework.http.MediaType;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.netty.http.client.HttpClient;

public class PythonAiEngineAdapter implements AiEngineAdapter {
    private final WebClient webClient;
    private final EngineEventMapper eventMapper;

    public PythonAiEngineAdapter(PythonEngineProperties properties, EngineEventMapper eventMapper) {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, properties.getPythonConnectTimeoutMs());
        if (properties.getPythonReadTimeoutMs() > 0) {
            httpClient = httpClient.responseTimeout(Duration.ofMillis(properties.getPythonReadTimeoutMs()));
        }

        this.webClient = WebClient.builder()
                .baseUrl(properties.getPythonBaseUrl())
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .build();
        this.eventMapper = eventMapper;
    }

    @Override
    public Flux<EngineEvent> startReview(ReviewTask task) {
        Map<String, Object> metadata = task.getMetadata();
        if (metadata.isEmpty()) {
            metadata = Map.of(
                    "requestedBy", "backend-java",
                    "debug", false);
        }

        PythonReviewRunRequest requestBody = new PythonReviewRunRequest(
                task.getTaskId(),
                task.getConversationId(),
                task.getMessageId(),
                task.getParentMessageId(),
                task.getMessageText(),
                task.getCodeText(),
                task.getLanguage(),
                task.getSourceType(),
                task.getOptions(),
                metadata);

        return webClient.post()
                .uri("/internal/reviews/run")
                .contentType(MediaType.APPLICATION_JSON)
                .accept(MediaType.APPLICATION_NDJSON)
                .bodyValue(requestBody)
                .retrieve()
                .onStatus(
                        status -> status.isError(),
                        clientResponse -> clientResponse
                                .bodyToMono(String.class)
                                .defaultIfEmpty("")
                                .map(responseBody -> new IllegalStateException(
                                        "python engine returned HTTP "
                                                + clientResponse.statusCode().value()
                                                + (responseBody.isBlank() ? "" : (": " + responseBody)))))
                .bodyToFlux(PythonEngineEvent.class)
                .map(event -> eventMapper.fromPythonEvent(task.getTaskId(), event))
                .switchIfEmpty(Flux.error(new IllegalStateException("python engine returned empty event stream")));
    }
}
