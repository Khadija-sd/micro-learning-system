package com.microlearning.analytics_service.service;

import com.microlearning.analytics_service.model.Progress;
import com.microlearning.analytics_service.model.UserStats;
import com.microlearning.analytics_service.repository.ProgressRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.util.List;
import java.util.Optional;

@Service
public class AnalyticsService {

    @Autowired
    private ProgressRepository progressRepository;

    // 1. Enregistrer une progression
    public Progress recordProgress(Progress progress) {
        // Vérifier si cette progression existe déjà
        List<Progress> existing = progressRepository.findByUserIdAndLessonId(
                progress.getUserId(),
                progress.getLessonId()
        );

        if (!existing.isEmpty()) {
            // Mettre à jour l'entrée existante
            Progress existingProgress = existing.get(0);
            existingProgress.setCompleted(progress.isCompleted());
            existingProgress.setQuizScore(progress.getQuizScore());
            existingProgress.setLessonTitle(progress.getLessonTitle());
            return progressRepository.save(existingProgress);
        }

        // Sinon, créer une nouvelle entrée
        return progressRepository.save(progress);
    }

    // 2. Récupérer une progression par ID
    public Optional<Progress> getProgressById(Long id) {
        return progressRepository.findById(id);
    }

    // 3. Récupérer toutes les progressions d'un utilisateur
    public List<Progress> getUserProgress(String userId) {
        return progressRepository.findByUserId(userId);
    }

    // 4. Supprimer une progression
    public boolean deleteProgress(Long id) {
        if (progressRepository.existsById(id)) {
            progressRepository.deleteById(id);
            return true;
        }
        return false;
    }

    // 5. Récupérer les statistiques d'un utilisateur
    public UserStats getUserStats(String userId) {
        List<Progress> userProgress = progressRepository.findByUserId(userId);

        int totalLessonsCompleted = progressRepository.countByUserIdAndCompleted(userId, true);

        int totalQuizzesTaken = (int) userProgress.stream()
                .filter(p -> p.getQuizScore() != null)
                .count();

        double averageScore = userProgress.stream()
                .filter(p -> p.getQuizScore() != null)
                .mapToInt(Progress::getQuizScore)
                .average()
                .orElse(0.0);

        // Trouver la dernière leçon complétée
        String lastLesson = userProgress.stream()
                .filter(Progress::isCompleted)
                .sorted((p1, p2) -> p2.getCompletedAt().compareTo(p1.getCompletedAt()))
                .findFirst()
                .map(Progress::getLessonTitle)
                .orElse("Aucune leçon complétée");

        UserStats stats = new UserStats(userId, totalLessonsCompleted, totalQuizzesTaken, averageScore);
        stats.setLastLessonCompleted(lastLesson);

        return stats;
    }

    // 6. Mettre à jour le score d'un quiz
    public Progress updateQuizScore(Long progressId, Integer newScore) {
        Optional<Progress> optionalProgress = progressRepository.findById(progressId);
        if (optionalProgress.isPresent()) {
            Progress progress = optionalProgress.get();
            progress.setQuizScore(newScore);
            return progressRepository.save(progress);
        }
        return null;
    }
}