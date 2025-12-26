import re
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from collections import Counter
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TransformationService:
    """Service de transformation de contenu en micro-leçons"""
    
    def __init__(self):
        # Télécharger les ressources NLTK
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('punkt')
            nltk.download('stopwords')
        
        self.stopwords = set(stopwords.words(['english', 'french']))
        self.words_per_minute = 200  # Vitesse lecture moyenne
    
    def split_into_micro_lessons(self, content: str, duration_minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Découper un contenu en micro-leçons de durée spécifiée
        
        Args:
            content: Texte à découper
            duration_minutes: Durée cible par micro-leçon (défaut: 5)
            
        Returns:
            Liste de micro-leçons avec titre, contenu, durée estimée
        """
        logger.info(f"Découpage de contenu ({len(content)} caractères) en micro-leçons de {duration_minutes} min")
        
        # Calcul du nombre de mots cible
        target_words = duration_minutes * self.words_per_minute
        
        # 1. Nettoyer et normaliser le contenu
        content = self._clean_content(content)
        
        # 2. Séparer en paragraphes significatifs
        paragraphs = self._split_into_paragraphs(content)
        
        # 3. Regrouper les paragraphes en micro-leçons
        micro_lessons = []
        current_lesson = {
            "paragraphs": [],
            "word_count": 0,
            "sentences": []
        }
        
        for paragraph in paragraphs:
            para_words = len(word_tokenize(paragraph))
            
            # Si l'ajout dépasse la cible, créer une nouvelle leçon
            if current_lesson["word_count"] + para_words > target_words and current_lesson["paragraphs"]:
                lesson = self._create_lesson_from_data(current_lesson, len(micro_lessons) + 1)
                micro_lessons.append(lesson)
                
                # Réinitialiser pour la prochaine leçon
                current_lesson = {
                    "paragraphs": [],
                    "word_count": 0,
                    "sentences": []
                }
            
            # Ajouter le paragraphe à la leçon courante
            current_lesson["paragraphs"].append(paragraph)
            current_lesson["word_count"] += para_words
            
            # Extraire les phrases pour générer un titre
            sentences = sent_tokenize(paragraph)
            current_lesson["sentences"].extend(sentences)
        
        # Ajouter la dernière leçon si elle contient du contenu
        if current_lesson["paragraphs"]:
            lesson = self._create_lesson_from_data(current_lesson, len(micro_lessons) + 1)
            micro_lessons.append(lesson)
        
        logger.info(f"✅ Créé {len(micro_lessons)} micro-leçons")
        return micro_lessons
    
    def _clean_content(self, content: str) -> str:
        """Nettoyer et normaliser le contenu"""
        # Supprimer les espaces multiples
        content = re.sub(r'\s+', ' ', content)
        
        # Normaliser les sauts de ligne
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        return content.strip()
    
    def _split_into_paragraphs(self, content: str) -> List[str]:
        """Diviser le contenu en paragraphes significatifs"""
        # Séparer par doubles sauts de ligne
        raw_paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        # Fusionner les paragraphes trop courts
        paragraphs = []
        current_para = ""
        
        for para in raw_paragraphs:
            if len(word_tokenize(para)) < 50:  # Paragraphe trop court
                current_para += " " + para if current_para else para
            else:
                if current_para:
                    paragraphs.append(current_para)
                    current_para = ""
                paragraphs.append(para)
        
        if current_para:
            paragraphs.append(current_para)
        
        return paragraphs
    
    def _create_lesson_from_data(self, lesson_data: Dict, order: int) -> Dict[str, Any]:
        """Créer un dictionnaire de micro-leçon à partir des données"""
        # Générer un titre à partir de la première phrase significative
        title = self._generate_title(lesson_data["sentences"])
        
        # Calculer la durée estimée
        estimated_minutes = max(1, round(lesson_data["word_count"] / self.words_per_minute))
        
        # Construire le contenu
        content = "\n\n".join(lesson_data["paragraphs"])
        
        return {
            "title": f"Leçon {order}: {title}",
            "content": content,
            "estimated_minutes": estimated_minutes,
            "word_count": lesson_data["word_count"],
            "order": order,
            "keywords": self.extract_keywords(content, top_n=5)
        }
    
    def _generate_title(self, sentences: List[str]) -> str:
        """Générer un titre à partir des premières phrases"""
        if not sentences:
            return "Micro-Leçon"
        
        # Prendre la première phrase significative
        for sentence in sentences:
            if len(word_tokenize(sentence)) > 5:  # Au moins 5 mots
                # Tronquer si nécessaire
                if len(sentence) > 80:
                    return sentence[:77] + "..."
                return sentence
        
        return sentences[0][:80] + "..." if len(sentences[0]) > 80 else sentences[0]
    
    def extract_keywords(self, content: str, top_n: int = 10) -> List[str]:
        """Extraire les mots-clés principaux d'un contenu"""
        # Tokenizer et nettoyer
        words = word_tokenize(content.lower())
        words = [w for w in words if w.isalpha() and len(w) > 3]
        
        # Filtrer les stopwords
        words = [w for w in words if w not in self.stopwords]
        
        # Compter les fréquences
        word_counts = Counter(words)
        
        return [word for word, _ in word_counts.most_common(top_n)]
    
    def generate_summary(self, content: str, max_sentences: int = 3) -> str:
        """Générer un résumé du contenu"""
        sentences = sent_tokenize(content)
        
        if len(sentences) <= max_sentences:
            return " ".join(sentences)
        
        # Sélectionner les premières phrases (simplifié)
        return " ".join(sentences[:max_sentences]) + "..."
    
    def generate_quiz_questions(self, content: str, num_questions: int = 5) -> List[Dict[str, Any]]:
        """Générer des questions de quiz à partir du contenu"""
        sentences = sent_tokenize(content)
        
        if len(sentences) < num_questions:
            num_questions = len(sentences)
        
        questions = []
        used_sentences = set()
        
        for i in range(num_questions):
            # Trouver une phrase non utilisée
            sentence = None
            for s in sentences:
                if s not in used_sentences and len(word_tokenize(s)) > 6:
                    sentence = s
                    used_sentences.add(s)
                    break
            
            if not sentence:
                break
            
            # Générer une question simple
            question = self._generate_question_from_sentence(sentence, i+1)
            if question:
                questions.append(question)
        
        return questions
    
    def _generate_question_from_sentence(self, sentence: str, number: int) -> Dict[str, Any]:
        """Générer une question à partir d'une phrase"""
        # Simplifié pour l'exemple
        keywords = [w for w in word_tokenize(sentence) 
                   if w.isalpha() and len(w) > 4 and w.lower() not in self.stopwords]
        
        if not keywords:
            return None
        
        main_keyword = keywords[0] if keywords else "concept"
        
        return {
            "text": f"Question {number}: Expliquez le concept de '{main_keyword}' dans ce contexte",
            "options": [
                "Un élément technique essentiel",
                "Une notion secondaire", 
                "Un principe fondamental",
                "Un détail sans importance"
            ],
            "correct_answer": "Un élément technique essentiel",
            "points": 1,
            "explanation": f"Le concept '{main_keyword}' est central pour comprendre ce contenu."
        }

# Instance globale
transformation_service = TransformationService()