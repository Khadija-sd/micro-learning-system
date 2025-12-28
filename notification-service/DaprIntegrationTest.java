package com.microlearning.notification_service;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.*;
import org.springframework.test.context.ActiveProfiles;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
public class DaprIntegrationTest {

    @LocalServerPort
    private int port;

    @Autowired
    private TestRestTemplate restTemplate;

    private String getBaseUrl() {
        return "http://localhost:" + port + "/api/notifications";
    }

    @Test
    public void testHealthEndpoint() {
        System.out.println("🧪 Test Health Endpoint");
        
        ResponseEntity<String> response = restTemplate.getForEntity(
            getBaseUrl() + "/health", 
            String.class
        );
        
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("Notification Service is UP");
        
        System.out.println("✅ Health endpoint OK: " + response.getBody());
    }

    @Test
    public void testDaprSubscribeEndpoint() {
        System.out.println("🧪 Test Dapr Subscribe Endpoint");
        
        ResponseEntity<Object> response = restTemplate.getForEntity(
            getBaseUrl() + "/dapr/subscribe", 
            Object.class
        );
        
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        System.out.println("✅ Dapr subscribe endpoint OK");
        
        // Afficher les subscriptions
        System.out.println("Subscriptions: " + response.getBody());
    }

    @Test
    public void testEventHandlers() {
        System.out.println("🧪 Test Event Handlers");
        
        // Test quiz_completed event
        Map<String, Object> quizEvent = Map.of(
            "quiz_id", "test-java-quiz-001",
            "user_id", "test-java-user-001",
            "score", 91.5,
            "passed", true,
            "timestamp", java.time.Instant.now().toString()
        );
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(quizEvent, headers);
        
        ResponseEntity<String> response = restTemplate.postForEntity(
            getBaseUrl() + "/events/quiz-completed",
            request,
            String.class
        );
        
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        System.out.println("✅ Quiz completed event handler OK: " + response.getBody());
        
        // Test course_created event
        Map<String, Object> courseEvent = Map.of(
            "course_id", "test-java-course-001",
            "teacher_id", "test-java-teacher-001",
            "title", "Java Programming",
            "micro_lessons_count", 15,
            "timestamp", java.time.Instant.now().toString()
        );
        
        HttpEntity<Map<String, Object>> courseRequest = new HttpEntity<>(courseEvent, headers);
        
        ResponseEntity<String> courseResponse = restTemplate.postForEntity(
            getBaseUrl() + "/events/course-created",
            courseRequest,
            String.class
        );
        
        assertThat(courseResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        System.out.println("✅ Course created event handler OK: " + courseResponse.getBody());
    }

    @Test
    public void testTestPublishEndpoint() {
        System.out.println("🧪 Test Publish Test Endpoint");
        
        ResponseEntity<String> response = restTemplate.postForEntity(
            getBaseUrl() + "/test/publish",
            null,
            String.class
        );
        
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).contains("Événement de test publié");
        
        System.out.println("✅ Test publish endpoint OK: " + response.getBody());
    }

    @Test
    public void testNotificationCreation() {
        System.out.println("🧪 Test Notification Creation via Dapr Events");
        
        // Simuler un événement Dapr
        Map<String, Object> eventData = Map.of(
            "data", Map.of(
                "quiz_id", "integration-test-001",
                "user_id", "integration-user-001",
                "score", 87.0,
                "passed", true,
                "service", "content-service"
            ),
            "id", "test-event-id",
            "source", "content-service",
            "type", "quiz_completed",
            "specversion", "1.0"
        );
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(eventData, headers);
        
        ResponseEntity<String> response = restTemplate.postForEntity(
            getBaseUrl() + "/events/quiz-completed",
            request,
            String.class
        );
        
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        System.out.println("✅ Notification creation via Dapr event OK");
        
        // Vérifier qu'une notification a été créée
        ResponseEntity<String> notificationsResponse = restTemplate.getForEntity(
            getBaseUrl() + "/user/integration-user-001",
            String.class
        );
        
        if (notificationsResponse.getStatusCode() == HttpStatus.OK) {
            System.out.println("📊 Notifications pour l'utilisateur: " + notificationsResponse.getBody());
        }
    }
}