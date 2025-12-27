package com.microlearning.notification_service.service;

import com.microlearning.notification_service.model.Notification;
import com.microlearning.notification_service.repository.NotificationRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.util.List;
import java.util.Optional;

@Service
public class NotificationService {

    @Autowired
    private NotificationRepository notificationRepository;

    // 1. Envoyer/Créer une notification
    public Notification sendNotification(Notification notification) {
        return notificationRepository.save(notification);
    }

    // 2. Récupérer une notification par ID
    public Optional<Notification> getNotificationById(Long id) {
        return notificationRepository.findById(id);
    }

    // 3. Récupérer toutes les notifications d'un utilisateur
    public List<Notification> getUserNotifications(String userId) {
        return notificationRepository.findByUserId(userId);
    }

    // 4. Récupérer les notifications non lues
    public List<Notification> getUnreadNotifications(String userId) {
        return notificationRepository.findByUserIdAndRead(userId, false);
    }

    // 5. Marquer comme lue
    public Notification markAsRead(Long id) {
        Optional<Notification> optional = notificationRepository.findById(id);
        if (optional.isPresent()) {
            Notification notification = optional.get();
            notification.setRead(true);
            return notificationRepository.save(notification);
        }
        return null;
    }

    // 6. Supprimer une notification
    public boolean deleteNotification(Long id) {
        if (notificationRepository.existsById(id)) {
            notificationRepository.deleteById(id);
            return true;
        }
        return false;
    }

    // 7. Compter les notifications non lues
    public int countUnreadNotifications(String userId) {
        return notificationRepository.countByUserIdAndRead(userId, false);
    }

    // 8. Créer une notification avec paramètres simples
    public Notification createNotification(String userId, String type, String title, String message) {
        Notification notification = new Notification(userId, type, title, message);
        return notificationRepository.save(notification);
    }
}