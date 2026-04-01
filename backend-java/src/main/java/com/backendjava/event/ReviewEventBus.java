package com.backendjava.event;

import java.util.concurrent.ConcurrentHashMap;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

@Component
public class ReviewEventBus {
    private final ConcurrentHashMap<String, Sinks.Many<ReviewEvent>> taskEventSinks = new ConcurrentHashMap<>();

    public void initializeTaskStream(String taskId) {
        taskEventSinks.computeIfAbsent(taskId, ignored -> Sinks.many().replay().all());
    }

    public void publish(ReviewEvent event) {
        Sinks.Many<ReviewEvent> sink =
                taskEventSinks.computeIfAbsent(event.taskId(), ignored -> Sinks.many().replay().all());
        sink.emitNext(event, Sinks.EmitFailureHandler.FAIL_FAST);
    }

    public Flux<ReviewEvent> streamForTask(String taskId) {
        Sinks.Many<ReviewEvent> sink = taskEventSinks.get(taskId);
        if (sink == null) {
            return Flux.error(new ResponseStatusException(HttpStatus.NOT_FOUND, "task not found: " + taskId));
        }
        return sink.asFlux();
    }

    public void completeTaskStream(String taskId) {
        Sinks.Many<ReviewEvent> sink = taskEventSinks.get(taskId);
        if (sink != null) {
            sink.emitComplete(Sinks.EmitFailureHandler.FAIL_FAST);
        }
    }
}
