export interface SearchResult {
  chunk_id: string;
  document_id: string;
  filename: string;
  canonical_path: string;
  display_path: string;
  file_type: 'docx' | 'pdf' | 'pptx' | 'md' | 'code' | 'config' | 'txt' | string;
  location_label: string;
  passage_preview: string;
  hybrid_rank: number;
  semantic_rank?: number;
  lexical_rank?: number;
  rrf_score?: number;
  last_updated?: string;
}

export interface PassageDetail {
  chunk_id: string;
  document_id: string;
  filename: string;
  display_path: string;
  canonical_path: string;
  file_type: string;
  location_label: string;
  text: string;
  page_number?: number | null;
  slide_number?: number | null;
  start_line?: number | null;
  end_line?: number | null;
  section_heading?: string | null;
  hybrid_rank?: number;
  semantic_rank?: number;
  lexical_rank?: number;
}

export interface IndexedDirectory {
  directory_id: string;
  canonical_path: string;
  display_name: string;
  file_count: number;
  passage_count: number;
  sync_status: 'IDLE' | 'SYNCING' | 'ERROR';
  last_sync_completed_at?: string;
  last_error?: string | null;
}

export interface SyncJob {
  job_id: string;
  directory_id?: string;
  job_type: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  stage: string;
  progress_percent: number;
  files_discovered: number;
  files_processed: number;
  passages_created: number;
  current_file_or_desc?: string;
}
