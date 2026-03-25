package com.digitalbank.predictbackend;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.kafka.annotation.EnableKafka;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
@EnableAsync
public class PredictBackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(PredictBackendApplication.class, args);
    }
    @KafkaListener(topics = "predictions-ia-topic", groupId = "test-group")
    public void testRapide(String message) {
        System.out.println("🚀 FLASH : KAFKA FONCTIONNE ENFIN ! MESSAGE : " + message);
    }

}
