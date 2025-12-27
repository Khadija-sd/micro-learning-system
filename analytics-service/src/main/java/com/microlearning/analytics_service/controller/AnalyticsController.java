package com.microlearning.analytics_service.controller;

import com.microlearning.analytics_service.model.Progress;
import com.microlearning.analytics_service.model.UserStats;
import com.microlearning.analytics_service.service.AnalyticsService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import org.springframework.http.HttpStatus;
import java.util.Optional;

@RestController
@RequestMapping("/api/analytics")
public class AnalyticsController {

    @Autowired
    private AnalyticsService analyticsService;

    // ==== ENDPOINTS CRUD =====

    // 1. POST /api/analytics/progress - Créer/Enregistrer une progression
    @PostMapping("/progress")
    public ResponseEntity<Progress> createProgress(@RequestBody Progress progress) {
        Progress savedProgress = analyticsService.recordProgress(progress);
        return ResponseEntity.status(HttpStatus.CREATED).body(savedProgress);
    }

    // 2. GET /api/analytics/progress/{id} - Récupérer une progression par ID
    @GetMapping("/progress/{id}")
    public ResponseEntity<Progress> getProgressById(@PathVariable Long id) {
        Optional<Progress> progress = analyticsService.getProgressById(id);
        return progress.map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    // 3. GET /api/analytics/user/{userId}/progress - Récupérer toutes les progressions d'un utilisateur
    @GetMapping("/user/{userId}/progress")
    public ResponseEntity<List<Progress>> getUserProgress(@PathVariable String userId) {
        List<Progress> progressList = analyticsService.getUserProgress(userId);
        return ResponseEntity.ok(progressList);
    }

    // 4. DELETE /api/analytics/progress/{id} - Supprimer une progression
    @DeleteMapping("/progress/{id}")
    public ResponseEntity<String> deleteProgress(@PathVariable Long id) {
        boolean deleted = analyticsService.deleteProgress(id);
        if (deleted) {
            return ResponseEntity.ok("Progression supprimée avec succès");
        }
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body("Progression non trouvée");
    }

    // 5. PUT /api/analytics/progress/{id}/score - Mettre à jour le score d'un quiz
    @PutMapping("/progress/{id}/score")
    public ResponseEntity<Progress> updateQuizScore(@PathVariable Long id, @RequestParam Integer score) {
        Progress updated = analyticsService.updateQuizScore(id, score);
        if (updated != null) {
            return ResponseEntity.ok(updated);
        }
        return ResponseEntity.notFound().build();
    }

    // ==== ENDPOINTS SPÉCIFIQUES (du rapport) =====

    // 6. GET /api/analytics/stats/{userId} - Statistiques utilisateur (EXIGÉ par le rapport)
    @GetMapping("/stats/{userId}")
    public ResponseEntity<UserStats> getUserStats(@PathVariable String userId) {
        UserStats stats = analyticsService.getUserStats(userId);
        return ResponseEntity.ok(stats);
    }

    // 7. POST /api/analytics/progress (avec query params) - Alternative
    @PostMapping("/record")
    public ResponseEntity<Progress> recordProgress(
            @RequestParam String userId,
            @RequestParam String lessonId,
            @RequestParam String lessonTitle,
            @RequestParam boolean completed,
            @RequestParam(required = false) Integer quizScore) {

        Progress progress = new Progress(userId, lessonId, lessonTitle, completed, quizScore);
        Progress saved = analyticsService.recordProgress(progress);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    // ==== ENDPOINTS UTILITAIRES =====

    // Health check
    @GetMapping("/health")
    public ResponseEntity<String> healthCheck() {
        return ResponseEntity.ok("Analytics Service is UP and RUNNING on port 8083");
    }

    // Hello World test
    @GetMapping("/hello")
    public ResponseEntity<String> hello() {
        return ResponseEntity.ok("Hello from Analytics Microservice!");
    }

    // Version
    @GetMapping("/version")
    public ResponseEntity<String> version() {
        return ResponseEntity.ok("Analytics Service v1.0.0");
    }
}