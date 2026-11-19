/*
 * Voice input (speech-to-text) and read-aloud (text-to-speech) for the chatbot,
 * using the browser's built-in Web Speech API. No extra libraries or servers.
 *
 * - Voice input works in Chrome and Edge (Firefox doesn't support it; the mic
 *   button is hidden there).
 * - Read-aloud works in all modern browsers; Hindi needs a Hindi voice on the
 *   device (Android/Chrome and Windows usually have one).
 */

const Voice = (() => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const canListen = Boolean(Recognition);
    const canSpeak = "speechSynthesis" in window && typeof SpeechSynthesisUtterance !== "undefined";

    let recognition = null;
    let listening = false;
    let speakingId = null;

    function listen({ lang, onInterim, onResult, onEnd, onError } = {}) {
        if (!canListen) {
            if (onError) onError("unsupported");
            return;
        }
        if (listening) {
            stopListening();
            return;
        }

        recognition = new Recognition();
        recognition.lang = lang || "en-IN";
        recognition.interimResults = true;
        recognition.continuous = false;
        recognition.maxAlternatives = 1;

        let finalText = "";

        recognition.onresult = (event) => {
            let interim = "";
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const result = event.results[i];
                if (result.isFinal) finalText += result[0].transcript;
                else interim += result[0].transcript;
            }
            if (onInterim) onInterim((finalText + interim).trim());
        };

        recognition.onerror = (event) => {
            if (onError) onError(event.error || "error");
        };

        recognition.onend = () => {
            listening = false;
            recognition = null;
            const text = finalText.trim();
            if (text && onResult) onResult(text);
            if (onEnd) onEnd(Boolean(text));
        };

        try {
            listening = true;
            recognition.start();
        } catch (error) {
            listening = false;
            recognition = null;
            if (onError) onError("start-failed");
            if (onEnd) onEnd(false);
        }
    }

    function stopListening() {
        if (recognition) recognition.stop();
    }

    // Emojis, bullets and links sound bad when read out.
    function cleanForSpeech(text) {
        return String(text || "")
            .replace(/https?:\/\/\S+/g, "")
            .replace(/[\p{Extended_Pictographic}️‍]/gu, "")
            .replace(/[•▪]/g, "")
            .replace(/\s*\n+\s*/g, ". ")
            .replace(/\.\s*\./g, ".")
            .replace(/\s{2,}/g, " ")
            .trim();
    }

    function pickVoice(lang) {
        const voices = window.speechSynthesis.getVoices() || [];
        const base = lang.split("-")[0];
        return (
            voices.find((v) => v.lang === lang) ||
            voices.find((v) => v.lang && v.lang.replace("_", "-").startsWith(base)) ||
            null
        );
    }

    // Speak `text`; calling again with the same id while it is speaking stops it.
    function speak(id, text, lang, { onStart, onEnd } = {}) {
        if (!canSpeak) return false;
        const synth = window.speechSynthesis;
        const togglingOff = speakingId === id && (synth.speaking || synth.pending);

        synth.cancel();
        if (togglingOff) {
            speakingId = null;
            if (onEnd) onEnd();
            return true;
        }

        const utterance = new SpeechSynthesisUtterance(cleanForSpeech(text));
        utterance.lang = lang;
        utterance.rate = 0.95;
        const voice = pickVoice(lang);
        if (voice) utterance.voice = voice;

        const finish = () => {
            if (speakingId === id) speakingId = null;
            if (onEnd) onEnd();
        };
        utterance.onend = finish;
        utterance.onerror = finish;

        speakingId = id;
        if (onStart) onStart();
        synth.speak(utterance);
        return true;
    }

    function stopSpeaking() {
        if (canSpeak) window.speechSynthesis.cancel();
        speakingId = null;
    }

    // Some browsers load voices asynchronously.
    if (canSpeak && window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }

    return {
        canListen,
        canSpeak,
        listen,
        stopListening,
        speak,
        stopSpeaking,
        cleanForSpeech,
        isListening: () => listening,
        speakingId: () => speakingId,
    };
})();

function speechLangFor(text) {
    return /[ऀ-ॿ]/.test(String(text || "")) ? "hi-IN" : "en-IN";
}
