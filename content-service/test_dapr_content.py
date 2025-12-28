import requests
import json
import time
import sys

# Configuration
CONTENT_SERVICE_URL = "http://localhost:8001"
DAPR_PORT = "3500"

def test_health():
    """Test health endpoint"""
    print("=== Test Health ===")
    response = requests.get(f"{CONTENT_SERVICE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_dapr_subscribe():
    """Test Dapr subscription endpoint"""
    print("\n=== Test Dapr Subscribe ===")
    response = requests.get(f"{CONTENT_SERVICE_URL}/dapr/subscriptions")
    print(f"Status: {response.status_code}")
    print(f"Subscriptions: {response.json()}")
    
    subscriptions = response.json()
    has_quiz = any(sub['topic'] == 'quiz_completed' for sub in subscriptions)
    has_course = any(sub['topic'] == 'course_created' for sub in subscriptions)
    
    print(f"Has quiz_completed: {has_quiz}")
    print(f"Has course_created: {has_course}")
    
    return response.status_code == 200 and has_quiz and has_course

def test_publish_event_via_dapr():
    """Test publishing event via Dapr sidecar"""
    print("\n=== Test Publish Event via Dapr ===")
    
    event_data = {
        "quiz_id": "test-quiz-001",
        "user_id": "test-user-001",
        "score": 85.5,
        "passed": True,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    
    # Publier via le sidecar Dapr
    dapr_url = f"http://localhost:{DAPR_PORT}/v1.0/publish/pubsub/quiz_completed"
    
    try:
        response = requests.post(
            dapr_url,
            json=event_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Dapr Publish Status: {response.status_code}")
        print(f"Dapr Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Événement publié avec succès via Dapr")
            return True
        else:
            print("❌ Erreur lors de la publication")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_event_handler():
    """Test the event handler directly"""
    print("\n=== Test Event Handler Direct ===")
    
    event_data = {
        "quiz_id": "direct-test-001",
        "user_id": "direct-user-001",
        "score": 95.0,
        "passed": True
    }
    
    response = requests.post(
        f"{CONTENT_SERVICE_URL}/events/quiz-completed",
        json=event_data
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    return response.status_code == 200

def test_quiz_submission_with_dapr():
    """Test quiz submission that triggers Dapr event"""
    print("\n=== Test Quiz Submission (triggers Dapr) ===")
    
    # Créer d'abord un quiz de test
    quiz_data = {
        "course_id": "course-dapr-test",
        "title": "Test Dapr Quiz",
        "description": "Quiz pour tester l'intégration Dapr",
        "questions": [
            {
                "text": "Qu'est-ce que Dapr?",
                "options": ["Un langage", "Un runtime", "Une base de données", "Un framework"],
                "correct_answer": "Un runtime",
                "points": 1
            }
        ],
        "passing_score": 50
    }
    
    try:
        # Créer le quiz
        quiz_response = requests.post(
            f"{CONTENT_SERVICE_URL}/quiz",
            json=quiz_data
        )
        
        if quiz_response.status_code != 200:
            print("❌ Erreur création quiz")
            return False
            
        quiz_id = quiz_response.json().get("id")
        print(f"Quiz créé avec ID: {quiz_id}")
        
        # Soumettre le quiz (ceci devrait publier un événement Dapr)
        submission_data = {
            "user_id": "dapr-test-user",
            "answers": ["Un runtime"]
        }
        
        submission_response = requests.post(
            f"{CONTENT_SERVICE_URL}/quiz/{quiz_id}/submit",
            json=submission_data
        )
        
        print(f"Submission Status: {submission_response.status_code}")
        print(f"Submission Response: {submission_response.json()}")
        
        if submission_response.status_code == 200:
            print("✅ Quiz soumis avec succès")
            print("📤 Un événement Dapr devrait avoir été publié")
            return True
        else:
            print("❌ Erreur soumission quiz")
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def run_all_tests():
    """Run all Dapr tests"""
    print("🧪 Début des tests Dapr pour Content Service")
    print("=" * 50)
    
    results = []
    
    results.append(("Health Check", test_health()))
    time.sleep(1)
    
    results.append(("Dapr Subscribe", test_dapr_subscribe()))
    time.sleep(1)
    
    results.append(("Event Handler", test_event_handler()))
    time.sleep(1)
    
    results.append(("Dapr Publish", test_publish_event_via_dapr()))
    time.sleep(2)
    
    results.append(("Quiz Submission", test_quiz_submission_with_dapr()))
    
    # Afficher le résumé
    print("\n" + "=" * 50)
    print("📊 RÉSUMUM DES TESTS DAPR - CONTENT SERVICE")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 50)
    if all_passed:
        print("🎉 TOUS LES TESTS DAPR SONT PASSÉS!")
    else:
        print("⚠️  Certains tests ont échoué")
    
    return all_passed

if __name__ == "__main__":
    # Vérifier que le service est en cours d'exécution
    try:
        requests.get(f"{CONTENT_SERVICE_URL}/health", timeout=5)
    except:
        print("❌ Content Service n'est pas accessible sur localhost:8001")
        print("   Assurez-vous que le service est en cours d'exécution:")
        print("   python -m uvicorn app:app --host 0.0.0.0 --port 8001")
        sys.exit(1)
    
    success = run_all_tests()
    sys.exit(0 if success else 1)