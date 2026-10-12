"""
Text-to-Speech (TTS) Engine for English and Nigerian Languages
Synthesizes and speaks out English sentences or translated Yoruba, Igbo, and Hausa phrases.
"""
import os
import sys
import time
import tempfile
import threading
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TTSEngine")

class TTSEngine:
    def __init__(self):
        self.is_speaking = False
        self._lock = threading.Lock()
        self._pygame_initialized = False
        self._init_audio_backend()

    def _init_audio_backend(self):
        try:
            import pygame
            pygame.mixer.init()
            self._pygame_initialized = True
        except Exception as e:
            logger.debug(f"Pygame audio backend not initialized: {e}")

    def speak(self, text: str, lang_name: str = "English", async_mode: bool = True):
        """
        Synthesize and play speech for the given text in the specified language.
        
        Args:
            text: Text to speak.
            lang_name: 'English', 'Yoruba', 'Igbo', or 'Hausa'.
            async_mode: If True, executes in a background thread to prevent UI freezing.
        """
        text_clean = text.strip()
        if not text_clean:
            return

        if async_mode:
            thread = threading.Thread(target=self._speak_worker, args=(text_clean, lang_name), daemon=True)
            thread.start()
        else:
            self._speak_worker(text_clean, lang_name)

    def _speak_worker(self, text: str, lang_name: str):
        with self._lock:
            self.is_speaking = True
            logger.info(f"Speaking [{lang_name}]: {text}")

            # 1. Attempt gTTS (Google Neural TTS with African language support)
            success = self._speak_gtts(text, lang_name)

            # 2. Fallback: Offline pyttsx3 or OS SAPI
            if not success:
                self._speak_offline_fallback(text)

            self.is_speaking = False

    def _speak_gtts(self, text: str, lang_name: str) -> bool:
        try:
            from gtts import gTTS

            # Map to language code supported by gTTS
            lang_lower = lang_name.lower()
            if "yoruba" in lang_lower:
                lang_code = "yo"
            elif "hausa" in lang_lower:
                lang_code = "ha"
            elif "igbo" in lang_lower:
                # gTTS does not currently have direct 'ig' ISO voice; we use English phonetics or Swahili/Yoruba accent
                lang_code = "en"
            else:
                lang_code = "en"

            tts = gTTS(text=text, lang=lang_code, slow=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                temp_path = fp.name

            tts.save(temp_path)
            self._play_audio_file(temp_path)

            try:
                os.remove(temp_path)
            except Exception:
                pass
            return True

        except Exception as e:
            logger.warning(f"gTTS online synthesis unavailable: {e}. Falling back to offline voice.")
            return False

    def _play_audio_file(self, file_path: str):
        """Play an MP3/WAV audio file cross-platform."""
        if self._pygame_initialized:
            try:
                import pygame
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                return
            except Exception as e:
                logger.debug(f"Pygame playback error: {e}")

        # Windows PowerShell fallback audio player
        if sys.platform == "win32":
            try:
                cmd = f'powershell -c "(New-Object Media.SoundPlayer \'{file_path}\').PlaySync()"'
                os.system(cmd)
            except Exception:
                pass

    def _speak_offline_fallback(self, text: str):
        """Local offline text-to-speech fallback using pyttsx3 or Windows SAPI."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            if sys.platform == "win32":
                try:
                    clean = text.replace('"', '').replace("'", "")
                    cmd = f'powershell -Command "Add-Type –AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{clean}\')"'
                    os.system(cmd)
                except Exception as e:
                    logger.error(f"Offline voice failed: {e}")

if __name__ == "__main__":
    tts = TTSEngine()
    tts.speak("Hello! Testing ASL translator to Nigerian languages.", "English", async_mode=False)
    tts.speak("Ẹ n lẹ o, bawo ni o ṣe wa?", "Yoruba", async_mode=False)
