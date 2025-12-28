import requests
import json
import time
import subprocess
import sys

def test_services():
    """Teste la connectivité entre les services dans Docker"""
    
    print("🔍 Test de connectivité entre services...")
    
    # Test 1: Vérifier que le content-service fonctionne
    try:
        print("\n1. Test du content-service...")
        response = requests.get("http://localhost:8001/health", timeout=5)
        print(f"✅ Content Service: {response.json()}")
    except Exception as e:
        print(f"❌ Content Service non accessible: {e}")
        return False
    
    # Test 2: Vérifier que le notification-service fonctionne
    try:
        print("\n2. Test du notification-service...")
        response = requests.get("http://localhost:8082/api/notifications/health", timeout=5)
        print(f"✅ Notification Service: {response.text}")
    except Exception as e:
        print(f"❌ Notification Service non accessible: {e}")
        return False
    
    # Test 3: Tester la publication d'un événement
    try:
        print("\n3. Test de publication d'événement quiz_completed...")
        
        # D'abord créer un cours (optionnel)
        course_data = {
            "title": "Test Course",
            "teacher_id": "test-teacher-123",
            "subject": "Mathematics"
        }
        response = requests.post("http://localhost:8001/course", 
                               json=course_data, 
                               timeout=10)
        
        if response.status_code == 200:
            course_id = response.json().get("id")
            print(f"✅ Cours créé: {course_id}")
            
            # Créer un quiz
            quiz_data = {
                "course_id": course_id,
                "title": "Test Quiz",
                "questions": [
                    {
                        "text": "Qu'est-ce que 2+2?",
                        "options": ["3", "4", "5", "6"],
                        "correct_answer": "4",
                        "points": 1
                    }
                ],
                "passing_score": 70
            }
            
            response = requests.post("http://localhost:8001/quiz", 
                                   json=quiz_data, 
                                   timeout=10)
            
            if response.status_code == 200:
                quiz_id = response.json().get("id")
                print(f"✅ Quiz créé: {quiz_id}")
                
                # Soumettre le quiz (cela devrait déclencher un événement Dapr)
                submission_data = {
                    "user_id": "test-student-456",
                    "answers": ["4"]
                }
                
                response = requests.post(f"http://localhost:8001/quiz/{quiz_id}/submit", 
                                       json=submission_data, 
                                       timeout=10)
                
                if response.status_code == 200:
                    print(f"✅ Quiz soumis: {response.json()}")
                    print("\n📤 Événement Dapr 'quiz_completed' devrait être publié...")
                    print("Vérifiez les logs du notification-service pour voir si la notification a été créée.")
                    return True
                else:
                    print(f"❌ Échec soumission quiz: {response.status_code}")
            else:
                print(f"❌ Échec création quiz: {response.status_code}")
        else:
            print(f"❌ Échec création cours: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erreur lors du test d'événement: {e}")
        import traceback
        traceback.print_exc()
    
    return False

def test_direct_dapr():
    """Test direct avec les API Dapr"""
    print("\n🔌 Test direct des API Dapr...")
    
    # Test 1: Vérifier l'état de Dapr pour content-service
    try:
        response = requests.get("http://localhost:3500/v1.0/health", timeout=5)
        print(f"✅ Dapr content-service: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Dapr content-service non accessible sur 3500, essayons 3500 sur content-service...")
    
    # Test 2: Vérifier l'état de Dapr pour notification-service
    try:
        response = requests.get("http://localhost:3501/v1.0/health", timeout=5)
        print(f"✅ Dapr notification-service: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Dapr notification-service non accessible sur 3501")
    
    # Test 3: Publier un événement directement via Dapr
    try:
        print("\n📨 Publication directe d'événement via Dapr...")
        event_data = {
            "quiz_id": "direct-test-quiz",
            "user_id": "direct-test-user",
            "score": 95.0,
            "passed": True,
            "timestamp": "2024-01-15T10:30:00Z"
        }
        
        response = requests.post(
            "http://localhost:3500/v1.0/publish/pubsub/quiz_completed",
            json=event_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code in [200, 204]:
            print("✅ Événement publié avec succès via Dapr")
            print("Attendez 5 secondes pour que la notification soit traitée...")
            time.sleep(5)
            
            # Vérifier si une notification a été créée
            try:
                response = requests.get(
                    "http://localhost:8082/api/notifications/user/direct-test-user",
                    timeout=5
                )
                if response.status_code == 200:
                    notifications = response.json()
                    print(f"📧 Notifications pour l'utilisateur: {len(notifications)} trouvées")
                    for notif in notifications:
                        print(f"  - {notif.get('title')}: {notif.get('message')}")
                else:
                    print("⚠️  Aucune notification trouvée")
            except Exception as e:
                print(f"⚠️  Erreur vérification notifications: {e}")
        else:
            print(f"❌ Échec publication événement: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Erreur publication Dapr: {e}")

def main():
    print("🚀 Test de connectivité Dapr entre Content et Notification Services")
    print("=" * 60)
    
    # Attendre que les services soient prêts
    print("⏳ Attente de 10 secondes pour que les services démarrent...")
    time.sleep(10)
    
    # Test basique des services
    if test_services():
        print("\n✅ Test des services réussi!")
    else:
        print("\n⚠️  Test des services partiellement réussi ou échoué")
    
    # Test direct Dapr
    test_direct_dapr()
    
    print("\n" + "=" * 60)
    print("📋 Pour vérifier manuellement:")
    print("1. Voir les logs du content-service:")
    print("   docker logs content-service")
    print("\n2. Voir les logs du notification-service:")
    print("   docker logs notification-service")
    print("\n3. Vérifier les événements Dapr:")
    print("   docker logs redis (pour voir l'activité Redis)")
    print("\n4. Tester l'API de publication:")
    print("   curl -X POST http://localhost:3500/v1.0/publish/pubsub/quiz_completed \\")
    print("     -H 'Content-Type: application/json' \\")
    print('     -d \'{"quiz_id":"test","user_id":"test","score":80,"passed":true}\'')

if __name__ == "__main__":
    main()