import React, { useEffect, useRef } from 'react';

interface RankingPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  onToggle: () => void;
}

export const RankingPopover: React.FC<RankingPopoverProps> = ({ isOpen, onClose, onToggle }) => {
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
    <div className="relative mt-4 flex items-center justify-center">
      <button
        ref={triggerRef}
        aria-controls="ranking-popover"
        aria-expanded={isOpen}
        onClick={onToggle}
        type="button"
        className="group/btn flex items-center gap-1.5 px-2.5 py-1 rounded text-text-secondary hover:text-text-primary transition-colors duration-150 focus:outline-none"
      >
        <span className="material-symbols-outlined text-[15px] text-text-secondary group-hover/btn:text-primary-container transition-colors">
          info
        </span>
        <span className="font-caption text-caption underline decoration-text-secondary/40 underline-offset-4 group-hover/btn:decoration-text-primary transition-colors">
          How results are ranked
        </span>
      </button>

      {isOpen && (
        <div
          ref={popoverRef}
          id="ranking-popover"
          role="region"
          aria-label="Search ranking modes"
          className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-[310px] sm:w-[340px] p-4 rounded-xl shadow-[0_12px_36px_-6px_rgba(41,37,34,0.16),0_2px_8px_-2px_rgba(41,37,34,0.04)] z-40 transition-all duration-200 border border-border-subtle/50 text-left bg-surface-elevated/95 animate-in fade-in zoom-in-95"
        >
          <div className="flex items-center justify-between pb-2.5 mb-2.5 bg-surface-secondary/40 -mx-4 -mt-4 px-4 pt-3.5 rounded-t-xl">
            <span className="font-label-md text-label-md text-text-primary font-semibold">
              Retrieval Ranking
            </span>
            <button
              aria-label="Close info"
              onClick={onClose}
              type="button"
              className="text-text-secondary hover:text-text-primary p-0.5 rounded transition-colors"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
          <ul className="space-y-3 font-body-sm text-body-sm">
            <li className="flex items-start gap-2.5">
              <span className="w-1.5 h-1.5 rounded-full bg-primary-container mt-2 shrink-0"></span>
              <div>
                <strong className="font-semibold text-text-primary font-label-md">Hybrid</strong>
                <p className="text-text-secondary text-caption font-caption mt-0.5">
                  Combines meaning and keyword matching for balanced precision.
                </p>
              </div>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="w-1.5 h-1.5 rounded-full bg-tertiary-container/60 mt-2 shrink-0"></span>
              <div>
                <strong className="font-semibold text-text-primary font-label-md">Semantic</strong>
                <p className="text-text-secondary text-caption font-caption mt-0.5">
                  Prioritizes passages with similar contextual meaning and concepts.
                </p>
              </div>
            </li>
            <li className="flex items-start gap-2.5">
              <span className="w-1.5 h-1.5 rounded-full bg-border-subtle mt-2 shrink-0"></span>
              <div>
                <strong className="font-semibold text-text-primary font-label-md">Lexical</strong>
                <p className="text-text-secondary text-caption font-caption mt-0.5">
                  Prioritizes verbatim matching words and exact terminology.
                </p>
              </div>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
};
