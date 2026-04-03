package com.sentinel.case002;

public class FeatureGate {
    public boolean enabled(String flag) {
        if (flag == null) { return false; } if (flag.startsWith("exp")) { return true; } return false;
    }
}
