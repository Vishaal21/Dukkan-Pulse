import { useEffect, useRef, useState } from "react";
import { useApp } from "../store";
import { answerQuestion, askLLM } from "../services/assistantService";
import { recommendationService } from "../services/recommendationService";
import { useSpeechRecognition, useSpeechSynthesis } from "../services/speech";
import { ASSISTANT_SUGGESTIONS } from "../mocks/demoData";
import Section from "../components/Section";

// Render **bold** markers from AI replies as real bold text.
function renderRich(text) {
  return String(text)
    .split(/(\*\*[^*]+\*\*)/g)
    .map((part, i) => {
      const m = part.match(/^\*\*([^*]+)\*\*$/);
      return m ? <strong key={i}>{m[1]}</strong> : part;
    });
}

export default function Assistant({ onNavigate }) {
  const { recommendations, budgetPlan } = useApp();
  const [messages, setMessages] = useState([]);
  const [composer, setComposer] = useState("");
  const [speakOn, setSpeakOn] = useState(true);
  const [thinking, setThinking] = useState(false);
  const endRef = useRef(null);

  const { supported: voiceSupported, listening, start, stop } = useSpeechRecognition({
    onResult: (text) => setComposer(text),
  });
  const { supported: speakSupported, speak, cancel } = useSpeechSynthesis();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  async function send(text) {
    const q = (text || "").trim();
    if (!q) return;
    setComposer("");
    cancel();
    setMessages((m) => [...m, { role: "user", text: q }]);
    setThinking(true);

    const ctx = { recommendations };
    const amount = q.match(/([\d,]{3,})/);
    if (amount && /budget|have|purchase|buy/i.test(q)) {
      const amt = Number(amount[1].replace(/,/g, ""));
      if (amt > 0) {
        try {
          ctx.budgetPlan = await recommendationService.getBudgetPlan(amt);
        } catch {
          /* fall through to non-budget answer */
        }
      }
    }

    const res = answerQuestion(q, ctx);
    let message = { role: "assistant", ...res };
    const llmAnswer = await askLLM(q);
    if (llmAnswer) {
      // AI text stands on its own; keep only the navigation links.
      message = { role: "assistant", text: llmAnswer, links: res.links, source: "llm" };
    }
    setMessages((m) => [...m, message]);
    setThinking(false);
    if (speakOn) speak(message.text);
  }

  return (
    <>
      <div className="page-head">
        <div className="page-head-row">
          <div>
            <h1>Ask DukaanPulse</h1>
            <p className="sub">Ask questions about your store and purchasing decisions.</p>
          </div>
          {speakSupported && (
            <label className="small-note" style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={speakOn} onChange={(e) => setSpeakOn(e.target.checked)} />
              Speak answers
            </label>
          )}
        </div>
      </div>

      <Section>
        {messages.length === 0 ? (
          <p className="state">Ask DukaanPulse about your store. Try a suggested question below.</p>
        ) : (
          <div className="chat" aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={"msg " + m.role}>
                <div className="who">
                  {m.role === "user" ? "You" : "DukaanPulse"}
                  {m.source === "llm" && <span className="ai-tag">AI</span>}
                </div>
                <div className="bubble">
                  {renderRich(m.text)}
                  {m.insights?.length > 0 && (
                    <div className="insights">
                      <div className="kv">
                        {m.insights.map((ins, j) => (
                          <span key={j}>
                            {ins.k}: <b>{ins.v}</b>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {m.links?.length > 0 && (
                    <div className="filters mt-16">
                      {m.links.map((l, j) => (
                        <button key={j} className="btn secondary small" onClick={() => onNavigate(l.page)}>
                          {l.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {thinking && (
              <div className="msg assistant">
                <div className="who">DukaanPulse</div>
                <div className="bubble muted">Thinking…</div>
              </div>
            )}
          </div>
        )}
        <div ref={endRef} />

        <div className="suggestions">
          {ASSISTANT_SUGGESTIONS.map((s) => (
            <button key={s} className="filter-chip" onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>

        <div className="composer">
          <textarea
            className="input"
            rows={2}
            aria-label="Your question"
            placeholder={listening ? "Listening…" : "Ask about reorders, low stock, slow movers or your budget…"}
            value={composer}
            onChange={(e) => setComposer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send(composer);
              }
            }}
          />
          {voiceSupported && (
            <button
              className={"mic" + (listening ? " listening" : "")}
              onClick={() => (listening ? stop() : start())}
              aria-label={listening ? "Stop recording" : "Start voice input"}
              title={listening ? "Stop recording" : "Start voice input"}
            >
              {listening ? "■" : "🎤"}
            </button>
          )}
          <button className="btn" onClick={() => send(composer)} disabled={!composer.trim()}>
            Send
          </button>
        </div>

        {voiceSupported ? (
          listening && <p className="transcript-note">Listening… speak now, then edit the text if needed.</p>
        ) : (
          <p className="transcript-note">
            Voice input isn’t supported in this browser. Please type your question instead.
          </p>
        )}
        <p className="transcript-note">
          Replies are written by AI (Groq) using your store data and the recommendation engine.
        </p>
      </Section>
    </>
  );
}
