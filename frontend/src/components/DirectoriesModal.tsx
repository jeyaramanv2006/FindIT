import React, { useState, useRef } from 'react';
import type { IndexedDirectory, SyncJob } from '../types';
import { pickNativeFolder } from '../services/api';

interface DirectoriesModalProps {
  isOpen: boolean;
  onClose: () => void;
  directories: IndexedDirectory[];
  onAddDirectory: (path: string) => void;
  onSyncDirectory: (directoryId: string) => void;
  onSyncAll: () => void;
  onRemoveDirectory: (directoryId: string) => void;
  activeJob: SyncJob | null;
}

export const DirectoriesModal: React.FC<DirectoriesModalProps> = ({
  isOpen,
  onClose,
  directories,
  onAddDirectory,
  onSyncDirectory,
  onSyncAll,
  onRemoveDirectory,
  activeJob,
}) => {
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [newPathInput, setNewPathInput] = useState('');
  const [showManualInput, setShowManualInput] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  if (!isOpen) return null;

  const totalFolders = directories.length;
  const totalFiles = directories.reduce((acc, d) => acc + d.file_count, 0);

  // File Explorer directory selection
  const handleBrowseFolder = async () => {
    // 1. Try host backend native folder picker (system dialog)
    try {
      const nativeResult = await pickNativeFolder();
      if (nativeResult.selected && nativeResult.path) {
        onAddDirectory(nativeResult.path);
        return;
      }
      if (nativeResult.selected === false) {
        return; // User cancelled
      }
    } catch {
      // Backend offline or pick endpoint unavailable; fallback
    }

    // 2. Try modern File System Access API
    if ('showDirectoryPicker' in window) {
      try {
        const picker = (window as unknown as { showDirectoryPicker: () => Promise<{ name: string }> }).showDirectoryPicker;
        const handle = await picker();
        if (handle && handle.name) {
          onAddDirectory(handle.name);
          return;
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'AbortError') return;
      }
    }

    // 3. Fallback to HTML5 directory picker
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const relPath = files[0].webkitRelativePath;
      const folderName = relPath ? relPath.split('/')[0] : files[0].name;
      onAddDirectory(folderName);
    }
    if (e.target) e.target.value = '';
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPathInput.trim()) {
      onAddDirectory(newPathInput.trim());
      setNewPathInput('');
      setShowManualInput(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="directoriesModalTitle"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto bg-[#1f1b18]/30 backdrop-blur-[2px] transition-all duration-200"
    >
      {/* Hidden file input for native folder picker */}
      <input
        ref={fileInputRef}
        type="file"
        // @ts-expect-error webkitdirectory is a standard non-standard attribute supported in all modern browsers
        webkitdirectory=""
        directory=""
        multiple
        onChange={handleFileInputChange}
        className="hidden"
      />

      {/* Modal Surface */}
      <div className="relative w-full max-w-[820px] bg-[#FFFEFB] border border-[#E3D2BE] rounded-2xl shadow-[0_20px_50px_-12px_rgba(41,37,34,0.18),0_4px_16px_-4px_rgba(41,37,34,0.06)] overflow-hidden flex flex-col my-auto transition-all duration-200 animate-in fade-in zoom-in-95">
        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-[#E3D2BE]/60 flex items-start justify-between gap-4 bg-[#FFFEFB]">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <span className="material-symbols-outlined text-[24px] text-[#9E2F2B]">folder_managed</span>
              <h2 id="directoriesModalTitle" className="font-headline-section text-[20px] font-semibold text-[#292522] tracking-tight">
                Indexed directories
              </h2>
            </div>
            <p className="font-body-sm text-[13px] text-[#77716B]">
              Manage your folders and keep your index up to date.
            </p>
          </div>
          <div className="flex items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={onSyncAll}
              className="bg-[#9E2F2B] hover:bg-[#852522] active:scale-95 text-white rounded-xl px-3.5 py-2 text-xs font-medium inline-flex items-center gap-1.5 shadow-sm transition-all focus-ring"
            >
              <span className={`material-symbols-outlined text-[16px] ${activeJob?.job_type === 'SYNC_ALL' ? 'animate-spin' : ''}`}>
                sync
              </span>
              <span>Sync all</span>
            </button>
            <button
              type="button"
              aria-label="Close dialog"
              onClick={onClose}
              className="p-1.5 text-[#77716B] hover:text-[#292522] hover:bg-[#EDE3D4]/50 rounded-lg transition-colors focus-ring"
            >
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 overflow-y-auto max-h-[calc(85vh-160px)] bg-[#FFFEFB]">
          {/* Statistics Boxes */}
          <div className="grid grid-cols-2 gap-3.5">
            <div className="p-3.5 rounded-xl bg-[#F8F4EC]/90 border border-[#E3D2BE]/70 flex items-center justify-between">
              <div>
                <span className="text-[11px] font-medium uppercase tracking-wider text-[#77716B]">Folders indexed</span>
                <div className="text-[22px] font-bold text-[#292522] mt-0.5">{totalFolders}</div>
              </div>
              <div className="w-9 h-9 rounded-lg bg-[#EDE3D4] flex items-center justify-center text-[#9E2F2B]">
                <span className="material-symbols-outlined text-[20px]">folder</span>
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-[#F8F4EC]/90 border border-[#E3D2BE]/70 flex items-center justify-between">
              <div>
                <span className="text-[11px] font-medium uppercase tracking-wider text-[#77716B]">Files indexed</span>
                <div className="text-[22px] font-bold text-[#292522] mt-0.5">{totalFiles.toLocaleString()}</div>
              </div>
              <div className="w-9 h-9 rounded-lg bg-[#EDE3D4] flex items-center justify-center text-[#9E2F2B]">
                <span className="material-symbols-outlined text-[20px]">description</span>
              </div>
            </div>
          </div>

          {/* Global Sync-All Progress Banner — Appears ONLY for 'SYNC_ALL' */}
          {activeJob && activeJob.job_type === 'SYNC_ALL' && (
            <div className="p-4 rounded-xl bg-[#F8F4EC] border border-[#9E2F2B]/30 relative overflow-hidden transition-all animate-in fade-in duration-200">
              <div className="flex items-start justify-between gap-3 mb-2.5">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#9E2F2B] text-[20px] animate-spin">sync</span>
                  <div>
                    <h4 className="text-[13px] font-semibold text-[#292522]">Overall sync progress</h4>
                    <p className="text-[12px] text-[#77716B]">{activeJob.stage}: {activeJob.current_file_or_desc || 'Scanning all registered folders...'}</p>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-[#9E2F2B]/10 text-[#9E2F2B] border border-[#9E2F2B]/20">
                  {Math.round(activeJob.progress_percent)}%
                </span>
              </div>
              <div className="w-full bg-[#E5D7C7] h-2 rounded-full overflow-hidden mb-2">
                <div
                  className="bg-[#9E2F2B] h-full rounded-full transition-all duration-300"
                  style={{ width: `${Math.max(5, activeJob.progress_percent)}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-[#77716B]">
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#9E2F2B] animate-ping" />
                  Processed {activeJob.files_processed} of {activeJob.files_discovered} files ({activeJob.passages_created} passages)
                </span>
              </div>
            </div>
          )}

          {/* Directory Rows */}
          <div className="space-y-2.5">
            {directories.map((dir) => {
              const isSyncingThisDir = Boolean(activeJob && activeJob.directory_id === dir.directory_id);

              return (
                <div
                  key={dir.directory_id}
                  className={`p-3.5 rounded-xl bg-[#F8F4EC]/60 border transition-all flex flex-col gap-2.5 ${
                    isSyncingThisDir
                      ? 'border-[#9E2F2B]/50 bg-[#F8F4EC]'
                      : 'border-[#E3D2BE]/60 hover:border-[#9E2F2B]/40'
                  }`}
                >
                  {/* Top directory item row */}
                  <div className="flex items-center justify-between gap-3 w-full">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="w-8 h-8 rounded-lg bg-[#EDE3D4] flex items-center justify-center text-[#9E2F2B] shrink-0">
                        <span className="material-symbols-outlined text-[18px]">folder</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-semibold text-[#292522] truncate">{dir.display_name}</h4>
                          <span className="text-[11px] font-mono px-1.5 py-0.5 rounded bg-[#EDE3D4] text-[#77716B]">
                            {dir.file_count} files
                          </span>
                        </div>
                        <p className="text-xs text-[#77716B] font-mono truncate">{dir.canonical_path}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => onSyncDirectory(dir.directory_id)}
                        title="Sync folder"
                        disabled={isSyncingThisDir}
                        className="p-1.5 rounded-lg text-[#77716B] hover:text-[#9E2F2B] hover:bg-[#EDE3D4] transition-colors focus-ring disabled:opacity-50"
                      >
                        <span className={`material-symbols-outlined text-[18px] ${isSyncingThisDir ? 'animate-spin text-[#9E2F2B]' : ''}`}>
                          refresh
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(dir.directory_id)}
                        title="Remove from index"
                        className="p-1.5 rounded-lg text-[#77716B] hover:text-[#ba1a1a] hover:bg-[#ffdad6]/50 transition-colors focus-ring"
                      >
                        <span className="material-symbols-outlined text-[18px]">delete</span>
                      </button>
                    </div>
                  </div>

                  {/* Individual Folder Sync Load Bar — Appears directly below this specific folder */}
                  {isSyncingThisDir && activeJob && (
                    <div className="pt-2.5 border-t border-[#E3D2BE]/60 w-full animate-in fade-in duration-200">
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <span className="flex items-center gap-1.5 text-[#77716B]">
                          <span className="material-symbols-outlined text-[15px] text-[#9E2F2B] animate-spin">sync</span>
                          <span className="font-semibold text-[#292522]">{activeJob.stage}:</span>
                          <span>{activeJob.current_file_or_desc || 'Scanning files...'}</span>
                        </span>
                        <span className="font-mono text-[11px] font-semibold text-[#9E2F2B] bg-[#9E2F2B]/10 px-2 py-0.5 rounded-full border border-[#9E2F2B]/20">
                          {Math.round(activeJob.progress_percent)}%
                        </span>
                      </div>
                      <div className="w-full bg-[#E5D7C7] h-1.5 rounded-full overflow-hidden mb-1.5">
                        <div
                          className="bg-[#9E2F2B] h-full rounded-full transition-all duration-300"
                          style={{ width: `${Math.max(5, activeJob.progress_percent)}%` }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-[#77716B]">
                        <span>Processed {activeJob.files_processed} of {activeJob.files_discovered} files</span>
                        <span>{activeJob.passages_created} passages created</span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Add Directory Section */}
          <div className="space-y-2.5">
            {showManualInput ? (
              <form onSubmit={handleManualSubmit} className="p-3.5 rounded-xl border border-[#9E2F2B]/40 bg-[#F8F4EC]/80 space-y-2 animate-in fade-in">
                <label className="block text-xs font-medium text-[#292522]">Enter directory path to index:</label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    autoFocus
                    value={newPathInput}
                    onChange={(e) => setNewPathInput(e.target.value)}
                    placeholder="/Users/you/Documents/Notes or C:/Users/..."
                    className="flex-1 px-3 py-1.5 text-xs bg-white border border-[#E3D2BE] rounded-lg focus:outline-none focus:border-[#9E2F2B]"
                  />
                  <button
                    type="submit"
                    className="px-3 py-1.5 text-xs font-medium text-white bg-[#9E2F2B] hover:bg-[#852522] rounded-lg transition-colors"
                  >
                    Register
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowManualInput(false)}
                    className="px-3 py-1.5 text-xs text-[#77716B] hover:text-[#292522]"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {/* 1. File Explorer native selection button */}
                <button
                  type="button"
                  onClick={handleBrowseFolder}
                  className="py-2.5 px-4 bg-surface hover:bg-[#FAF6F0] border border-[#9E2F2B]/40 hover:border-[#9E2F2B] rounded-xl text-xs font-medium text-[#9E2F2B] flex items-center justify-center gap-2 transition-all shadow-xs active:scale-98"
                >
                  <span className="material-symbols-outlined text-[18px]">folder_open</span>
                  <span>Select Folder via File Explorer</span>
                </button>

                {/* 2. Manual path entry button */}
                <button
                  type="button"
                  onClick={() => setShowManualInput(true)}
                  className="py-2.5 px-4 border border-dashed border-[#E3D2BE] hover:border-[#9E2F2B] rounded-xl text-xs font-medium text-[#77716B] hover:text-[#9E2F2B] flex items-center justify-center gap-2 transition-colors"
                >
                  <span className="material-symbols-outlined text-[16px]">edit_note</span>
                  <span>Enter path manually</span>
                </button>
              </div>
            )}
          </div>

          {/* Immutability Assurance Notice */}
          <div className="pt-2 text-center text-[11px] text-[#77716B] border-t border-[#E3D2BE]/40">
            <span className="inline-flex items-center gap-1">
              <span className="material-symbols-outlined text-[13px] text-[#9E2F2B]">verified_user</span>
              Removing a directory only clears internal search index records. Original files are never modified or deleted.
            </span>
          </div>
        </div>
      </div>

      {/* Confirmation Modal for Directory Removal */}
      {confirmDeleteId && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="w-full max-w-sm bg-white p-5 rounded-2xl border border-[#E3D2BE] shadow-xl space-y-3">
            <h3 className="text-sm font-bold text-[#292522]">Remove from index?</h3>
            <p className="text-xs text-[#77716B] leading-relaxed">
              This will remove FindIT's internal search index for this directory. Your original documents on disk will remain completely untouched.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteId(null)}
                className="px-3 py-1.5 text-xs text-[#77716B] hover:text-[#292522] rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  onRemoveDirectory(confirmDeleteId);
                  setConfirmDeleteId(null);
                }}
                className="px-3 py-1.5 text-xs font-medium text-white bg-[#ba1a1a] hover:bg-[#93000a] rounded-lg transition-colors"
              >
                Confirm Remove
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
