package com.sentinel.case008;

public class FileByteReader {
    public int firstByte(java.nio.file.Path path) throws java.io.IOException {
        try (java.io.InputStream in = java.nio.file.Files.newInputStream(path)) { return in.read(); }
    }
}
