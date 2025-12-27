package com.microlearning.analytics_service.model;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "user_progress")
public class Progress {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private String userId;

    @Column(name = "lesson_id", nullable = false)
    private String lessonId;

    @Column(name = "lesson_title")
    private String lessonTitle;

    @Column(name = "completed")
    private boolean completed = false;

    @Column(name = "quiz_score")
    private Integer quizScore;

    @Column(name = "completed_at")
    private LocalDateTime completedAt;

    // Constructeurs
    public Progress() {
        this.completedAt = LocalDateTime.now();
    }

    public Progress(String userId, String lessonId, String lessonTitle, boolean completed, Integer quizScore) {
        this.userId = userId;
        this.lessonId = lessonId;
        this.lessonTitle = lessonTitle;
        this.completed = completed;
        this.quizScore = quizScore;
        this.completedAt = LocalDateTime.now();
    }

    // Getters et Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }

    public String getLessonId() { return lessonId; }
    public void setLessonId(String lessonId) { this.lessonId = lessonId; }

    public String getLessonTitle() { return lessonTitle; }
    public void setLessonTitle(String lessonTitle) { this.lessonTitle = lessonTitle; }

    public boolean isCompleted() { return completed; }
    public void setCompleted(boolean completed) {
        this.completed = completed;
        if (completed) {
            this.completedAt = LocalDateTime.now();
        }
    }

    public Integer getQuizScore() { return quizScore; }
    public void setQuizScore(Integer quizScore) { this.quizScore = quizScore; }

    public LocalDateTime getCompletedAt() { return completedAt; }
    public void setCompletedAt(LocalDateTime completedAt) { this.completedAt = completedAt; }
}