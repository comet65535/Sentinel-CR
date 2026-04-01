package com.backendjava.task;

import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Repository;

@Repository
public class InMemoryTaskRepository {
    private final ConcurrentHashMap<String, ReviewTask> tasks = new ConcurrentHashMap<>();

    public ReviewTask save(ReviewTask task) {
        tasks.put(task.getTaskId(), task);
        return task;
    }

    public Optional<ReviewTask> findByTaskId(String taskId) {
        return Optional.ofNullable(tasks.get(taskId));
    }

    public boolean existsByTaskId(String taskId) {
        return tasks.containsKey(taskId);
    }
}
