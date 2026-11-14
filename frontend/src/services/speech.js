import { useCallback, useEffect, useRef, useState } from "react";

// Browser speech recognition (Chrome/Edge). Gracefully unavailable elsewhere.
export function useSpeechRecognition({ onResult } = {}) {
  const SR =
    typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);
  const supported = !!SR;
  const [listening, setListening] = useState(false);
  const recRef = useRef(null);

  const stop = useCallback(() => {
    if (recRef.current) {
      recRef.current.stop();
      setListening(false);
    }
  }, []);

  const start = useCallback(() => {
    if (!supported) return;
    const rec = new SR();
    rec.lang = "en-IN";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      onResult?.(text);
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    rec.start();
    setListening(true);
  }, [SR, supported, onResult]);

  useEffect(() => () => recRef.current?.stop(), []);
  return { supported, listening, start, stop };
}

// Speech synthesis wrapper.
export function useSpeechSynthesis() {
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;

  const speak = useCallback(
    (text) => {
      if (!supported || !text) return;
      try {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = "en-IN";
        u.rate = 1;
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(u);
      } catch {
        /* ignore */
      }
    },
    [supported]
  );

  const cancel = useCallback(() => {
    if (supported) window.speechSynthesis.cancel();
  }, [supported]);

  return { supported, speak, cancel };
}
