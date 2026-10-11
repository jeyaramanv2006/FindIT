import React, { useEffect, useRef } from 'react';

interface RankingPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  onToggle: () => void;
  currentMode?: 'hybrid' | 'semantic' | 'lexical';
  onSelectMode?: (mode: 'hybrid' | 'semantic' | 'lexical') => void;
}

export const RankingPopover: React.FC<RankingPopoverProps> = ({
  isOpen,
  onClose,
  onToggle,
  currentMode = 'hybrid',
  onSelectMode,
}) => {
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    const handleClickOutside = (e: MouseEvent) => {
      if (
        isOpen &&
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        triggerRef.current &&
        !triggerRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('click', handleClickOutside);
    };
  }, [isOpen, onClose]);

  return (
    <div className="relative inline-flex items-center">
      <button
        ref={triggerRef}
        aria-controls="ranking-popover"
        aria-expanded={isOpen}
        onClick={onToggle}
        type="button"
        title="Choose ranking mode or learn how results are ranked"
        className="group/btn flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-text-secondary hover:text-text-primary hover:bg-sand-200/50 transition-colors duration-150 focus:outline-none"
      >
        <span className="material-symbols-outlined text-[15px] text-text-secondary group-hover/btn:text-primary-container transition-colors">
          tune
        </span>
        <span className="font-caption text-caption underline decoration-text-secondary/40 underline-offset-4 group-hover/btn:decoration-text-primary transition-colors">
          Ranking modes
        </span>
      </button>

      {isOpen && (
        <div
          ref={popoverRef}
          id="ranking-popover"
          role="region"
          aria-label="Search ranking modes"
          className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-[320px] sm:w-[350px] p-4 rounded-xl shadow-[0_12px_36px_-6px_rgba(41,37,34,0.18),0_2px_8px_-2px_rgba(41,37,34,0.06)] z-50 transition-all duration-200 border border-border-subtle/80 text-left bg-surface-elevated animate-in fade-in zoom-in-95"
        >
          <div className="flex items-center justify-between pb-2.5 mb-2.5 bg-surface-secondary/40 -mx-4 -mt-4 px-4 pt-3.5 rounded-t-xl border-b border-sand-300/40">
            <div>
              <span className="font-label-md text-label-md text-text-primary font-semibold block">
                Choose Ranking Strategy
              </span>
              <span className="text-[11px] text-warmgrey">Select how search results will be sorted</span>
            </div>
            <button
              aria-label="Close info"
              onClick={onClose}
              type="button"
              className="text-text-secondary hover:text-text-primary p-0.5 rounded transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>

          <div className="space-y-1.5 font-body-sm text-body-sm">
            {/* Hybrid Choice */}
            <button
              type="button"
              onClick={() => {
                onSelectMode?.('hybrid');
                onClose();
              }}
              className={`w-full text-left p-2.5 rounded-xl border transition-all flex items-start gap-2.5 cursor-pointer ${
                currentMode === 'hybrid'
                  ? 'bg-brick-light/50 border-[#9E2F2B]/40 shadow-xs'
                  : 'bg-surface hover:bg-sand-100/60 border-sand-300/30'
              }`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${
                  currentMode === 'hybrid' ? 'bg-[#9E2F2B] ring-2 ring-[#9E2F2B]/30' : 'bg-sand-400'
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <strong className="font-semibold text-text-primary font-label-md">Hybrid (RRF)</strong>
                  {currentMode === 'hybrid' && (
                    <span className="text-[10px] font-mono font-semibold text-brick bg-brick/10 px-1.5 py-0.5 rounded">
                      Selected
                    </span>
                  )}
                </div>
                <p className="text-text-secondary text-caption font-caption mt-0.5 leading-snug">
                  Combines semantic meaning and keyword matching for balanced precision.
                </p>
              </div>
            </button>

            {/* Semantic Choice */}
            <button
              type="button"
              onClick={() => {
                onSelectMode?.('semantic');
                onClose();
              }}
              className={`w-full text-left p-2.5 rounded-xl border transition-all flex items-start gap-2.5 cursor-pointer ${
                currentMode === 'semantic'
                  ? 'bg-brick-light/50 border-[#9E2F2B]/40 shadow-xs'
                  : 'bg-surface hover:bg-sand-100/60 border-sand-300/30'
              }`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${
                  currentMode === 'semantic' ? 'bg-[#9E2F2B] ring-2 ring-[#9E2F2B]/30' : 'bg-sand-400'
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <strong className="font-semibold text-text-primary font-label-md">Semantic (Dense)</strong>
                  {currentMode === 'semantic' && (
                    <span className="text-[10px] font-mono font-semibold text-brick bg-brick/10 px-1.5 py-0.5 rounded">
                      Selected
                    </span>
                  )}
                </div>
                <p className="text-text-secondary text-caption font-caption mt-0.5 leading-snug">
                  Prioritizes passages with similar contextual meaning and concepts (FAISS vectors).
                </p>
              </div>
            </button>

            {/* Lexical Choice */}
            <button
              type="button"
              onClick={() => {
                onSelectMode?.('lexical');
                onClose();
              }}
              className={`w-full text-left p-2.5 rounded-xl border transition-all flex items-start gap-2.5 cursor-pointer ${
                currentMode === 'lexical'
                  ? 'bg-brick-light/50 border-[#9E2F2B]/40 shadow-xs'
                  : 'bg-surface hover:bg-sand-100/60 border-sand-300/30'
              }`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${
                  currentMode === 'lexical' ? 'bg-[#9E2F2B] ring-2 ring-[#9E2F2B]/30' : 'bg-sand-400'
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <strong className="font-semibold text-text-primary font-label-md">Lexical (BM25)</strong>
                  {currentMode === 'lexical' && (
                    <span className="text-[10px] font-mono font-semibold text-brick bg-brick/10 px-1.5 py-0.5 rounded">
                      Selected
                    </span>
                  )}
                </div>
                <p className="text-text-secondary text-caption font-caption mt-0.5 leading-snug">
                  Prioritizes exact verbatim terminology and term frequencies (BM25 keywords).
                </p>
              </div>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
