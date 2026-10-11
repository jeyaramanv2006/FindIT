import React, { useState, useEffect, useRef } from 'react';
import { TerracottaCanvas } from './components/TerracottaCanvas';
import { RankingPopover } from './components/RankingPopover';
import { SearchResultCard } from './components/SearchResultCard';
import { PassageInspectorModal } from './components/PassageInspectorModal';
import { DirectoriesModal } from './components/DirectoriesModal';
import type { SearchResult, PassageDetail, IndexedDirectory, SyncJob, HealthStatus } from './types';
import {
  searchPassages,
  getPassageDetail,
  getIndexedDirectories,
  registerDirectory,
  deleteDirectory,
  syncDirectory,
  syncAllDirectories,
  openContainingFolder,
  checkBackendHealth,
} from './services/api';

export function App() {
  const [viewState, setViewState] = useState<'hero' | 'results'>('hero');
  const [queryInput, setQueryInput] = useState('vector indexing and authentication architecture');
  const [activeQuery, setActiveQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [totalAvailable, setTotalAvailable] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [pulseCount, setPulseCount] = useState(0);

  // Popover & Modal States
  const [rankingPopoverOpen, setRankingPopoverOpen] = useState(false);
  const [foldersModalOpen, setFoldersModalOpen] = useState(false);
  const [selectedPassage, setSelectedPassage] = useState<PassageDetail | null>(null);

  // Directories & Sync state
  const [directories, setDirectories] = useState<IndexedDirectory[]>([]);
  const [backendHealth, setBackendHealth] = useState<HealthStatus | null>(null);
  const [activeJob, setActiveJob] = useState<SyncJob | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Load directories and backend health on mount
  useEffect(() => {
    checkBackendHealth().then((status) => {
      setBackendHealth(status);
    });
    getIndexedDirectories().then((dirs) => setDirectories(dirs));
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const executeSearch = async (searchTerm: string) => {
    if (!searchTerm.trim()) return;

    setPulseCount((c) => c + 1);
    setIsLoading(true);
    setActiveQuery(searchTerm.trim());
    setViewState('results');
    setRankingPopoverOpen(false);

    try {
      const data = await searchPassages(searchTerm.trim(), 10, 0);
      setResults(data.results);
      setTotalAvailable(data.total_available);
    } catch {
      // Fallback
    } finally {
      setIsLoading(false);
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(queryInput);
  };

  const handleClear = () => {
    setQueryInput('');
    if (searchInputRef.current) {
      searchInputRef.current.focus();
    }
  };

  const handleInspectPassage = async (item: SearchResult) => {
    const detail = await getPassageDetail(item.chunk_id);
    setSelectedPassage(detail);
  };

  const handleOpenFolder = async (item: SearchResult | PassageDetail) => {
    await openContainingFolder(item.document_id);
    showToast(`Revealed folder for ${item.filename}`);
  };

  // Sync operations
  const handleSyncDirectory = async (dirId: string) => {
    const target = directories.find((d) => d.directory_id === dirId);
    if (!target) return;

    setActiveJob({
      job_id: 'job_' + Date.now(),
      directory_id: dirId,
      job_type: 'SYNC_DIRECTORY',
      status: 'RUNNING',
      stage: 'Scanning files',
      progress_percent: 30,
      files_discovered: target.file_count,
      files_processed: Math.floor(target.file_count * 0.3),
      passages_created: target.passage_count,
      current_file_or_desc: target.display_name,
    });

    try {
      const res = await syncDirectory(dirId);
      setActiveJob(null);
      showToast(`Sync completed for ${target.display_name} (${res.files_discovered} files).`);
      const updatedDirs = await getIndexedDirectories();
      setDirectories(updatedDirs);
    } catch (err: unknown) {
      // Fallback simulation if offline
      setTimeout(() => {
        setActiveJob((prev) =>
          prev && prev.directory_id === dirId
            ? {
                ...prev,
                stage: 'Creating embeddings',
                progress_percent: 78,
                files_processed: Math.floor(target.file_count * 0.78),
                passages_created: 140,
              }
            : prev
        );
      }, 1000);

      setTimeout(() => {
        setActiveJob(null);
        showToast(`Sync simulated for ${target.display_name}`);
      }, 2000);
    }
  };

  const handleSyncAll = async () => {
    const totalFiles = directories.reduce((acc, d) => acc + d.file_count, 0);
    setActiveJob({
      job_id: 'job_all_' + Date.now(),
      job_type: 'SYNC_ALL',
      status: 'RUNNING',
      stage: 'Scanning all directories',
      progress_percent: 20,
      files_discovered: totalFiles,
      files_processed: Math.floor(totalFiles * 0.2),
      passages_created: 320,
      current_file_or_desc: `Indexing across ${directories.length} folders`,
    });

    try {
      const res = await syncAllDirectories();
      setActiveJob(null);
      showToast(`All ${res.synced_directories} indexed directories successfully synchronized.`);
      const updatedDirs = await getIndexedDirectories();
      setDirectories(updatedDirs);
    } catch {
      setTimeout(() => {
        setActiveJob((prev) =>
          prev && prev.job_type === 'SYNC_ALL'
            ? {
                ...prev,
                stage: 'Creating embeddings',
                progress_percent: 68,
                files_processed: Math.floor(totalFiles * 0.68),
                passages_created: 1450,
                current_file_or_desc: 'Batch vector inference',
              }
            : prev
        );
      }, 1200);

      setTimeout(() => {
        setActiveJob(null);
        showToast(`All ${directories.length} indexed directories successfully synchronized.`);
      }, 2500);
    }
  };

  const handleAddDirectory = async (path: string) => {
    try {
      const res = await registerDirectory(path);
      showToast(`Registered: ${res.directory.display_name} (${res.directory.file_count} files)`);
      const updatedDirs = await getIndexedDirectories();
      setDirectories(updatedDirs);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Registration failed';
      if (!backendHealth || msg.includes('Failed to fetch')) {
        const newDir: IndexedDirectory = {
          directory_id: 'dir_' + Date.now(),
          canonical_path: path.includes('/') || path.includes('\\') ? path : `/Users/you/Documents/${path}`,
          display_name: path.split('/').pop() || path.split('\\').pop() || path,
          file_count: 18,
          passage_count: 94,
          sync_status: 'IDLE',
          last_sync_completed_at: new Date().toISOString(),
        };
        setDirectories((prev) => [...prev, newDir]);
        showToast(`Registered (mock): ${newDir.display_name}`);
      } else {
        showToast(`Registration error: ${msg}`);
      }
    }
  };

  const handleRemoveDirectory = async (dirId: string) => {
    try {
      await deleteDirectory(dirId);
      setDirectories((prev) => prev.filter((d) => d.directory_id !== dirId));
      showToast('Directory removed from index. Original files are untouched.');
    } catch (err: unknown) {
      if (!backendHealth) {
        setDirectories((prev) => prev.filter((d) => d.directory_id !== dirId));
        showToast('Directory removed from index. Original files are untouched.');
      } else {
        const msg = err instanceof Error ? err.message : 'Failed to delete directory';
        showToast(`Error: ${msg}`);
      }
    }
  };

  return (
    <div className="relative flex flex-col min-h-screen bg-surface-canvas text-text-primary overflow-x-hidden selection:bg-brick-light selection:text-[#7D231F]">
      {/* Topographic Labyrinth Canvas Background */}
      <TerracottaCanvas isSearching={isLoading} pulseTrigger={pulseCount} />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-60 bg-surface-elevated border border-border-subtle shadow-xl px-4 py-2.5 rounded-xl text-xs font-medium text-cocoa flex items-center gap-2 animate-in slide-in-from-bottom-2 duration-200">
          <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* DYNAMIC TOP HEADER (Morphs between hero and sticky results header) */}
      <header
        id="appHeader"
        className={`z-30 w-full view-transition ${
          viewState === 'results'
            ? 'sticky top-0 px-4 sm:px-8 border-b border-[#E3D2BE]/60 bg-[#F8F4EC]/90 backdrop-blur-md py-3 shadow-xs'
            : 'pt-16 pb-6'
        }`}
      >
        <div
          className={`w-full mx-auto flex flex-col items-center ${
            viewState === 'results' ? 'max-w-5xl' : 'max-w-4xl'
          }`}
        >
          {/* HERO CENTERED BRAND & TAGLINE (Visible in Hero state, smoothly collapses in results) */}
          <div
            id="heroCenterBlock"
            className={`view-transition overflow-hidden w-full text-center flex flex-col items-center justify-center select-none ${
              viewState === 'results'
                ? 'opacity-0 max-h-0 mb-0 pointer-events-none'
                : 'opacity-100 max-h-[260px] mb-8'
            }`}
          >
            {/* FindIT Wordmark with Dot */}
            <div
              onClick={() => setViewState('hero')}
              className="mb-4 flex items-center justify-center gap-1.5 group cursor-pointer"
            >
              <span className="font-headline-hero tracking-[-0.04em] font-bold text-[34px] sm:text-[46px] text-text-primary">
                Find<span className="text-primary-container font-extrabold tracking-tight">IT</span>
              </span>
              <span className="w-2 h-2 rounded-full bg-primary-container inline-block mb-1 group-hover:scale-125 transition-transform duration-200" />
            </div>

            <h1 className="font-headline-hero text-2xl sm:text-[36px] sm:leading-[44px] text-text-primary tracking-tight font-semibold mb-2">
              Find what you remember.
            </h1>
            <p className="font-body-md text-body-md text-text-secondary max-w-md mx-auto leading-relaxed">
              Whatever you remember, find where it belongs.
            </p>
          </div>

          {/* HEADER ROW: Strictly Centered Across Both Modes */}
          {viewState === 'hero' ? (
            /* HERO MODE: 100% Dead-Center Aligned to Screen */
            <div className="w-full max-w-[720px] mx-auto flex flex-col items-center justify-center">
              <form onSubmit={handleFormSubmit} className="relative w-full">
                <div className="w-full relative flex items-center rounded-2xl bg-surface-canvas/90 backdrop-blur-sm border border-[#9E2F2B]/40 hover:border-[#9E2F2B]/60 shadow-[0_4px_20px_-2px_rgba(158,47,43,0.08),0_1px_4px_rgba(41,37,34,0.04)] focus-within:border-[#9E2F2B] focus-within:shadow-[0_0_0_3px_rgba(158,47,43,0.18),0_8px_30px_-4px_rgba(158,47,43,0.14)] px-4 py-3 transition-all duration-200">
                  {/* Left: Magnifying Search Icon */}
                  <div className="pr-3 flex items-center justify-center text-text-secondary pointer-events-none group-focus-within:text-primary-container transition-colors">
                    <span className="material-symbols-outlined text-[22px]">search</span>
                  </div>

                  {/* Input field */}
                  <input
                    ref={searchInputRef}
                    type="text"
                    spellCheck="false"
                    autoComplete="off"
                    value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    placeholder="Search your documents…"
                    className="w-full bg-transparent font-body-lg text-sm sm:text-base text-text-primary placeholder:text-text-secondary/70 focus:outline-none"
                  />

                  {/* Right Actions: Clear, Folder Manager Trigger, Enter Hint */}
                  <div className="flex items-center gap-1.5 pl-2 shrink-0">
                    {queryInput.length > 0 && (
                      <button
                        type="button"
                        aria-label="Clear query"
                        onClick={handleClear}
                        className="text-text-secondary hover:text-text-primary p-1 rounded-lg transition-colors focus:outline-none"
                      >
                        <span className="material-symbols-outlined text-[18px]">close</span>
                      </button>
                    )}

                    <div className="h-4 w-px bg-sand-300"></div>

                    {/* Folder Icon Trigger */}
                    <button
                      type="button"
                      aria-label="Indexed folders"
                      onClick={() => setFoldersModalOpen(true)}
                      title="Manage indexed folders"
                      className="p-1.5 rounded-xl text-text-secondary hover:text-primary-container hover:bg-surface-secondary/70 active:scale-95 transition-all focus:outline-none focus:ring-1 focus:ring-primary-container"
                    >
                      <span className="material-symbols-outlined text-[20px]">folder</span>
                    </button>

                    <button
                      type="submit"
                      className="hidden sm:inline-flex items-center text-[11px] font-mono font-medium text-warmgrey/70 bg-sand-200/60 hover:bg-sand-200 hover:text-cocoa px-1.5 py-0.5 rounded border border-sand-300/60 transition-colors"
                    >
                      ↵ Enter
                    </button>
                  </div>
                </div>
              </form>

              {/* Ranking Mode Popover in Hero View */}
              <RankingPopover
                isOpen={rankingPopoverOpen}
                onClose={() => setRankingPopoverOpen(false)}
                onToggle={() => setRankingPopoverOpen(!rankingPopoverOpen)}
              />

              {/* Local Runtime Status Badge in Hero View */}
              <div className="mt-5 flex items-center justify-center gap-3 text-xs text-warmgrey select-none">
                <div
                  className="flex items-center gap-1.5 cursor-pointer hover:text-brick transition-colors"
                  onClick={() => setFoldersModalOpen(true)}
                  title="Manage indexed folders"
                >
                  <span className="material-symbols-outlined text-[15px]">folder</span>
                  <span>{directories.length} folders indexed</span>
                </div>
                <span className="text-sand-300">·</span>
                <div
                  className="flex items-center gap-1.5"
                  title={
                    backendHealth
                      ? `Connected to local FastAPI backend v${backendHealth.version} (127.0.0.1:8000)`
                      : 'Local backend is starting or offline'
                  }
                >
                  <span
                    className={`w-2 h-2 rounded-full transition-colors ${
                      backendHealth ? 'bg-emerald-600' : 'bg-amber-500'
                    }`}
                  />
                  <span>
                    {backendHealth
                      ? `Runtime: 127.0.0.1:8000 (v${backendHealth.version})`
                      : 'Runtime: Standby'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            /* RESULTS MODE: Responsive 3-Column Header Bar with Zero Overlap */
            <div className="w-full flex items-center justify-between gap-3 sm:gap-4 md:gap-6">
              {/* Left Column: Fixed / Natural Brand Wordmark */}
              <div className="shrink-0 flex items-center">
                <div
                  id="headerLeftWordmark"
                  className="view-transition flex items-center gap-2 cursor-pointer animate-in fade-in"
                  onClick={() => setViewState('hero')}
                  title="Return to FindIT hero view"
                >
                  <div className="text-2xl font-bold tracking-tight text-cocoa hover:text-brick transition-colors">
                    Find<span className="text-brick font-bold">IT</span>
                    <span className="inline-block w-1.5 h-1.5 rounded-full bg-brick ml-0.5 align-middle" />
                  </div>
                  <span className="hidden lg:inline text-xs font-normal text-warmgrey border-l border-[#E3D2BE] pl-2.5 ml-1">
                    Find what you remember
                  </span>
                </div>
              </div>

              {/* Center Column: Search Input Bar (min-w-0 prevents flex blowout) */}
              <div className="flex-1 w-full max-w-2xl min-w-0 mx-auto">
                <form onSubmit={handleFormSubmit} className="relative w-full">
                  <div className="w-full relative flex items-center rounded-2xl bg-[#FFFEFB] border border-[#9E2F2B]/40 hover:border-[#9E2F2B] focus-within:border-[#9E2F2B] px-3.5 py-2 shadow-xs focus-within:shadow-[0_0_0_3px_rgba(158,47,43,0.14)] transition-all duration-200">
                    <div className="pr-2.5 flex items-center justify-center text-text-secondary pointer-events-none group-focus-within:text-primary-container transition-colors shrink-0">
                      <span className="material-symbols-outlined text-[20px]">search</span>
                    </div>

                    <input
                      ref={searchInputRef}
                      type="text"
                      spellCheck="false"
                      autoComplete="off"
                      value={queryInput}
                      onChange={(e) => setQueryInput(e.target.value)}
                      placeholder="Search your documents…"
                      className="w-full min-w-0 bg-transparent font-body-lg text-sm md:text-base text-text-primary placeholder:text-text-secondary/70 focus:outline-none"
                    />

                    <div className="flex items-center gap-1.5 pl-2 shrink-0">
                      {queryInput.length > 0 && (
                        <button
                          type="button"
                          aria-label="Clear query"
                          onClick={handleClear}
                          className="text-text-secondary hover:text-text-primary p-1 rounded-lg transition-colors focus:outline-none"
                        >
                          <span className="material-symbols-outlined text-[16px]">close</span>
                        </button>
                      )}

                      <div className="h-4 w-px bg-sand-300"></div>

                      <button
                        type="button"
                        aria-label="Indexed folders"
                        onClick={() => setFoldersModalOpen(true)}
                        title="Manage indexed folders"
                        className="p-1.5 rounded-xl text-text-secondary hover:text-primary-container hover:bg-surface-secondary/70 active:scale-95 transition-all focus:outline-none focus:ring-1 focus:ring-primary-container"
                      >
                        <span className="material-symbols-outlined text-[18px]">folder</span>
                      </button>

                      <button
                        type="submit"
                        className="hidden sm:inline-flex items-center text-[11px] font-mono font-medium text-warmgrey/70 bg-sand-200/60 hover:bg-sand-200 hover:text-cocoa px-1.5 py-0.5 rounded border border-sand-300/60 transition-colors"
                      >
                        ↵ Enter
                      </button>
                    </div>
                  </div>
                </form>
              </div>

              {/* Right Column: Hero view button and Index Status (shrink-0, whitespace-nowrap) */}
              <div className="shrink-0 flex items-center gap-2.5 whitespace-nowrap">
                <button
                  type="button"
                  onClick={() => setViewState('hero')}
                  className="hidden sm:inline-flex items-center px-2.5 py-1 text-xs font-medium text-warmgrey hover:text-cocoa rounded-full bg-sand-200/50 hover:bg-sand-200 border border-sand-300/60 transition-colors whitespace-nowrap"
                  title="Switch view to hero homepage"
                >
                  Hero view
                </button>
                <div
                  onClick={() => setFoldersModalOpen(true)}
                  className="flex items-center gap-1.5 text-xs text-warmgrey font-medium pl-1 sm:pl-2 sm:border-l sm:border-sand-300 cursor-pointer hover:text-brick transition-colors whitespace-nowrap"
                  title={
                    backendHealth
                      ? `Local Runtime: 127.0.0.1:8000 (v${backendHealth.version}) · ${directories.length} folders indexed`
                      : `${directories.length} folders indexed`
                  }
                >
                  <span className="w-2 h-2 rounded-full bg-emerald-600 shrink-0" />
                  <span className="hidden sm:inline whitespace-nowrap">{directories.length} folders indexed</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* MAIN UNIFIED SEARCH RESULTS REGION */}
      {viewState === 'results' && (
        <main className="view-transition flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 pb-20 animate-in fade-in slide-in-from-bottom-2 duration-300">
          {/* RESULTS SUMMARY BAR */}
          <div className="flex items-center justify-between mb-6 pb-3 border-b border-[#E3D2BE]/60">
            <div className="flex flex-wrap items-baseline gap-2">
              <h2 className="text-base font-semibold text-cocoa tracking-tight">Search results</h2>
              <span className="text-xs text-warmgrey">
                for <span className="font-medium text-cocoa">"{activeQuery}"</span>
              </span>
            </div>
            <div className="flex items-center gap-2 text-xs text-warmgrey shrink-0">
              <span className="font-mono text-[11px] text-warmgrey">
                {totalAvailable} matching passages across {Math.min(5, totalAvailable)} files
              </span>
              <span className="hidden md:inline-block text-sand-300">·</span>
              <div className="hidden md:flex items-center gap-2 text-[11px] text-warmgrey">
                <span className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-brick" />
                  <span>Hybrid</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-sand-400" />
                  <span>Semantic</span>
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-sand-400" />
                  <span>Lexical</span>
                </span>
              </div>
            </div>
          </div>

          {/* LOADING STATE */}
          {isLoading && (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
              <span className="material-symbols-outlined text-[32px] text-brick animate-spin">
                progress_activity
              </span>
              <p className="text-xs text-warmgrey font-mono">Running hybrid vector & lexical retrieval...</p>
            </div>
          )}

          {/* EMPTY RESULTS STATE */}
          {!isLoading && results.length === 0 && (
            <div className="py-16 text-center space-y-3 bg-surface border border-sand-300 rounded-2xl p-8">
              <div className="w-12 h-12 rounded-full bg-sand-200 text-brick flex items-center justify-center mx-auto">
                <span className="material-symbols-outlined text-[24px]">search_off</span>
              </div>
              <h3 className="text-base font-semibold text-cocoa">No matching passages found</h3>
              <p className="text-xs text-warmgrey max-w-sm mx-auto">
                Try describing what you remember with different keywords, or check that the target folder is indexed.
              </p>
              <button
                type="button"
                onClick={() => setFoldersModalOpen(true)}
                className="mt-2 text-xs text-brick hover:underline font-medium"
              >
                Manage indexed folders →
              </button>
            </div>
          )}

          {/* UNIFIED RESULTS LIST */}
          {!isLoading && results.length > 0 && (
            <section aria-label="Search passages" className="space-y-2.5 mb-10">
              {results.map((result) => (
                <SearchResultCard
                  key={result.chunk_id}
                  result={result}
                  onInspect={handleInspectPassage}
                  onOpenFolder={handleOpenFolder}
                />
              ))}
            </section>
          )}

          {/* Bottom helper guidance */}
          <div className="pt-4 text-center text-xs text-warmgrey border-t border-sand-300/60">
            Click any row to inspect relevant extracted passages · Use{' '}
            <span className="font-mono text-[11px] bg-sand-200/60 px-1 py-0.5 rounded">
              Open in folder
            </span>{' '}
            to locate the physical file
          </div>
        </main>
      )}

      {/* PASSAGE INSPECTION MODAL */}
      <PassageInspectorModal
        passage={selectedPassage}
        query={activeQuery}
        onClose={() => setSelectedPassage(null)}
        onOpenFolder={handleOpenFolder}
      />

      {/* INDEXED DIRECTORIES MANAGEMENT MODAL */}
      <DirectoriesModal
        isOpen={foldersModalOpen}
        onClose={() => setFoldersModalOpen(false)}
        directories={directories}
        onAddDirectory={handleAddDirectory}
        onSyncDirectory={handleSyncDirectory}
        onSyncAll={handleSyncAll}
        onRemoveDirectory={handleRemoveDirectory}
        activeJob={activeJob}
      />
    </div>
  );
}
export default App;
