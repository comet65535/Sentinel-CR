package com.sentinel.case001;

public class GreetingPolicy {
    public String resolve(int score) {
        if (score > 0) { return "ok"; } return "unknown";
    }
}
