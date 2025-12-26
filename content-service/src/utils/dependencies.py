from fastapi import Depends, HTTPException, status
from models.schemas import UserResponse, UserRole

# For testing purposes - simulate authentication
# In production, integrate with your authentication service

def get_current_user() -> UserResponse:
    """Simulate getting current user for testing"""
    # This is a mock function for testing
    # In production, implement JWT validation or integration with user-service
    return UserResponse(
        id="user-123",
        email="teacher@example.com",
        first_name="John",
        last_name="Doe",
        role=UserRole.TEACHER
    )