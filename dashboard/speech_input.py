import streamlit as st


speech_input = st.components.v2.component(
    name="autopilot_voice_dictation",
    html='''
        <div class="voice-control">
            <button id="voice-button" type="button">🎙️ Start recording</button>
            <span id="voice-status" role="status">Ready</span>
        </div>
    ''',
    css='''
        .voice-control {
            display: flex;
            align-items: center;
            gap: 12px;
            min-height: 44px;
            color: var(--st-text-color);
            font-family: var(--st-font);
        }
        #voice-button {
            border: 1px solid var(--st-primary-color);
            border-radius: 8px;
            padding: 9px 14px;
            background: var(--st-primary-color);
            color: white;
            font: inherit;
            font-weight: 600;
            cursor: pointer;
        }
        #voice-button:disabled {
            opacity: 0.55;
            cursor: not-allowed;
        }
        #voice-status {
            font-size: 0.9rem;
            opacity: 0.8;
        }
    ''',
    js='''
        export default function ({ parentElement, data, setStateValue, setTriggerValue }) {
            const button = parentElement.querySelector("#voice-button");
            const status = parentElement.querySelector("#voice-status");
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            if (!SpeechRecognition) {
                button.disabled = true;
                status.textContent = "Voice input is not supported by this browser.";
                return;
            }

            const recognition = new SpeechRecognition();
            recognition.lang = data?.lang || "fr-FR";
            recognition.continuous = true;
            recognition.interimResults = true;
            let finalTranscript = "";
            let listening = false;
            let stopRequestedByUser = false;

            recognition.onstart = () => {
                listening = true;
                finalTranscript = "";
                stopRequestedByUser = false;
                setStateValue("transcript", "");
                setTriggerValue("started", { event_id: `${Date.now()}-${Math.random()}` });
                button.textContent = "⏹️ Stop recording";
                status.textContent = "Listening…";
            };

            recognition.onresult = (event) => {
                let interimTranscript = "";
                for (let i = event.resultIndex; i < event.results.length; i += 1) {
                    const phrase = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        finalTranscript += `${phrase} `;
                    } else {
                        interimTranscript += phrase;
                    }
                }
                const transcript = `${finalTranscript}${interimTranscript}`.trim();
                setStateValue("transcript", transcript);
                status.textContent = interimTranscript ? `Listening: ${interimTranscript}` : "Transcript updated.";
            };

            recognition.onerror = (event) => {
                const messages = {
                    "not-allowed": "Allow microphone access in your browser.",
                    "no-speech": "No speech detected. Please try again.",
                    "audio-capture": "No microphone detected.",
                    "network": "Voice recognition requires a network connection.",
                };
                status.textContent = messages[event.error] || "Voice recognition encountered an error.";
                listening = false;
                button.textContent = "🎙️ Start recording";
            };

            recognition.onend = () => {
                listening = false;
                button.textContent = "🎙️ Start recording";
                const completedTranscript = finalTranscript.trim();
                if (stopRequestedByUser) {
                    setTriggerValue("finished", {
                        event_id: `${Date.now()}-${Math.random()}`,
                        transcript: completedTranscript,
                    });
                    status.textContent = "Recording complete. You can submit your request.";
                } else if (completedTranscript) {
                    status.textContent = "Recording complete.";
                }
                stopRequestedByUser = false;
            };

            button.addEventListener("click", () => {
                if (listening) {
                    stopRequestedByUser = true;
                    recognition.stop();
                }
                else {
                    try {
                        recognition.start();
                    } catch (error) {
                        status.textContent = "Recording is already in progress.";
                    }
                }
            });

            return () => recognition.stop();
        }
    ''',
)
