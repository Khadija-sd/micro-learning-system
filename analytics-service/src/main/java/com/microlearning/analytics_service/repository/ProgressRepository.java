package com.microlearning.analytics_service.repository;

import com.microlearning.analytics_service.model.Progress;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface ProgressRepository extends JpaRepository<Progress, Long> {

    // Trouver toutes les progressions d'un utilisateur
    List<Progress> findByUserId(String userId);

    // Trouver les leçons complétées par un utilisateur
    List<Progress> findByUserIdAndCompleted(String userId, boolean completed);

    // Compter les leçons complétées par un utilisateur
    int countByUserIdAndCompleted(String userId, boolean completed);

    // Trouver par userId et lessonId (pour éviter les doublons)
    List<Progress> findByUserIdAndLessonId(String userId, String lessonId);
}