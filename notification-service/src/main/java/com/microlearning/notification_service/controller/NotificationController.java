package com.microlearning.notification_service.controller;
import com.microlearning.notification_service.model.Notification;
import com.microlearning.notification_service.service.NotificationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/notifications")
public class NotificationController {

    @Autowired
    private NotificationService notificationService;

    // ==== ENDPOINTS CRUD BASIQUES =====

    // 1. POST /api/notifications - Créer une notification
    @PostMapping
    public ResponseEntity<Notification> createNotification(@RequestBody Notification notification) {
        Notification saved = notificationService.sendNotification(notification);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    // 2. POST /api/notifications/send - Alternative (comme dans le rapport)
    @PostMapping("/send")
    public ResponseEntity<Notification> sendNotification(@RequestBody Notification notification) {
        Notification saved = notificationService.sendNotification(notification);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    // 3. GET /api/notifications/{id} - Récupérer une notification par ID
    @GetMapping("/{id}")
    public ResponseEntity<Notification> getNotification(@PathVariable Long id) {
        return notificationService.getNotificationById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    // 4. GET /api/notifications/user/{userId} - Historique (comme dans le rapport)
    @GetMapping("/user/{userId}")
    public ResponseEntity<List<Notification>> getUserNotifications(@PathVariable String userId) {
        List<Notification> notifications = notificationService.getUserNotifications(userId);
        return ResponseEntity.ok(notifications);
    }

    // 5. GET /api/notifications/user/{userId}/unread - Notifications non lues
    @GetMapping("/user/{userId}/unread")
    public ResponseEntity<List<Notification>> getUnreadNotifications(@PathVariable String userId) {
        List<Notification> notifications = notificationService.getUnreadNotifications(userId);
        return ResponseEntity.ok(notifications);
    }

    // 6. PUT /api/notifications/{id}/read - Marquer comme lue
    @PutMapping("/{id}/read")
    public ResponseEntity<Notification> markAsRead(@PathVariable Long id) {
        Notification updated = notificationService.markAsRead(id);
        if (updated != null) {
            return ResponseEntity.ok(updated);
        }
        return ResponseEntity.notFound().build();
    }

    // 7. DELETE /api/notifications/{id} - Supprimer une notification
    @DeleteMapping("/{id}")
    public ResponseEntity<String> deleteNotification(@PathVariable Long id) {
        boolean deleted = notificationService.deleteNotification(id);
        if (deleted) {
            return ResponseEntity.ok("Notification supprimée avec succès");
        }
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body("Notification non trouvée");
    }

    // ==== ENDPOINTS UTILITAIRES =====

    // 8. GET /api/notifications/health - Health check
    @GetMapping("/health")
    public ResponseEntity<String> healthCheck() {
        return ResponseEntity.ok("Notification Service is UP and RUNNING on port 8082");
    }

    // 9. GET /api/notifications/stats/user/{userId} - Statistiques
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

    // 10. POST /api/notifications/quick - Création rapide avec paramètres
    @PostMapping("/quick")
    public ResponseEntity<Notification> quickCreate(
            @RequestParam String userId,
            @RequestParam String type,
            @RequestParam String title,
            @RequestParam String message) {

        Notification notification = notificationService.createNotification(userId, type, title, message);
        return ResponseEntity.status(HttpStatus.CREATED).body(notification);
    }

    // 11. GET /api/notifications/test - Test simple
    @GetMapping("/test")
    public ResponseEntity<String> test() {
        return ResponseEntity.ok("Notification Service fonctionne !");
    }

    // 12. GET /api/notifications/all - Toutes les notifications (pour debug)
    @GetMapping("/all")
    public ResponseEntity<List<Notification>> getAllNotifications() {
        // Note: Dans un vrai service, on limiterait l'accès
        List<Notification> all = notificationService.getUserNotifications("dummy");
        return ResponseEntity.ok(all);
    }
}