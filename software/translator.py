"""
N-Atlas Multilingual Translation Engine
Translates English text derived from ASL gloves into Nigerian languages (Yoruba, Igbo, Hausa).
Features a dual-engine architecture:
  1. Fast offline lexicon with high-fidelity tonal diacritics.
  2. N-Atlas / NLLB Deep Seq2Seq Neural Transformer via Hugging Face.
"""
import sys
import logging
from typing import Dict, Optional, Tuple, Any
import threading
import config

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TranslatorEngine")

class NAtlasTranslator:
    # High-accuracy bilingual repository of everyday phrases & words with authentic tone markings
    LEXICON = {
        # Greetings & Courtesies
        "hello": {
            "Yoruba": ("Ẹ n lẹ o!", "Ehn-leh oh"),
            "Igbo": ("Ndewo!", "N-deh-woh"),
            "Hausa": ("Sannu!", "Sahn-noo")
        },
        "hello, greetings!": {
            "Yoruba": ("Ẹ n lẹ o, ẹ ku àbọ̀!", "Ehn-leh oh, eh koo ah-boh"),
            "Igbo": ("Ndewo, nnoo!", "N-deh-woh, n-noh"),
            "Hausa": ("Sannu da zuwa!", "Sahn-noo dah zoo-wah")
        },
        "how are you doing?": {
            "Yoruba": ("Bawo ni o ṣe wa?", "Bah-woh nee oh shay wah?"),
            "Igbo": ("Kedu ka ị mere?", "Keh-doo kah ee meh-reh?"),
            "Hausa": ("Yaya kake?", "Yah-yah kah-keh?")
        },
        "hello, how are you doing?": {
            "Yoruba": ("Ẹ n lẹ o, bawo ni gbogbo nkan?", "Ehn-leh oh, bah-woh nee gbog-boh n-kahn?"),
            "Igbo": ("Ndewo, kedu ka ị mere?", "N-deh-woh, keh-doo kah ee meh-reh?"),
            "Hausa": ("Sannu, yaya kake yau?", "Sahn-noo, yah-yah kah-keh yow?")
        },
        "thank you very much.": {
            "Yoruba": ("Ẹ ṣe pupọ.", "Eh shay poo-poh"),
            "Igbo": ("Dalu nke ukwuu.", "Dah-loo n-keh oo-kwoo"),
            "Hausa": ("Nagode sosai.", "Nah-goh-deh soh-sigh")
        },
        "please.": {
            "Yoruba": ("Ẹ jọ̀wọ́.", "Eh joh-woh"),
            "Igbo": ("Biko.", "Bee-koh"),
            "Hausa": ("Don Allah.", "Dohn Ahl-lah")
        },
        "yes, that is correct.": {
            "Yoruba": ("Bẹ́ẹ̀ni, bẹ́ẹ̀ gẹ́gẹ́ ni.", "Beh-eh-nee, beh-eh geh-geh nee"),
            "Igbo": ("Ee, ọ bụ eziokwu.", "Eh, oh boo eh-zee-oh-kwoo"),
            "Hausa": ("I, haka ne.", "Ee, hah-kah neh")
        },
        "no, thank you.": {
            "Yoruba": ("Rárá, ẹ ṣe.", "Rah-rah, eh shay"),
            "Igbo": ("Mba, dalu.", "M-bah, dah-loo"),
            "Hausa": ("A'a, nagode.", "Ah-ah, nah-goh-deh")
        },
        # Emergencies & Needs
        "please, i need help.": {
            "Yoruba": ("Ẹ jọ̀wọ́, ẹ gbà mí o!", "Eh joh-woh, eh gbah mee oh!"),
            "Igbo": ("Biko, nyere m aka!", "Bee-koh, nyeh-reh m ah-kah!"),
            "Hausa": ("Don Allah, taimake ni!", "Dohn Ahl-lah, tie-mah-keh nee!")
        },
        "please, help me immediately.": {
            "Yoruba": ("Ẹ tètè gbà mí o!", "Eh teh-teh gbah mee oh!"),
            "Igbo": ("Biko nyere m aka ozugbo!", "Bee-koh nyeh-reh m ah-kah oh-zoog-boh!"),
            "Hausa": ("Don Allah taimake ni yanzu!", "Dohn Ahl-lah tie-mah-keh nee yahn-zoo!")
        },
        "i would like some water.": {
            "Yoruba": ("Mo fẹ́ mu omi.", "Moh feh moo oh-mee"),
            "Igbo": ("Achọrọ m mmiri.", "Ah-choh-roh m mmee-ree"),
            "Hausa": ("Ina son ruwa.", "Ee-nah sohn roo-wah")
        },
        "please give me some water.": {
            "Yoruba": ("Ẹ jọ̀wọ́, ẹ fún mi ní omi.", "Eh joh-woh, eh foon mee nee oh-mee"),
            "Igbo": ("Biko nye m mmiri.", "Bee-koh nyeh m mmee-ree"),
            "Hausa": ("Don Allah bani ruwa.", "Dohn Ahl-lah bah-nee roo-wah")
        },
        "i need food.": {
            "Yoruba": ("Mo fẹ́ jẹ oúnjẹ.", "Moh feh jeh oh-oon-jeh"),
            "Igbo": ("Achọrọ m nri.", "Ah-choh-roh m n-ree"),
            "Hausa": ("Ina son abinci.", "Ee-nah sohn ah-been-chee")
        },
        "please give me some food.": {
            "Yoruba": ("Ẹ jọ̀wọ́, ẹ fún mi ní oúnjẹ.", "Eh joh-woh, eh foon mee nee oh-oon-jeh"),
            "Igbo": ("Biko nye m nri.", "Bee-koh nyeh m n-ree"),
            "Hausa": ("Don Allah bani abinci.", "Dohn Ahl-lah bah-nee ah-been-chee")
        },
        "i need to see a doctor.": {
            "Yoruba": ("Mo fẹ́ rí dókítà.", "Moh feh ree doh-kee-tah"),
            "Igbo": ("Achọrọ m ịhụ dọkịta.", "Ah-choh-roh m ee-hoo doh-kee-tah"),
            "Hausa": ("Ina buƙatar ganin likita.", "Ee-nah boo-kah-tahr gah-neen lee-kee-tah")
        },
        "medical emergency, please call a doctor!": {
            "Yoruba": ("Pàjáwìrì! Ẹ pe dókítà wá!", "Pah-jah-wee-ree! Eh peh doh-kee-tah wah!"),
            "Igbo": ("Ihe mberede ahụike! Biko kpọọ dọkịta!", "Ee-heh m-beh-reh-deh ah-hoo-ee-keh!"),
            "Hausa": ("Gaggawa! Don Allah a kira likita!", "Gahg-gah-wah! Dohn ahl-lah ah kee-rah lee-kee-tah!")
        },
        # Everyday & Family
        "this is my family.": {
            "Yoruba": ("Èyí ni ẹbí mi.", "Eh-yee nee eh-bee mee"),
            "Igbo": ("Nke a bụ ezinụlọ m.", "N-keh ah boo eh-zee-noo-loh m"),
            "Hausa": ("Wannan shine iyalina.", "Wahn-nahn shee-neh ee-yah-lee-nah")
        },
        "i love you.": {
            "Yoruba": ("Mo nífẹ̀ẹ́ rẹ.", "Moh nee-feh-eh reh"),
            "Igbo": ("A hụrụ m gị n'anya.", "Ah hoo-roo m gee n-ahn-yah"),
            "Hausa": ("Ina son ku.", "Ee-nah sohn koo")
        },
        "good morning to you.": {
            "Yoruba": ("Ẹ káàárọ̀ o.", "Eh kah-ah-roh oh"),
            "Igbo": ("Ụtụtụ ọma.", "Oo-too-too oh-mah"),
            "Hausa": ("Ina kwana.", "Ee-nah kwah-nah")
        },
        "peace and harmony.": {
            "Yoruba": ("Àlàáfíà àti ìrẹ́pọ̀.", "Ah-lah-fee-ah ah-tee ee-reh-poh"),
            "Igbo": ("Udo na ịdị n'otu.", "Oo-doh nah ee-dee n-oh-too"),
            "Hausa": ("Zaman lafiya da jituwa.", "Zah-mahn lah-fee-yah dah jee-too-wah")
        },
        "goodbye, see you later.": {
            "Yoruba": ("Ó dàbọ̀, a ó ríra nígbà mìíràn.", "Oh dah-boh, ah oh ree-rah"),
            "Igbo": ("Ka ọ dị, ka emesia.", "Kah oh dee, kah eh-meh-see-ah"),
            "Hausa": ("Sai an jima, sai mun sake haɗuwa.", "Sigh ahn jee-mah")
        }
    }

    def __init__(self):
        self.tokenizer = None
        self.neural_model = None
        self.neural_loading = False
        self.neural_ready = False
        self._lock = threading.Lock()

    def load_neural_model_async(self, model_name: str = config.NATLAS_MODEL_NAME):
        """Asynchronously load N-Atlas / NLLB Seq2Seq model without stalling the UI."""
        if self.neural_ready or self.neural_loading:
            return

        def _loader():
            self.neural_loading = True
            logger.info(f"Loading neural translation model '{model_name}'...")
            try:
                from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
                with self._lock:
                    self.tokenizer = tokenizer
                    self.neural_model = model
                    self.neural_ready = True
                logger.info(f"Neural model '{model_name}' loaded successfully!")
            except Exception as e:
                logger.error(f"Failed to load neural model: {e}. Fallback lexicon remains active.")
            finally:
                self.neural_loading = False

        thread = threading.Thread(target=_loader, daemon=True)
        thread.start()

    def get_model_details(self) -> Dict[str, Any]:
        """Return metadata summary about the N-Atlas translation architecture."""
        return {
            "model_title": "N-Atlas Afro-Centric Multilingual Translation Engine",
            "supported_languages": ["Yoruba (yor_Latn)", "Igbo (ibo_Latn)", "Hausa (hau_Latn)"],
            "lexicon_entries": len(self.LEXICON),
            "neural_checkpoint": config.NATLAS_MODEL_NAME,
            "neural_ready": self.neural_ready,
            "neural_loading": self.neural_loading,
            "active_engine": "N-Atlas Neural Transformer" if self.neural_ready else "N-Atlas Authentic Tonal Lexicon",
            "tonal_diacritics": "High (´), Low (`), Subdots (ẹ, ọ, ṣ, ụ, ị, ṅ)"
        }

    def translate(self, text: str, target_lang: str) -> Dict[str, str]:
        """
        Translate input English text to chosen target language.
        
        Args:
            text: Input English sentence.
            target_lang: 'English', 'Yoruba', 'Igbo', or 'Hausa'.
            
        Returns:
            Dictionary with {source, target_lang, translation, phonetic, engine}.
        """
        text_clean = text.strip()
        if not text_clean:
            return {"source": "", "target_lang": target_lang, "translation": "", "phonetic": "", "engine": "None"}

        if target_lang.lower() == "english":
            return {
                "source": text_clean,
                "target_lang": "English",
                "translation": text_clean,
                "phonetic": text_clean,
                "engine": "Passthrough"
            }

        # 1. Check Lexicon for instant accurate translation
        text_lookup = text_clean.lower().rstrip(".")
        for key in self.LEXICON:
            if key.rstrip(".") == text_lookup:
                trans_tuple = self.LEXICON[key].get(target_lang)
                if trans_tuple:
                    return {
                        "source": text_clean,
                        "target_lang": target_lang,
                        "translation": trans_tuple[0],
                        "phonetic": trans_tuple[1],
                        "engine": "N-Atlas Lexicon"
                    }

        # 2. Check if deep neural model is ready
        if self.neural_ready and self.tokenizer and self.neural_model:
            try:
                target_meta = config.SUPPORTED_LANGUAGES.get(target_lang, {})
                nllb_code = target_meta.get("nllb_code", "yor_Latn")
                
                inputs = self.tokenizer(text_clean, return_tensors="pt")
                forced_bos_token_id = self.tokenizer.lang_code_to_id.get(nllb_code)

                outputs = self.neural_model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    max_length=128,
                    num_beams=3
                )
                pred_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                return {
                    "source": text_clean,
                    "target_lang": target_lang,
                    "translation": pred_text,
                    "phonetic": pred_text,
                    "engine": "N-Atlas Neural Transformer"
                }
            except Exception as e:
                logger.warning(f"Neural inference error: {e}. Falling back to word-level lookup.")

        # 3. Fallback: Word-by-word tokenized lookup
        words = text_clean.split()
        translated_tokens = []
        for w in words:
            w_norm = w.lower().strip(".,!?:;")
            found = False
            for k, v in self.LEXICON.items():
                if k.lower().strip(".,!?:;") == w_norm and target_lang in v:
                    translated_tokens.append(v[target_lang][0])
                    found = True
                    break
            if not found:
                translated_tokens.append(w)

        assembled = " ".join(translated_tokens)
        return {
            "source": text_clean,
            "target_lang": target_lang,
            "translation": assembled,
            "phonetic": assembled,
            "engine": "N-Atlas Heuristic Lexicon"
        }

if __name__ == "__main__":
    t = NAtlasTranslator()
    test_phrases = ["Hello!", "Please give me some water.", "Thank you very much."]
    for lang in ["Yoruba", "Igbo", "Hausa"]:
        print(f"\n--- Target: {lang} ---")
        for p in test_phrases:
            res = t.translate(p, lang)
            print(f"EN: {p} -> {res['translation']} (Phonetic: {res['phonetic']}) [{res['engine']}]")
