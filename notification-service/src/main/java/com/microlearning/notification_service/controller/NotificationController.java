package com.microlearning.notification_service.controller;

import com.microlearning.notification_service.model.Notification;
import com.microlearning.notification_service.service.NotificationService;
import io.dapr.Topic;
import io.dapr.client.DaprClient;
import io.dapr.client.DaprClientBuilder;
import io.dapr.client.domain.CloudEvent;
import io.dapr.client.domain.HttpExtension;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import jakarta.annotation.PostConstruct;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    @Autowired
    private NotificationService notificationService;

    private final DaprClient daprClient = new DaprClientBuilder().build();

    // =========================
    // INITIALISATION DAPR
    // =========================

    @PostConstruct
    public void initDaprSubscriptions() {
        System.out.println("🔔 Initialisation des abonnements Dapr...");
        
        try {
            System.out.println("📡 Abonnements Dapr configurés:");
            System.out.println("   - quiz_completed → /api/notifications/events/quiz-completed");
            System.out.println("   - course_created → /api/notifications/events/course-created");
            
            if (daprClient != null) {
                System.out.println("✅ DaprClient initialisé avec succès");
                
                // Tester la connexion Dapr
                try {
                    // Publier un événement test
                    Map<String, Object> testEvent = new HashMap<>();
                    testEvent.put("test", "initialisation");
                    testEvent.put("timestamp", System.currentTimeMillis());
                    
                    daprClient.publishEvent("pubsub", "dapr_init_test", testEvent).block();
                    System.out.println("📤 Événement test Dapr publié");
                } catch (Exception e) {
                    System.out.println("⚠️  Impossible de publier événement test: " + e.getMessage());
                }
            } else {
                System.out.println("❌ DaprClient non initialisé");
            }
        } catch (Exception e) {
            System.out.println("❌ Erreur initialisation Dapr: " + e.getMessage());
            e.printStackTrace();
        }
        
        System.out.println("🎯 NotificationController prêt à recevoir les événements Dapr");
    }

    // =========================
    // ENDPOINTS CRUD BASIQUES
    // =========================

    @PostMapping
    public ResponseEntity<Notification> createNotification(@RequestBody Notification notification) {
        Notification saved = notificationService.sendNotification(notification);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @PostMapping("/send")
    public ResponseEntity<Notification> sendNotification(@RequestBody Notification notification) {
        Notification saved = notificationService.sendNotification(notification);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Notification> getNotification(@PathVariable Long id) {
        return notificationService.getNotificationById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/user/{userId}")
    public ResponseEntity<List<Notification>> getUserNotifications(@PathVariable String userId) {
        List<Notification> notifications = notificationService.getUserNotifications(userId);
        return ResponseEntity.ok(notifications);
    }

    @GetMapping("/user/{userId}/unread")
    public ResponseEntity<List<Notification>> getUnreadNotifications(@PathVariable String userId) {
        List<Notification> notifications = notificationService.getUnreadNotifications(userId);
        return ResponseEntity.ok(notifications);
    }

    @PutMapping("/{id}/read")
    public ResponseEntity<Notification> markAsRead(@PathVariable Long id) {
        Notification updated = notificationService.markAsRead(id);
        if (updated != null) {
            return ResponseEntity.ok(updated);
        }
        return ResponseEntity.notFound().build();
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<String> deleteNotification(@PathVariable Long id) {
        boolean deleted = notificationService.deleteNotification(id);
        if (deleted) {
            return ResponseEntity.ok("Notification supprimée avec succès");
        }
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body("Notification non trouvée");
    }

    @GetMapping("/health")
    public ResponseEntity<String> healthCheck() {
        return ResponseEntity.ok("Notification Service is UP and RUNNING on port 8082");
    }

    @GetMapping("/stats/user/{userId}")
    public ResponseEntity<Map<String, Object>> getUserStats(@PathVariable String userId) {
        List<Notification> all = notificationService.getUserNotifications(userId);
        int unreadCount = notificationService.countUnreadNotifications(userId);

        Map<String, Object> stats = new HashMap<>();
        stats.put("userId", userId);
        stats.put("totalNotifications", all.size());
        stats.put("unreadCount", unreadCount);
        stats.put("readCount", all.size() - unreadCount);

        return ResponseEntity.ok(stats);
    }

    @PostMapping("/quick")
    public ResponseEntity<Notification> quickCreate(
            @RequestParam String userId,
            @RequestParam String type,
            @RequestParam String title,
            @RequestParam String message) {

        Notification notification = notificationService.createNotification(userId, type, title, message);
        return ResponseEntity.status(HttpStatus.CREATED).body(notification);
    }

    @GetMapping("/test")
    public ResponseEntity<String> test() {
        return ResponseEntity.ok("Notification Service fonctionne !");
    }

    @GetMapping("/all")
    public ResponseEntity<List<Notification>> getAllNotifications() {
        List<Notification> all = notificationService.getUserNotifications("dummy");
        return ResponseEntity.ok(all);
    }

    // =========================
    // ENDPOINTS DAPR
    // =========================

    @Topic(name = "quiz_completed", pubsubName = "pubsub")
    @PostMapping(path = "/events/quiz-completed")
    public Mono<ResponseEntity<String>> handleQuizCompleted(
            @RequestBody(required = false) CloudEvent<Map<String, Object>> cloudEvent) {
        return Mono.fromSupplier(() -> {
            try {
                System.out.println("📨 Événement Dapr reçu: quiz_completed");
                
                if (cloudEvent == null) {
                    System.out.println("⚠️  CloudEvent est null");
                    return ResponseEntity.badRequest().body("CloudEvent manquant");
                }
                
                Map<String, Object> data = cloudEvent.getData();
                
                if (data == null) {
                    System.out.println("⚠️  Données de l'événement manquantes");
                    return ResponseEntity.badRequest().body("Données manquantes");
                }
                
                System.out.println("📦 Données reçues: " + data);

                String quizId = (String) data.get("quiz_id");
                String userId = (String) data.get("user_id");
                Double score = data.get("score") != null ? 
                    Double.valueOf(data.get("score").toString()) : 0.0;
                Boolean passed = data.get("passed") != null ? 
                    Boolean.valueOf(data.get("passed").toString()) : false;

                System.out.println("👤 Création notification pour: " + userId);
                System.out.println("📊 Score: " + score + ", Réussi: " + passed);

                Notification notification = new Notification();
                notification.setUserId(userId);
                notification.setType("QUIZ_RESULT");
                notification.setTitle("Résultat du Quiz");
                
                String message = passed ?
                        String.format("✅ Félicitations! Vous avez réussi le quiz avec un score de %.1f%%", score) :
                        String.format("⚠️ Quiz terminé avec un score de %.1f%%. Continuez à réviser!", score);
                
                notification.setMessage(message);
                notification.setRead(false);

                Notification saved = notificationService.sendNotification(notification);
                System.out.println("✅ Notification créée: ID=" + saved.getId());

                return ResponseEntity.ok("Événement traité avec succès");

            } catch (Exception e) {
                System.out.println("❌ Erreur traitement événement quiz_completed: " + e.getMessage());
                e.printStackTrace();
                return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                        .body("Erreur traitement événement: " + e.getMessage());
            }
        });
    }

    @Topic(name = "course_created", pubsubName = "pubsub")
    @PostMapping(path = "/events/course-created")
    public Mono<ResponseEntity<String>> handleCourseCreated(
            @RequestBody(required = false) CloudEvent<Map<String, Object>> cloudEvent) {
        return Mono.fromSupplier(() -> {
            try {
                System.out.println("📨 Événement Dapr reçu: course_created");
                
                if (cloudEvent == null) {
                    System.out.println("⚠️  CloudEvent est null");
                    return ResponseEntity.badRequest().body("CloudEvent manquant");
                }
                
                Map<String, Object> data = cloudEvent.getData();
                
                if (data == null) {
                    System.out.println("⚠️  Données de l'événement manquantes");
                    return ResponseEntity.badRequest().body("Données manquantes");
                }
                
                System.out.println("📦 Données reçues: " + data);

                String courseId = (String) data.get("course_id");
                String teacherId = (String) data.get("teacher_id");
                String title = (String) data.get("title");
                Integer microLessonsCount = data.get("micro_lessons_count") != null ? 
                    Integer.valueOf(data.get("micro_lessons_count").toString()) : 0;

                System.out.println("👨‍🏫 Création notification pour professeur: " + teacherId);
                System.out.println("📚 Cours: " + title + ", Leçons: " + microLessonsCount);

                Notification profNotification = new Notification();
                profNotification.setUserId(teacherId);
                profNotification.setType("COURSE_READY");
                profNotification.setTitle("Cours Transformé");
                profNotification.setMessage(String.format(
                        "Votre cours '%s' a été transformé en %d micro-leçons. Il est maintenant disponible pour les étudiants.",
                        title, microLessonsCount
                ));
                profNotification.setRead(false);

                Notification saved = notificationService.sendNotification(profNotification);
                System.out.println("✅ Notification créée: ID=" + saved.getId());

                return ResponseEntity.ok("Événement traité avec succès");

            } catch (Exception e) {
                System.out.println("❌ Erreur traitement événement course_created: " + e.getMessage());
                e.printStackTrace();
                return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                        .body("Erreur traitement événement: " + e.getMessage());
            }
        });
    }

    @GetMapping("/dapr/subscribe")
    public ResponseEntity<List<Map<String, String>>> getSubscriptions() {
        System.out.println("📡 Dapr demande les abonnements...");
        
        List<Map<String, String>> subscriptions = List.of(
                Map.of(
                        "pubsubname", "pubsub",
                        "topic", "quiz_completed",
                        "route", "/api/notifications/events/quiz-completed"
                ),
                Map.of(
                        "pubsubname", "pubsub",
                        "topic", "course_created",
                        "route", "/api/notifications/events/course-created"
                )
        );
        
        System.out.println("✅ Abonnements retournés: " + subscriptions);
        return ResponseEntity.ok(subscriptions);
    }

    @PostMapping("/test/publish")
    public ResponseEntity<String> testPublish() {
        try {
            System.out.println("🧪 Test de publication Dapr...");
            
            Map<String, Object> eventData = new HashMap<>();
            eventData.put("quiz_id", "test-quiz-123");
            eventData.put("user_id", "test-user-456");
            eventData.put("score", 85.5);
            eventData.put("passed", true);
            eventData.put("timestamp", java.time.Instant.now().toString());

            daprClient.publishEvent("pubsub", "quiz_completed", eventData).block();

            System.out.println("✅ Événement de test publié avec succès");
            return ResponseEntity.ok("Événement de test publié avec succès");

        } catch (Exception e) {
            System.out.println("❌ Erreur publication test: " + e.getMessage());
            e.printStackTrace();
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Erreur publication test: " + e.getMessage());
        }
    }

    @GetMapping("/test/invoke/{service}")
    public ResponseEntity<String> testInvoke(@PathVariable String service) {
        try {
            System.out.println("🔗 Test d'invocation Dapr vers: " + service);
            
            String methodName = "health";
            String result = daprClient.invokeMethod(
                    service,
                    methodName,
                    null,
                    HttpExtension.GET,
                    String.class
            ).block();

            System.out.println("✅ Résultat: " + result);
            return ResponseEntity.ok("Résultat de l'appel à " + service + ": " + result);

        } catch (Exception e) {
            System.out.println("❌ Erreur invocation: " + e.getMessage());
            e.printStackTrace();
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Erreur invocation: " + e.getMessage());
        }
    }

    @GetMapping("/debug/dapr")
    public ResponseEntity<Map<String, Object>> debugDapr() {
        System.out.println("🔍 Debug Dapr...");
        
        Map<String, Object> debugInfo = new HashMap<>();
        debugInfo.put("daprClient", daprClient != null ? "initialisé" : "null");
        debugInfo.put("timestamp", System.currentTimeMillis());
        debugInfo.put("endpoints", List.of(
            "/api/notifications/dapr/subscribe",
            "/api/notifications/events/quiz-completed",
            "/api/notifications/events/course-created"
        ));
        
        return ResponseEntity.ok(debugInfo);
    }
}