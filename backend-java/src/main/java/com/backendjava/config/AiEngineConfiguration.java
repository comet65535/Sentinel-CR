package com.backendjava.config;

import com.backendjava.engine.AiEngineAdapter;
import com.backendjava.engine.EngineEventMapper;
import com.backendjava.engine.MockAiEngineAdapter;
import com.backendjava.engine.PythonAiEngineAdapter;
import com.backendjava.engine.PythonEngineProperties;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(PythonEngineProperties.class)
public class AiEngineConfiguration {

    @Bean
    @ConditionalOnProperty(prefix = "sentinel.ai", name = "mode", havingValue = "python")
    public AiEngineAdapter pythonAiEngineAdapter(
            PythonEngineProperties properties, EngineEventMapper eventMapper) {
        return new PythonAiEngineAdapter(properties, eventMapper);
    }

    @Bean
    @ConditionalOnProperty(prefix = "sentinel.ai", name = "mode", havingValue = "mock")
    public AiEngineAdapter mockAiEngineAdapter() {
        return new MockAiEngineAdapter();
    }
}
