package com.microlearning.analytics_service.model;

import java.util.Map;

public class UserStats {
    private String userId;
    private int totalLessonsCompleted;
    private int totalQuizzesTaken;
    private double averageQuizScore;
    private String lastLessonCompleted;

    // Constructeurs
    public UserStats() {}

    public UserStats(String userId, int totalLessonsCompleted, int totalQuizzesTaken, double averageQuizScore) {
        this.userId = userId;
        this.totalLessonsCompleted = totalLessonsCompleted;
        this.totalQuizzesTaken = totalQuizzesTaken;
        this.averageQuizScore = averageQuizScore;
    }

    // Getters et Setters
    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }

    public int getTotalLessonsCompleted() { return totalLessonsCompleted; }
    public void setTotalLessonsCompleted(int totalLessonsCompleted) { this.totalLessonsCompleted = totalLessonsCompleted; }

    public int getTotalQuizzesTaken() { return totalQuizzesTaken; }
    public void setTotalQuizzesTaken(int totalQuizzesTaken) { this.totalQuizzesTaken = totalQuizzesTaken; }

    public double getAverageQuizScore() { return averageQuizScore; }
    public void setAverageQuizScore(double averageQuizScore) { this.averageQuizScore = averageQuizScore; }

    public String getLastLessonCompleted() { return lastLessonCompleted; }
    public void setLastLessonCompleted(String lastLessonCompleted) { this.lastLessonCompleted = lastLessonCompleted; }
}