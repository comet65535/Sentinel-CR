package com.sentinel.case003;

public class Greeter {
    public String greet(boolean formal) {
        String prefix = "Hi"; if (formal) { prefix = "Dear"; } return prefix + " user";
    }
}
