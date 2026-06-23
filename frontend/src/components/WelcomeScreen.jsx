import React from 'react';
import TextInput from './TextInput';
import VoiceButton from './VoiceButton';

const SUGGESTIONS = [
  { icon: '🏭', label: 'Production Status',     text: 'Show current production batch status and any active delays' },
  { icon: '📊', label: 'Quality Compliance',    text: 'What is the quality compliance rate for this week?' },
  { icon: '🚛', label: 'Logistics Update',      text: 'Summarise logistics delays and shipment issues today' },
  { icon: '📦', label: 'Packaging Efficiency',  text: 'How is the packaging line performing right now?' },
  { icon: '🔬', label: 'Lab Results',           text: 'Show recent lab test results and any out-of-spec items' },
  { icon: '📋', label: 'Compliance Check',      text: 'Are there any open compliance or regulatory issues?' },
];

export default function WelcomeScreen({
  onQueryClick,
  onVoiceClick,
  onTextSend,
  isRecording,
  isBusy,
}) {
  return (
    <div className="flex flex-col w-full px-4 sm:px-8 md:px-10 pt-6 pb-8 gap-7">

      {/* ── Input bar — top of chat ── */}
      <div className="w-full">
        <p className="text-[10px] font-bold tracking-widest text-[var(--txt3)] uppercase mb-2">
          Ask ANI‑VOXA
        </p>
        <div
          className={`
            chat-input-row flex items-center gap-2 relative
            glass-surface rounded-full
            px-3 sm:px-4 py-2.5
            shadow-[0_4px_16px_rgba(0,0,0,0.18)]
            gradient-border-focus transition-all duration-150
            ${isRecording ? 'recording-pill' : ''}
          `}
        >
          <VoiceButton onRecordComplete={onVoiceClick} disabled={isBusy && !isRecording} />
          <TextInput onSend={onTextSend} disabled={isBusy} />
        </div>
        <p className="hidden md:block text-[11px] text-[var(--txt3)] opacity-50 mt-1.5 ml-1">
          Press Enter to send · Shift+Enter for new line · Space to toggle voice
        </p>
      </div>

      {/* ── Greeting ── */}
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-bold text-[var(--txt)] leading-snug">
          What can I help with today?
        </h2>
        <p className="text-sm text-[var(--txt3)]">
          Ask anything about production, quality, logistics, or packaging — or pick a quick prompt below.
        </p>
      </div>

      {/* ── Quick-prompt grid ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.label}
            onClick={() => onQueryClick?.(s.text)}
            className="
              flex items-start gap-3 p-3.5 rounded-xl text-left
              border border-[var(--brd)] bg-[var(--surf)]
              hover:bg-[var(--brd2)] hover:border-[var(--txt3)]
              active:scale-[0.98]
              transition-all duration-150 group
            "
          >
            <span className="text-xl leading-none mt-0.5 flex-shrink-0">{s.icon}</span>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-[var(--txt)] mb-0.5 group-hover:text-[var(--txt)]">
                {s.label}
              </div>
              <div className="text-[11px] text-[var(--txt3)] leading-relaxed line-clamp-2">
                {s.text}
              </div>
            </div>
          </button>
        ))}
      </div>

    </div>
  );
}
