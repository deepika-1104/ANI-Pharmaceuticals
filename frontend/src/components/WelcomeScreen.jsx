import React from 'react';
import TextInput from './TextInput';
import VoiceButton from './VoiceButton';
import AppLogo from './AppLogo';

const EXAMPLES = [
  { text: 'How many male, female, and other patients do we have?', icon: '🏥' },
  { text: 'List all 25 hospitals with their city, state, and bed capacity', icon: '📅' },
  { text: 'How many quality inspections passed, failed, conditional pass or are under review? What is the average inspection score?', icon: '🩺' },
  { text: 'List elderly patients above 65', icon: '👴' },
  { text: 'How many patients have blood type O+?', icon: '👩‍⚕️' },
  { text: 'How many lab results are flagged as Abnormal?', icon: '🛡️' },
];

/* Purple-to-pink gradient sound-wave icon */
function VoxaIcon({ size = 80 }) {
  const r  = Math.round(size * 0.22);
  const bw = Math.round(size * 0.1);
  const cx = size / 2;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <defs>
        <linearGradient id="vx-bg" x1="0" y1="0" x2={size} y2={size} gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#A855F7" />
          <stop offset="55%"  stopColor="#D946EF" />
          <stop offset="100%" stopColor="#EC4899" />
        </linearGradient>
      </defs>
      <rect width={size} height={size} rx={r} fill="url(#vx-bg)" />
      {/* Left bar  (shorter) */}
      <rect x={cx - size * 0.28} y={size * 0.35} width={bw} height={size * 0.30} rx={bw / 2} fill="white" opacity="0.85" />
      {/* Center bar (tallest) */}
      <rect x={cx - bw / 2}       y={size * 0.22} width={bw} height={size * 0.56} rx={bw / 2} fill="white" />
      {/* Right bar (shorter) */}
      <rect x={cx + size * 0.18}  y={size * 0.35} width={bw} height={size * 0.30} rx={bw / 2} fill="white" opacity="0.85" />
    </svg>
  );
}

/* Small circle-arrow avatar shown next to the welcome message */
function VoxaAvatar({ size = 36 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="18" cy="18" r="17" stroke="var(--gold-acc)" strokeWidth="1.5" fill="var(--surf)" opacity="0.9" />
      <circle cx="18" cy="18" r="11" stroke="var(--gold-acc)" strokeWidth="1.5" fill="none" opacity="0.5" />
      <path d="M18 22V14M14.5 17.5L18 14l3.5 3.5" stroke="var(--gold-acc)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function WelcomeScreen({
  onQueryClick,
  onVoiceClick,
  onTextSend,
  isRecording,
  isBusy,
}) {
  return (
    <div className="
      flex flex-col items-center w-full h-full
      px-3 sm:px-6 md:px-10
      pt-4 pb-3 overflow-hidden
    ">

      {/* ── Scrollable centre column ── */}
      <main className="
        flex flex-col items-center flex-1 min-h-0 w-full max-w-5xl
        gap-4 sm:gap-5
        overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden
        pt-6 sm:pt-10
      ">

        {/* Icon */}
        <div className="flex-shrink-0">
          <AppLogo size={160} />
        </div>

        {/* Title */}
        <h1 className="
          text-gold-gradient-animated font-extrabold tracking-tight text-center leading-tight m-0 flex-shrink-0
          text-[clamp(1.2rem,3.5vw,2.1rem)]
        ">
          VOXA : Voice Enabled AI Assistant
        </h1>

        {/* "TRY ASKING" label */}
        <p className="
          text-[var(--txt2)] text-[0.65rem] sm:text-[0.7rem] font-bold uppercase tracking-[0.18em]
          text-center m-0 flex-shrink-0
        ">
          Try Asking
        </p>

        {/* ── Pill chips — flex-wrap, 3 per row on wide screens ── */}
        <div className="flex flex-wrap justify-center gap-2 sm:gap-2.5 w-full flex-shrink-0 pb-12 sm:pb-16">
          {EXAMPLES.map((e, i) => (
            <button
              key={i}
              className="
                inline-flex items-center gap-1.5 flex-shrink-0
                rounded-full
                bg-[var(--surf)] border border-[var(--brd)] text-[var(--txt2)]
                px-3 py-1.5 sm:px-3.5 sm:py-2
                text-[0.7rem] sm:text-xs
                hover:border-gold/40 hover:text-gold hover:bg-[var(--surf-hover)] hover:-translate-y-px
                transition-all duration-150 cursor-pointer
                disabled:opacity-35 disabled:cursor-not-allowed disabled:!transform-none
              "
              onClick={() => onQueryClick(e.text)}
              disabled={isBusy}
            >
              <span className="text-xs sm:text-sm flex-shrink-0 leading-none">{e.icon}</span>
              <span className="text-left leading-snug">{e.text}</span>
            </button>
          ))}
        </div>

        {/* ── Welcome message bubble ── */}
        <div className="flex items-start gap-2.5 sm:gap-3 w-full flex-shrink-0">

          <div className="flex-shrink-0">
            <VoxaAvatar size={36} />
          </div>

          <div className="welcome-bubble text-xs sm:text-sm flex-1 min-w-0">
            Hello! I am{' '}
            <span className="text-gold-gradient font-semibold">VOXA</span>
            , your voice-enabled AI assistant designed to help you explore operational data intelligently.
          </div>
        </div>

      </main>

      {/* ── Bottom input bar ── */}
      <footer className="w-full max-w-5xl flex-shrink-0 pt-3">
        <div
          className={`
            chat-input-row w-full flex items-center gap-2 sm:gap-2.5 relative
            glass-surface rounded-full
            px-3 sm:px-4 py-2.5
            shadow-[0_4px_16px_rgba(0,0,0,0.3)] transition-all duration-150
            gradient-border-focus
            ${isRecording ? 'recording-pill' : ''}
          `}
        >
          <VoiceButton onRecordComplete={onVoiceClick} disabled={isBusy && !isRecording} />
          <TextInput onSend={onTextSend} disabled={isBusy} />
        </div>
        <p className="hidden sm:block text-[11px] text-[var(--txt3)] text-center mt-1.5 opacity-70">
          Press Enter to send · Shift+Enter for new line
        </p>
      </footer>

    </div>
  );
}
