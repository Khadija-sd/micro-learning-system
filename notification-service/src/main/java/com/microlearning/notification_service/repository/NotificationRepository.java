package com.microlearning.notification_service.repository;

import com.microlearning.notification_service.model.Notification;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;

@Repository
public interface NotificationRepository extends JpaRepository<Notification, Long> {

    // Trouver toutes les notifications d'un utilisateur
    List<Notification> findByUserId(String userId);

    // Trouver les notifications non lues
    List<Notification> findByUserIdAndRead(String userId, boolean read);

    // Compter les notifications non lues
    int countByUserIdAndRead(String userId, boolean read);
}