"""
Sentence Builder & ASL Gloss-to-English Grammar Engine
Transforms raw streams of ASL signs and fingerspelled letters into coherent English sentences.
"""
import time
import logging
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SentenceBuilder")

class SentenceBuilder:
    # Rule-based idiomatic ASL gloss sequence restructuring
    GLOSS_PHRASE_PATTERNS = {
        ("HELLO",): "Hello, greetings!",
        ("HELLO", "HOW_ARE_YOU"): "Hello, how are you doing?",
        ("HOW_ARE_YOU",): "How are you doing?",
        ("THANK_YOU",): "Thank you very much.",
        ("PLEASE",): "Please.",
        ("YES",): "Yes, that is correct.",
        ("NO",): "No, thank you.",
        ("HELP",): "Please, I need help.",
        ("HELP", "PLEASE"): "Please, help me immediately.",
        ("WATER",): "I would like some water.",
        ("WATER", "PLEASE"): "Please give me some water.",
        ("FOOD",): "I need food.",
        ("FOOD", "PLEASE"): "Please give me some food.",
        ("DOCTOR",): "I need to see a doctor.",
        ("DOCTOR", "HELP"): "Medical emergency, please call a doctor!",
        ("FAMILY",): "This is my family.",
        ("I_LOVE_YOU",): "I love you.",
        ("GOOD_MORNING",): "Good morning to you.",
        ("PEACE",): "Peace and harmony.",
        ("GOODBYE",): "Goodbye, see you later."
    }

    def __init__(self, fingerspell_timeout_sec: float = 2.5):
        self.tokens: List[str] = []
        self.spelling_buffer: List[str] = []
        self.last_letter_time: float = 0.0
        self.fingerspell_timeout = fingerspell_timeout_sec

    def add_token(self, token: str) -> str:
        """
        Add new recognized sign. Automatically detects if it is a single-letter fingerspelling
        or an entire word/sign. Prevents accidental consecutive word repetition.
        
        Returns the current draft sentence string.
        """
        token = token.strip().upper()
        if not token or token in ["IDLE", "REST", "NONE", "UNKNOWN"]:
            return self.get_draft_sentence()

        now = time.time()

        # If token is a single letter (A-Z)
        if len(token) == 1 and token.isalpha():
            # Prevent accidental double-tap bounce of the same letter within 400ms
            if self.spelling_buffer and self.spelling_buffer[-1] == token and (now - self.last_letter_time < 0.40):
                logger.debug(f"Suppressed rapid duplicate letter bounce: '{token}'")
                return self.get_draft_sentence()
            self.spelling_buffer.append(token)
            self.last_letter_time = now
        else:
            # If we were previously fingerspelling a word, flush it first
            self._flush_spelling_buffer()
            # Anti-repetition guard: prevent adding the exact same whole word consecutively
            if self.tokens and self.tokens[-1] == token:
                logger.info(f"SentenceBuilder: Suppressed consecutive repeated word '{token}'")
                return self.get_draft_sentence()
            self.tokens.append(token)

        return self.get_draft_sentence()

    def _flush_spelling_buffer(self):
        """Combine accumulated fingerspelled letters into a single word token."""
        if self.spelling_buffer:
            word = "".join(self.spelling_buffer).capitalize()
            self.tokens.append(word)
            self.spelling_buffer.clear()

    def check_timeout(self):
        """Called periodically; flushes fingerspelled letters if user paused signing."""
        if self.spelling_buffer and (time.time() - self.last_letter_time > self.fingerspell_timeout):
            self._flush_spelling_buffer()

    def get_tokens(self) -> List[str]:
        tokens_copy = list(self.tokens)
        if self.spelling_buffer:
            tokens_copy.append("".join(self.spelling_buffer))
        return tokens_copy

    def get_draft_sentence(self) -> str:
        """Construct the best English sentence from currently signed tokens."""
        self.check_timeout()
        tokens = self.get_tokens()
        if not tokens:
            return ""

        # Check for matching idiomatic multi-sign phrase
        tuple_tokens = tuple(tokens)
        if tuple_tokens in self.GLOSS_PHRASE_PATTERNS:
            return self.GLOSS_PHRASE_PATTERNS[tuple_tokens]

        # Check sub-patterns or format into smooth sentence
        formatted_words = []
        for t in tokens:
            # If word is like "HOW_ARE_YOU", convert to "how are you"
            cleaned = t.replace("_", " ").capitalize()
            formatted_words.append(cleaned)

        sentence = " ".join(formatted_words)
        # Ensure proper capitalization and ending punctuation
        if sentence and sentence[-1] not in [".", "?", "!"]:
            sentence += "."
        return sentence

    def backspace(self) -> str:
        """Remove last entered character or token."""
        if self.spelling_buffer:
            self.spelling_buffer.pop()
        elif self.tokens:
            self.tokens.pop()
        return self.get_draft_sentence()

    def clear(self):
        """Reset sentence buffer."""
        self.tokens.clear()
        self.spelling_buffer.clear()

    def commit_sentence(self) -> str:
        """Return finalized sentence and clear buffer."""
        self._flush_spelling_buffer()
        final_str = self.get_draft_sentence()
        self.clear()
        return final_str
