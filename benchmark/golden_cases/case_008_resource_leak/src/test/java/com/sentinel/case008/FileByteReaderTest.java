package com.sentinel.case008;

import org.junit.jupiter.api.Test;

public class FileByteReaderTest {
    @Test
    void shouldMatchGoldenExpectation() throws Exception {
        java.nio.file.Path p = java.nio.file.Files.createTempFile("golden",".txt"); java.nio.file.Files.writeString(p, "A"); org.junit.jupiter.api.Assertions.assertEquals(65, new FileByteReader().firstByte(p));
    }
}
