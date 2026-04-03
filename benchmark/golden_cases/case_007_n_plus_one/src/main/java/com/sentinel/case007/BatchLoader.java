package com.sentinel.case007;

public class BatchLoader {
    public int batchSize(java.util.List<Integer> ids) {
        java.util.Map<Integer, Integer> cache = new java.util.HashMap<>(); for (Integer id : ids) { cache.put(id, id); } return cache.size();
    }
}
