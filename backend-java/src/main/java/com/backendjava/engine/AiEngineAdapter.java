package com.backendjava.engine;

import com.backendjava.task.ReviewTask;
import reactor.core.publisher.Flux;

public interface AiEngineAdapter {
    Flux<EngineEvent> startReview(ReviewTask task);
}
